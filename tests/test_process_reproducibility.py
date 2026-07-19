import numpy as np
import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


def etched_si_nodes(seed):
    geometry = tp.make_initial_geometry(grid_delta=0.02)
    geometry, _ = tp.bosch_etch(
        geometry,
        num_cycles=2,
        etch_time=0.5,
        initial_etch_time=0.2,
        rays_per_point=200,
        rng_seed=seed,
    )
    return next(
        mesh["nodes"]
        for mesh in tm.raw_level_set_meshes(geometry)
        if mesh["material"] == ps.Material.Si
    )


def test_same_seed_reproduces_raw_mesh():
    first = etched_si_nodes(1234)
    second = etched_si_nodes(1234)
    assert first.shape == second.shape
    assert np.allclose(first, second, rtol=0.0, atol=1e-14)


def test_different_seed_changes_raw_mesh():
    first = etched_si_nodes(1234)
    second = etched_si_nodes(1235)
    assert first.shape != second.shape or not np.array_equal(first, second)


def deposited_liner_nodes(seed):
    geometry = ps.Domain(gridDelta=0.02, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(
        domain=geometry,
        holeRadius=0.15,
        holeDepth=1.0,
        maskHeight=0.3,
        holeShape=ps.HoleShape.QUARTER,
    ).apply()
    tp.strip_pattern_mask(geometry)
    tp.deposit_conformal(
        geometry,
        ps.Material.SiO2,
        0.04,
        sticking=0.05,
        rays_per_point=200,
        rng_seed=seed,
    )
    return tm.raw_level_set_meshes(geometry)[-1]["nodes"]


def test_deposition_seed_controls_raw_mesh():
    first = deposited_liner_nodes(4321)
    repeated = deposited_liner_nodes(4321)
    changed = deposited_liner_nodes(4322)
    assert first.shape == repeated.shape
    assert np.allclose(first, repeated, rtol=0.0, atol=1e-14)
    assert first.shape != changed.shape or not np.array_equal(first, changed)


if __name__ == "__main__":
    test_same_seed_reproduces_raw_mesh()
    test_different_seed_changes_raw_mesh()
    test_deposition_seed_controls_raw_mesh()
    print("process reproducibility checks: PASS")
