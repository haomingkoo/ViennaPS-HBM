"""Prescribed 2D controls for testing copper topology metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import SupportsFloat, SupportsIndex, cast

import numpy as np
import viennals as ls
import viennals.d2 as ls2

import traveler_metrics as tm
from process_config import PROCESS_CONFIG


MORPHOLOGY_ONLY_SCOPE = (
    "morphology-only ViennaLS geometry control; not electrochemical or recipe physics"
)

MORPHOLOGY_CONFIG = PROCESS_CONFIG["morphology"]
GRID_DELTA = MORPHOLOGY_CONFIG["grid_delta"]
VIA_RADIUS = MORPHOLOGY_CONFIG["via_radius"]
FIELD_Y = MORPHOLOGY_CONFIG["field_y"]
FLOOR_Y = MORPHOLOGY_CONFIG["floor_y"]
BOUNDS = tuple(MORPHOLOGY_CONFIG["bounds"])
FIELD_SAMPLE_XS = tuple(MORPHOLOGY_CONFIG["field_sample_xs"])
OPENING_TOP_Y = MORPHOLOGY_CONFIG["opening_top_y"]
VIA_EDGE_MARGIN_CELLS = MORPHOLOGY_CONFIG["via_edge_margin_cells"]
FIELD_MARGIN_CELLS = MORPHOLOGY_CONFIG["field_margin_cells"]
UPWARD_NORMAL_MIN = MORPHOLOGY_CONFIG["upward_normal_min"]
TOP_HEAVY_LENGTH_SCALE = MORPHOLOGY_CONFIG["top_heavy_length_scale"]
TOP_HEAVY_BASE_RATE = MORPHOLOGY_CONFIG["top_heavy_base_rate"]
TOP_HEAVY_RATE_SPAN = MORPHOLOGY_CONFIG["top_heavy_rate_span"]
ADVECTION_TIME_STEP_RATIO = MORPHOLOGY_CONFIG["advection_time_step_ratio"]
METRIC_TOLERANCE_CELLS = MORPHOLOGY_CONFIG["metric_tolerance_cells"]
INCOMPLETE_FILL_DURATION = MORPHOLOGY_CONFIG["incomplete_fill_duration"]
CLOSURE_DURATION = MORPHOLOGY_CONFIG["closure_duration"]
OVERBURDEN_DURATION = MORPHOLOGY_CONFIG["overburden_duration"]
FAILED_FILL_DURATION = MORPHOLOGY_CONFIG["failed_fill_duration"]


class MorphologyOnlyVelocity(ls.VelocityField):
    """Explicit velocity profiles used only as morphology controls."""

    def __init__(self, profile: str):
        super().__init__()
        self.profile = profile

    def getScalarVelocity(  # ty: ignore[invalid-method-override]
        self,
        coordinate: object,
        material: object,
        normal: object,
        point_id: object,
    ) -> float:
        coordinate_values = cast(Sequence[SupportsFloat | SupportsIndex], coordinate)
        normal_values = cast(Sequence[SupportsFloat | SupportsIndex], normal)
        if self.profile == "bottom_up":
            in_via = abs(float(coordinate_values[0])) < (
                VIA_RADIUS - VIA_EDGE_MARGIN_CELLS * GRID_DELTA
            )
            below_field = float(coordinate_values[1]) < (
                FIELD_Y + FIELD_MARGIN_CELLS * GRID_DELTA
            )
            upward_facing = float(normal_values[1]) > UPWARD_NORMAL_MIN
            return 1.0 if in_via and below_field and upward_facing else 0.0
        if self.profile == "top_heavy":
            depth_attenuation = math.exp(
                min(float(coordinate_values[1]), FIELD_Y) / TOP_HEAVY_LENGTH_SCALE
            )
            return TOP_HEAVY_BASE_RATE + TOP_HEAVY_RATE_SPAN * depth_attenuation
        if self.profile == "uniform":
            return 1.0
        raise ValueError(f"unknown morphology-only velocity profile: {self.profile}")

    def getVectorVelocity(  # ty: ignore[invalid-method-override]
        self,
        coordinate: object,
        material: object,
        normal: object,
        point_id: object,
    ) -> list[float]:
        return [0.0, 0.0, 0.0]


def _build_morphology_only_via():
    """Build an analytic 2D via cross-section for morphology controls."""
    boundary_conditions = (
        ls.BoundaryConditionEnum.REFLECTIVE_BOUNDARY,
        ls.BoundaryConditionEnum.INFINITE_BOUNDARY,
    )
    substrate = ls2.Domain(BOUNDS, boundary_conditions, GRID_DELTA)
    ls2.MakeGeometry(substrate, ls2.Plane((0.0, FIELD_Y), (0.0, 1.0))).apply()

    opening = ls2.Domain(BOUNDS, boundary_conditions, GRID_DELTA)
    ls2.MakeGeometry(
        opening,
        ls2.Box((-VIA_RADIUS, FLOOR_Y), (VIA_RADIUS, OPENING_TOP_Y)),
    ).apply()
    ls2.BooleanOperation(
        substrate,
        opening,
        ls.BooleanOperationEnum.RELATIVE_COMPLEMENT,
    ).apply()
    return substrate, ls2.Domain(substrate)


def _advect_morphology_only(substrate, fill, velocity, duration, *, ignore_voids=False):
    """Apply one deterministic, morphology-only low-level ViennaLS advection."""
    advection = ls2.Advect()
    advection.insertNextLevelSet(substrate)
    advection.insertNextLevelSet(fill)
    advection.setVelocityField(velocity)
    advection.setCalculateNormalVectors(True)
    advection.setIgnoreVoids(ignore_voids)
    advection.setTimeStepRatio(ADVECTION_TIME_STEP_RATIO)
    advection.setSpatialScheme(ls.SpatialSchemeEnum.ENGQUIST_OSHER_1ST_ORDER)
    advection.setTemporalScheme(ls.TemporalSchemeEnum.RUNGE_KUTTA_2ND_ORDER)
    advection.setAdvectionTime(duration)
    advection.apply()


def _measure_morphology_only(fill, *, initial_cavity_area=None):
    """Measure one morphology-only fill surface with the traveler topology metric."""
    mesh = ls.Mesh()
    ls2.ToSurfaceMesh(fill, mesh).apply()
    return tm.fill_topology_metrics_2d(
        np.asarray(mesh.getNodes(), dtype=float),
        np.asarray(mesh.getLines(), dtype=int),
        field_y=FIELD_Y,
        floor_y=FLOOR_Y,
        via_x_bounds=(-VIA_RADIUS, VIA_RADIUS),
        field_sample_xs=FIELD_SAMPLE_XS,
        center_x=0.0,
        tolerance=METRIC_TOLERANCE_CELLS * GRID_DELTA,
        initial_cavity_area=initial_cavity_area,
        grid_delta=GRID_DELTA,
    )


def run_morphology_only_positive_control():
    """Demonstrate open fill, void-free closure, then positive overburden."""
    ls.setNumThreads(1)
    substrate, fill = _build_morphology_only_via()
    initial = _measure_morphology_only(fill)
    initial_cavity_area = initial["remaining_void_area"]
    bottom_up = MorphologyOnlyVelocity("bottom_up")

    _advect_morphology_only(substrate, fill, bottom_up, INCOMPLETE_FILL_DURATION)
    incomplete = _measure_morphology_only(
        fill,
        initial_cavity_area=initial_cavity_area,
    )

    _advect_morphology_only(substrate, fill, bottom_up, CLOSURE_DURATION)
    closed = _measure_morphology_only(
        fill,
        initial_cavity_area=initial_cavity_area,
    )

    overburden_growth = MorphologyOnlyVelocity("uniform")
    _advect_morphology_only(substrate, fill, overburden_growth, OVERBURDEN_DURATION)
    overburden = _measure_morphology_only(
        fill,
        initial_cavity_area=initial_cavity_area,
    )

    return {
        "scope": MORPHOLOGY_ONLY_SCOPE,
        "initial_cavity_area": initial_cavity_area,
        "stages": {
            "incomplete_fill": incomplete,
            "void_free_closure": closed,
            "positive_overburden": overburden,
        },
    }


def run_morphology_only_failed_fill_control():
    """Demonstrate a top-heavy morphology that seals a measurable void."""
    ls.setNumThreads(1)
    substrate, fill = _build_morphology_only_via()
    initial_cavity_area = _measure_morphology_only(fill)["remaining_void_area"]
    top_heavy = MorphologyOnlyVelocity("top_heavy")
    _advect_morphology_only(
        substrate,
        fill,
        top_heavy,
        FAILED_FILL_DURATION,
        ignore_voids=True,
    )
    return {
        "scope": MORPHOLOGY_ONLY_SCOPE,
        "stage": "top_heavy_pinched_off_void",
        "initial_cavity_area": initial_cavity_area,
        "metrics": _measure_morphology_only(
            fill,
            initial_cavity_area=initial_cavity_area,
        ),
    }
