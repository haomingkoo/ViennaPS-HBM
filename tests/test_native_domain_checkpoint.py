"""Focused guards for native ViennaPS 2D domain checkpoints."""

from pathlib import Path
import tempfile

import numpy as np
import viennals as ls
import viennaps as ps

import native_domain_checkpoint as checkpoint
import traveler_metrics as tm


def analytic_mask_and_silicon():
    domain = ps.Domain(gridDelta=0.01, xExtent=1.0, yExtent=2.0)
    ps.MakeTrench(
        domain=domain,
        trenchWidth=0.3,
        trenchDepth=1.25,
        maskHeight=0.3,
        maskTaperAngle=0.0,
        halfTrench=False,
    ).apply()
    return domain


def ordered_materials(domain):
    material_map = domain.getMaterialMap()
    return [
        material_map.getMaterialAtIdx(index)
        for index in range(domain.getNumberOfLevelSets())
    ]


def assert_raw_level_sets_equal(before, after):
    assert ordered_materials(before) == ordered_materials(after)
    before_level_sets = before.getLevelSets()
    after_level_sets = after.getLevelSets()
    assert len(before_level_sets) == len(after_level_sets)
    for first, second in zip(before_level_sets, after_level_sets):
        assert first.getNumberOfPoints() == second.getNumberOfPoints()
        assert first.getNumberOfSegments() == second.getNumberOfSegments()
        assert first.getLevelSetWidth() == second.getLevelSetWidth()
    before_meshes = tm.raw_level_set_meshes(before)
    after_meshes = tm.raw_level_set_meshes(after)
    for first, second in zip(before_meshes, after_meshes):
        assert np.array_equal(first["nodes"], second["nodes"])
        assert np.array_equal(first["lines"], second["lines"])


def serialized_level_sets(domain, directory, prefix):
    result = []
    for index, level_set in enumerate(domain.getLevelSets()):
        path = Path(directory) / f"{prefix}-{index}.lvst"
        ls.Writer(level_set, str(path)).apply()
        result.append(path.read_bytes())
    return result


def test_native_checkpoint_roundtrip_preserves_level_sets_exactly():
    original = analytic_mask_and_silicon()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "domain.vpsd"
        original_level_sets = serialized_level_sets(original, directory, "before")
        digest = checkpoint.save_domain_atomic(path, original)
        restored = checkpoint.load_domain_checkpoint(
            path, expected_sha256=digest
        )
        restored_level_sets = serialized_level_sets(restored, directory, "after")

        assert original_level_sets == restored_level_sets
        assert_raw_level_sets_equal(original, restored)


def test_load_rejects_wrong_hash():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "domain.vpsd"
        checkpoint.save_domain_atomic(path, analytic_mask_and_silicon())
        try:
            checkpoint.load_domain_checkpoint(path, expected_sha256="0" * 64)
        except ValueError as error:
            assert "hash differs" in str(error)
        else:
            raise AssertionError("checkpoint load accepted an incorrect hash")


def test_failed_write_does_not_replace_existing_checkpoint():
    domain = analytic_mask_and_silicon()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "domain.vpsd"
        original_hash = checkpoint.save_domain_atomic(path, domain)
        writer = checkpoint.ps.Writer

        class FailingWriter:
            def __init__(self, _domain, filename):
                self.filename = filename

            def apply(self):
                Path(self.filename).write_bytes(b"partial")
                raise RuntimeError("injected write failure")

        checkpoint.ps.Writer = FailingWriter
        try:
            try:
                checkpoint.save_domain_atomic(path, domain)
            except RuntimeError as error:
                assert "injected write failure" in str(error)
            else:
                raise AssertionError("injected Writer failure did not propagate")
        finally:
            checkpoint.ps.Writer = writer

        assert checkpoint.file_sha256(path) == original_hash
        checkpoint.load_domain_checkpoint(path, expected_sha256=original_hash)
        assert not list(path.parent.glob(".*.tmp-*.vpsd"))


def test_raw_silicon_extraction_does_not_reconstruct_surface():
    original = analytic_mask_and_silicon()
    silicon_index = ordered_materials(original).index(ps.Material.Si)
    original_silicon = next(
        mesh
        for mesh in tm.raw_level_set_meshes(original)
        if mesh["material"] == ps.Material.Si
    )
    extracted = checkpoint.extract_raw_silicon_domain(original)
    extracted_silicon = tm.raw_level_set_meshes(extracted)[0]

    assert ordered_materials(extracted) == [ps.Material.Si]
    assert original.getNumberOfLevelSets() == 2
    assert np.array_equal(original_silicon["nodes"], extracted_silicon["nodes"])
    assert np.array_equal(original_silicon["lines"], extracted_silicon["lines"])
    with tempfile.TemporaryDirectory() as directory:
        before = serialized_level_sets(original, directory, "before")[silicon_index]
        after = serialized_level_sets(extracted, directory, "after")[0]
        assert before == after


if __name__ == "__main__":
    test_native_checkpoint_roundtrip_preserves_level_sets_exactly()
    test_load_rejects_wrong_hash()
    test_failed_write_does_not_replace_existing_checkpoint()
    test_raw_silicon_extraction_does_not_reconstruct_surface()
    print("native domain checkpoint checks: PASS")
