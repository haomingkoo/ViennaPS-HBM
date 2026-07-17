"""Atomic native ViennaPS 2D domain checkpoints."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import viennals as ls
import viennaps as ps


VPSD_MAGIC = b"psDomain"
VPSD_READER_VERSION = 2
VPSD_2D = 2


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_domain(domain) -> tuple:
    count = domain.getNumberOfLevelSets()
    if count < 1:
        raise ValueError("checkpoint domain contains no level sets")
    material_map = domain.getMaterialMap()
    if material_map.size() != count:
        raise ValueError("checkpoint material map and level-set count differ")
    if not domain.getSetup().isValid():
        raise ValueError("checkpoint domain setup is invalid")
    return tuple(material_map.getMaterialAtIdx(i) for i in range(count))


def _validate_file_header(path) -> None:
    with Path(path).open("rb") as handle:
        header = handle.read(10)
    if len(header) < 9 or header[:8] != VPSD_MAGIC:
        raise ValueError("checkpoint is not a ViennaPS domain file")
    version = header[8]
    if version > VPSD_READER_VERSION:
        raise ValueError(f"unsupported ViennaPS domain version: {version}")
    if version >= 2 and (len(header) < 10 or header[9] != VPSD_2D):
        raise ValueError("checkpoint is not a 2D ViennaPS domain")


def save_domain_atomic(path, domain) -> str:
    """Atomically write a native 2D ``.vpsd`` checkpoint and return its SHA-256."""
    path = Path(path)
    if path.suffix != ".vpsd":
        raise ValueError("native ViennaPS checkpoint path must end with .vpsd")
    _validate_domain(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp-{os.getpid()}.vpsd")
    temporary.unlink(missing_ok=True)
    try:
        ps.Writer(domain, str(temporary)).apply()
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise OSError("ViennaPS Writer did not create a checkpoint")
        _validate_file_header(temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return file_sha256(path)


def load_domain_checkpoint(path, *, expected_sha256: str):
    """Hash-check and load a native 2D ViennaPS domain checkpoint."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("checkpoint file is missing")
    observed_sha256 = file_sha256(path)
    if observed_sha256 != expected_sha256:
        raise ValueError("checkpoint file hash differs")
    _validate_file_header(path)
    domain = ps.Domain()
    ps.Reader(domain, str(path)).apply()
    _validate_domain(domain)
    return domain


def extract_raw_silicon_domain(domain):
    """Copy the sole raw Si level set without meshing or Boolean reconstruction."""
    material_map = domain.getMaterialMap()
    indices = [
        index
        for index in range(domain.getNumberOfLevelSets())
        if material_map.getMaterialAtIdx(index) == ps.Material.Si
    ]
    if len(indices) != 1:
        raise ValueError("checkpoint must contain exactly one Si level set")
    silicon = ls.Domain(domain.getLevelSets()[indices[0]])
    extracted = ps.Domain()
    extracted.insertNextLevelSetAsMaterial(silicon, ps.Material.Si, False)
    _validate_domain(extracted)
    return extracted
