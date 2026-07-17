#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_BASE="2956ed587984c6dc38be24c6e2390e10c9b2f0a7"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly SOURCE_DIR="${VIENNAPS_SOURCE_DIR:-${PROJECT_ROOT}/ViennaPS}"
readonly BUILD_DIR="${VIENNAPS_BUILD_DIR:-${SOURCE_DIR}/build}"
readonly PATCH_FILE="${PROJECT_ROOT}/patches/viennaps-copper-suppression-fill.patch"
readonly INSTALL_PREFIX="${1:-${VIENNAPS_INSTALL_PREFIX:-${TMPDIR:-/tmp}/viennaps-copper-suppression-fill}}"
readonly BUILD_JOBS="${VIENNAPS_BUILD_JOBS:-1}"

if (( $# > 1 )); then
  echo "usage: $0 [install-prefix]" >&2
  exit 2
fi
if [[ ! -d "${SOURCE_DIR}/.git" || ! -f "${PATCH_FILE}" ]]; then
  echo "ViennaPS checkout or packaged patch is missing." >&2
  exit 1
fi
if [[ ! "${BUILD_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "VIENNAPS_BUILD_JOBS must be a positive integer." >&2
  exit 2
fi

actual_base="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ "${actual_base}" != "${EXPECTED_BASE}" ]]; then
  echo "ViennaPS HEAD is ${actual_base}; expected ${EXPECTED_BASE}." >&2
  exit 1
fi

readonly EXPECTED_PATCHED_STATUS="$(cat <<'EOF'
 M include/viennaps/viennaps.hpp
 M python/pyWrap.cpp
 M python/pyWrapDimension.hpp
 M python/viennaps/__init__.pyi
 M python/viennaps/_core/__init__.pyi
 M python/viennaps/d2/__init__.pyi
 M python/viennaps/d3/__init__.pyi
?? include/viennaps/models/psCopperSuppressionFill.hpp
EOF
)"

snapshot="$(mktemp "${TMPDIR:-/tmp}/viennaps-copper-patch.XXXXXX")"
trap 'rm -f "${snapshot}"' EXIT

verify_exact_patched_state() {
  local status no_index_status
  status="$(git -C "${SOURCE_DIR}" status --short --untracked-files=all)"
  if [[ "${status}" != "${EXPECTED_PATCHED_STATUS}" ]]; then
    echo "ViennaPS has changes outside the packaged patch or a partial patch." >&2
    git -C "${SOURCE_DIR}" status --short --untracked-files=all >&2
    return 1
  fi

  git -C "${SOURCE_DIR}" diff --binary -- \
    include/viennaps/viennaps.hpp \
    python/pyWrap.cpp \
    python/pyWrapDimension.hpp \
    python/viennaps/__init__.pyi \
    python/viennaps/_core/__init__.pyi \
    python/viennaps/d2/__init__.pyi \
    python/viennaps/d3/__init__.pyi >"${snapshot}"

  set +e
  git -C "${SOURCE_DIR}" diff --no-index --binary -- /dev/null \
    include/viennaps/models/psCopperSuppressionFill.hpp >>"${snapshot}"
  no_index_status=$?
  set -e
  if [[ ${no_index_status} -ne 1 ]] || ! cmp -s "${PATCH_FILE}" "${snapshot}"; then
    echo "ViennaPS changes do not exactly match the packaged patch." >&2
    return 1
  fi
}

if git -C "${SOURCE_DIR}" apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
  verify_exact_patched_state
  echo "CopperSuppressionFill patch is already applied exactly."
elif git -C "${SOURCE_DIR}" apply --check "${PATCH_FILE}" >/dev/null 2>&1; then
  if [[ -n "$(git -C "${SOURCE_DIR}" status --short --untracked-files=all)" ]]; then
    echo "Refusing to patch a non-clean ViennaPS checkout." >&2
    git -C "${SOURCE_DIR}" status --short --untracked-files=all >&2
    exit 1
  fi
  git -C "${SOURCE_DIR}" apply "${PATCH_FILE}"
  verify_exact_patched_state
  echo "Applied CopperSuppressionFill patch."
else
  echo "Patch is neither cleanly applicable nor exactly applied." >&2
  exit 1
fi

if [[ ! -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  python_executable="${Python_EXECUTABLE:-${PYTHON_EXECUTABLE:-$(command -v python3)}}"
  cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" \
    -DVIENNAPS_BUILD_PYTHON=ON \
    -DVIENNAPS_BUILD_EXAMPLES=OFF \
    -DVIENNAPS_BUILD_TESTS=OFF \
    -DPython_EXECUTABLE="${python_executable}"
fi

echo "Building ViennaPS _core with ${BUILD_JOBS} job(s)."
cmake --build "${BUILD_DIR}" --target _core --parallel "${BUILD_JOBS}"

echo "Installing ViennaPS into ${INSTALL_PREFIX}."
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_PREFIX}"
