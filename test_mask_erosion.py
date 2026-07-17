"""Bosch mask erosion must be measurable and complete loss must stay visible."""

import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


def remaining_mask_height(mask_ion_rate):
    geometry = tp.make_initial_geometry(
        grid_delta=0.02,
        hole_shape=ps.HoleShape.FULL,
    )
    tp.bosch_etch(
        geometry,
        num_cycles=2,
        etch_time=0.5,
        initial_etch_time=0.2,
        rays_per_point=300,
        rng_seed=99100,
        mask_ion_rate=mask_ion_rate,
    )
    masks = [
        mesh
        for mesh in tm.raw_level_set_meshes(geometry)
        if mesh["material"] == ps.Material.Mask and len(mesh["nodes"])
    ]
    return float(masks[0]["nodes"][:, 1].max()) if masks else 0.0


def test_mask_erosion_is_monotonic_for_a_shared_stream():
    no_erosion = remaining_mask_height(0.0)
    moderate = remaining_mask_height(-0.1)
    consumed = remaining_mask_height(-0.5)
    assert no_erosion > moderate > consumed
    assert consumed == 0.0


def test_positive_mask_etch_rate_is_rejected():
    geometry = tp.make_initial_geometry(grid_delta=0.02)
    try:
        tp.bosch_etch(
            geometry,
            num_cycles=1,
            rays_per_point=100,
            rng_seed=99100,
            mask_ion_rate=0.1,
        )
    except ValueError as error:
        assert "zero or negative" in str(error)
    else:
        raise AssertionError("positive mask etch rate was accepted")


if __name__ == "__main__":
    test_mask_erosion_is_monotonic_for_a_shared_stream()
    test_positive_mask_etch_rate_is_rejected()
    print("mask erosion checks: PASS")
