"""Focused checks for the descriptive Cu transport effect audit."""

import numpy as np

import review_copper_fill_transport_effects as effects


def test_balanced_decomposition_separates_main_effect_and_interaction():
    sticking = np.arange(7, dtype=float)[:, None, None]
    power = np.arange(3, dtype=float)[None, :, None]
    stream = np.asarray([-0.03, -0.01, 0.01, 0.03])[None, None, :]
    values = sticking + 2.0 * power + 0.5 * sticking * power + stream
    result = effects.range_variance_decomposition(values)
    shares = result["sampled_range_variance_share"]
    assert shares["sticking"] > 0.0
    assert shares["source_power"] > 0.0
    assert shares["sticking_x_source_power"] > 0.0
    assert shares["paired_stream_residual"] > 0.0
    assert abs(sum(shares.values()) - 1.0) < 1e-12


def test_actual_audit_is_complete_and_scoped():
    rows = [
        effects.json.loads(line)
        for line in effects.DEFAULT_ROWS.read_text().splitlines()
        if line.strip()
    ]
    reviewed = effects.json.loads(effects.DEFAULT_REVIEWED_SUMMARY.read_text())
    summary = effects.build_summary(rows, reviewed)
    assert summary["status"] == "complete"
    assert summary["case_count"] == 168
    assert summary["validation_errors"] == []
    assert "not calibration" in summary["scope"]
    assert summary["monotonicity"][
        "flux_ratio_non_decreasing_with_sticking"
    ] == {"passing_sequences": 24, "total_sequences": 24}
    assert summary["paired_geometry_effect"][
        "nominal_minus_continuity_flux_ratio_positive_pairs"
    ] == 84
    continuity_flux = summary["factor_effects"]["continuity"][
        "floor_to_lower_flux_ratio"
    ]["sampled_range_variance_share"]
    nominal_velocity = summary["factor_effects"]["nominal_hbm"][
        "floor_to_lower_velocity_ratio"
    ]["sampled_range_variance_share"]
    assert np.isclose(continuity_flux["sticking"], 0.9957, atol=5e-5)
    assert np.isclose(nominal_velocity["source_power"], 0.5733, atol=5e-5)


if __name__ == "__main__":
    test_balanced_decomposition_separates_main_effect_and_interaction()
    test_actual_audit_is_complete_and_scoped()
    print("Cu-fill transport effect audit tests: PASS")
