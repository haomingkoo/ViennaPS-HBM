#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_BASE="2956ed587984c6dc38be24c6e2390e10c9b2f0a7"
readonly EXPECTED_PATCH_SHA256="0b635afc6ac1a4545748009d7d3efef0d2f15e1dc885e4698b409af85e23cc74"
readonly EXPECTED_SOURCE_SHA256="bbfc0c5b687ae55d62cfedfbcd90a6655b8fe893b2bf264d3c9575e0c172b3fd"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly BASE_REPOSITORY="${VIENNAPS_BASE_REPOSITORY:-${PROJECT_ROOT}/ViennaPS}"
readonly SOURCE_DIR="${VIENNAPS_CMP_SOURCE_DIR:-/tmp/viennaps-height-material-cmp-src}"
readonly BUILD_DIR="${VIENNAPS_CMP_BUILD_DIR:-/tmp/viennaps-height-material-cmp-build}"
readonly INSTALL_PREFIX="${1:-${VIENNAPS_CMP_INSTALL_PREFIX:-/tmp/viennaps-height-material-cmp-exact}}"
readonly PATCH_FILE="${PROJECT_ROOT}/patches/viennaps-height-material-cmp.patch"
readonly BUILD_JOBS="${VIENNAPS_BUILD_JOBS:-1}"
readonly PYTHON_EXECUTABLE="${Python_EXECUTABLE:-${PYTHON_EXECUTABLE:-${PROJECT_ROOT}/.venv/bin/python}}"
readonly OPENMP_ROOT="${OpenMP_ROOT:-${OPENMP_ROOT:-$(brew --prefix libomp 2>/dev/null || true)}}"

if (( $# > 1 )); then
  echo "usage: $0 [install-prefix]" >&2
  exit 2
fi
if [[ "${INSTALL_PREFIX}" == "${PROJECT_ROOT}/.venv" ||
      "${INSTALL_PREFIX}" == "${PROJECT_ROOT}/.venv/"* ]]; then
  echo "Refusing to install the isolated CMP build into the project .venv." >&2
  exit 2
fi
if [[ ! -f "${PATCH_FILE}" || ! -x "${PYTHON_EXECUTABLE}" ]]; then
  echo "CMP patch or Python executable is missing." >&2
  exit 1
fi
if ! [[ "${BUILD_JOBS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "VIENNAPS_BUILD_JOBS must be a positive integer." >&2
  exit 2
fi
if [[ "$(shasum -a 256 "${PATCH_FILE}" | awk '{print $1}')" != "${EXPECTED_PATCH_SHA256}" ]]; then
  echo "CMP patch hash does not match the packaged source." >&2
  exit 1
fi
if ! git -C "${BASE_REPOSITORY}" cat-file -e "${EXPECTED_BASE}^{commit}"; then
  echo "Pinned ViennaPS commit is unavailable in ${BASE_REPOSITORY}." >&2
  exit 1
fi

if ! git -C "${SOURCE_DIR}" rev-parse --git-dir >/dev/null 2>&1; then
  if [[ -e "${SOURCE_DIR}" ]]; then
    echo "Refusing to replace non-worktree path ${SOURCE_DIR}." >&2
    exit 1
  fi
  git -C "${BASE_REPOSITORY}" worktree add --detach \
    "${SOURCE_DIR}" "${EXPECTED_BASE}"
fi

actual_base="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ "${actual_base}" != "${EXPECTED_BASE}" ]]; then
  echo "Isolated ViennaPS HEAD is ${actual_base}; expected ${EXPECTED_BASE}." >&2
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
?? include/viennaps/models/psHeightMaterialCMP.hpp
EOF
)"

snapshot="$(mktemp "${TMPDIR:-/tmp}/viennaps-cmp-patch.XXXXXX")"
trap 'rm -f "${snapshot}"' EXIT

verify_exact_patched_state() {
  local status no_index_status source_hash
  status="$(git -C "${SOURCE_DIR}" status --short --untracked-files=all)"
  if [[ "${status}" != "${EXPECTED_PATCHED_STATUS}" ]]; then
    echo "Isolated source has changes outside the packaged CMP patch." >&2
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
    include/viennaps/models/psHeightMaterialCMP.hpp >>"${snapshot}"
  no_index_status=$?
  set -e
  if [[ ${no_index_status} -ne 1 ]] || ! cmp -s "${PATCH_FILE}" "${snapshot}"; then
    echo "Isolated source does not exactly match the packaged CMP patch." >&2
    return 1
  fi
  source_hash="$(shasum -a 256 "${SOURCE_DIR}/include/viennaps/models/psHeightMaterialCMP.hpp" | awk '{print $1}')"
  if [[ "${source_hash}" != "${EXPECTED_SOURCE_SHA256}" ]]; then
    echo "HeightMaterialCMP model source hash mismatch." >&2
    return 1
  fi
}

if git -C "${SOURCE_DIR}" apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
  verify_exact_patched_state
  echo "HeightMaterialCMP patch is already applied exactly."
elif git -C "${SOURCE_DIR}" apply --check "${PATCH_FILE}" >/dev/null 2>&1; then
  if [[ -n "$(git -C "${SOURCE_DIR}" status --short --untracked-files=all)" ]]; then
    echo "Refusing to patch a non-clean isolated checkout." >&2
    exit 1
  fi
  git -C "${SOURCE_DIR}" apply "${PATCH_FILE}"
  verify_exact_patched_state
  echo "Applied HeightMaterialCMP patch to isolated source."
else
  echo "CMP patch is neither cleanly applicable nor exactly applied." >&2
  exit 1
fi

cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" \
  -DVIENNAPS_BUILD_PYTHON=ON \
  -DVIENNAPS_BUILD_EXAMPLES=OFF \
  -DVIENNAPS_BUILD_TESTS=OFF \
  ${OPENMP_ROOT:+-DOpenMP_ROOT="${OPENMP_ROOT}"} \
  -DPython_EXECUTABLE="${PYTHON_EXECUTABLE}"

echo "Building isolated HeightMaterialCMP _core with ${BUILD_JOBS} job(s)."
cmake --build "${BUILD_DIR}" --target _core --parallel "${BUILD_JOBS}"

echo "Installing isolated HeightMaterialCMP into ${INSTALL_PREFIX}."
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_PREFIX}"

binary="$(find "${INSTALL_PREFIX}" -type f -name '_core*.so' -print -quit)"
if [[ -z "${binary}" ]]; then
  echo "Installed ViennaPS binary was not found." >&2
  exit 1
fi
echo "base_commit=${EXPECTED_BASE}"
echo "patch_sha256=$(shasum -a 256 "${PATCH_FILE}" | awk '{print $1}')"
echo "model_source_sha256=$(shasum -a 256 "${SOURCE_DIR}/include/viennaps/models/psHeightMaterialCMP.hpp" | awk '{print $1}')"
echo "binary_sha256=$(shasum -a 256 "${binary}" | awk '{print $1}')"
