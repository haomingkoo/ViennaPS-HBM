"""Qualify endpoint-aware CMP geometry controls."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

import numpy as np
import viennaps as ps

import traveler_metrics as tm
import tsv_process as tp


CU_SEED_MATERIAL = tp.CU_SEED_MATERIAL
RATE_SEED_FILE = (
    Path(__file__).resolve().parent
    / "ViennaPS/examples/sputterDeposition/rates2D.csv"
)
EVIDENCE_LABEL = "uncalibrated height/selectivity abstraction; not pad-pressure physics"
TOPOGRAPHIES = {
    "flat": {"overburden": 0.150, "boxes": ()},
    "thick_flat": {"overburden": 0.300, "boxes": ()},
    "raised_shoulders": {
        "overburden": 0.150,
        "boxes": ((-0.45, -0.25, 0.050), (0.25, 0.45, 0.050)),
    },
    "raised_plug": {
        "overburden": 0.150,
        "boxes": ((-0.15, 0.15, 0.050),),
    },
    "asymmetric": {
        "overburden": 0.150,
        "boxes": ((0.25, 0.45, 0.050),),
    },
}
QUALIFICATION_NUMERICS = {
    "grid_pair": (0.0025, 0.00125),
    "escalation_grid": 0.000625,
    "time_step_ratios": (0.4999, 0.24995),
    "maximum_profile_spacing_in_grid_cells": 0.5,
    "maximum_endpoint_dose_difference": 0.005,
    "maximum_ctq_difference": 0.005,
    "maximum_plug_area_loss_difference_fraction": 0.02,
    "overpolish_doses": (0.0, 0.0025, 0.005, 0.010, 0.020, 0.030),
}
# program.md requires stop and Cu-plug survival but does not assign allowable
# loss margins.  None is deliberate: qualification remains blocked until the
# research protocol declares these limits; they are not inferred from the grid.
REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS = {
    "minimum_stop_retained_thickness": None,
    "maximum_stop_erosion": None,
    "maximum_plug_height_loss": None,
    "maximum_plug_area_loss_fraction": None,
}


class ExactControlUnavailable(RuntimeError):
    """Raised when the installed Python API cannot represent an exact arm."""


@dataclass(frozen=True)
class HeightMaterialRemovalLaw:
    """Continuous scalar normal-removal law for pre-DOE mechanism checks."""

    stop_y: float
    compliance_length: float
    residual_contact: float
    material_rate_ratios: Mapping[ps.Material, float]
    evidence_label: str = EVIDENCE_LABEL

    def __post_init__(self):
        if self.compliance_length <= 0.0:
            raise ValueError("compliance_length must be positive")
        if not 0.0 <= self.residual_contact <= 1.0:
            raise ValueError("residual_contact must lie in [0, 1]")
        if any(rate < 0.0 for rate in self.material_rate_ratios.values()):
            raise ValueError("material rate ratios must be nonnegative")

    def contact_weight(self, height: float) -> float:
        fraction = np.clip(
            (float(height) - self.stop_y) / self.compliance_length,
            0.0,
            1.0,
        )
        smooth = fraction * fraction * (3.0 - 2.0 * fraction)
        return float(
            self.residual_contact
            + (1.0 - self.residual_contact) * smooth
        )

    def normal_velocity(self, height: float, material: ps.Material) -> float:
        """Return inward scalar velocity; negative values remove material."""
        return -float(self.material_rate_ratios.get(material, 0.0)) * self.contact_weight(
            height
        )


@dataclass
class AnalyticStack:
    geometry: object
    topography: str
    grid_delta: float
    stop_y: float
    cu_top_y: float
    via_radius: float
    via_depth: float
    materials: tuple
    pattern_mask_absent: bool


@dataclass(frozen=True)
class CMPProfile:
    """Dense interfaces plus independent functional-layer evidence."""

    x: np.ndarray
    field_mask: np.ndarray
    via_mask: np.ndarray
    grid_delta: float
    substrate_y: np.ndarray
    stop_top_y: np.ndarray
    barrier_top_y: np.ndarray
    seed_top_y: np.ndarray
    cu_top_y: np.ndarray
    liner_thickness: np.ndarray
    barrier_thickness: np.ndarray
    seed_thickness: np.ndarray
    liner_component_y_spans: tuple[tuple[float, float], ...]
    barrier_component_y_spans: tuple[tuple[float, float], ...]
    seed_component_y_spans: tuple[tuple[float, float], ...]
    cu_component_y_spans: tuple[tuple[float, float], ...]
    liner_region_connectivity: Mapping
    barrier_region_connectivity: Mapping
    seed_region_connectivity: Mapping
    cu_region_connectivity: Mapping
    geometry_invalid_reasons: tuple[str, ...] = ()


def default_candidate_law(stop_y: float) -> HeightMaterialRemovalLaw:
    return HeightMaterialRemovalLaw(
        stop_y=stop_y,
        compliance_length=0.10,
        residual_contact=0.05,
        material_rate_ratios={
            ps.Material.Cu: 1.0,
            CU_SEED_MATERIAL: 1.0,
            ps.Material.TaN: 0.25,
            ps.Material.SiO2: 0.01,
            ps.Material.Si: 0.01,
        },
    )


def _material_tuple(geometry) -> tuple:
    material_map = geometry.getMaterialMap()
    return tuple(
        material_map.getMaterialAtIdx(index)
        for index in range(geometry.getNumberOfLevelSets())
    )


def _surface_height(mesh, x: float) -> float:
    value = tm.surface_height_at_x(mesh["nodes"], mesh["lines"], x)
    if value is None:
        raise ValueError(f"surface has no intersection at x={x}")
    return float(value)


def _add_topography_box(geometry, x_min, x_max, bottom, top):
    box = ps.ls.Domain(geometry.getGrid())
    ps.ls.MakeGeometry(
        box,
        ps.ls.Box([x_min, bottom], [x_max, top]),
    ).apply()
    geometry.applyBooleanOperation(box, ps.ls.BooleanOperationEnum.UNION, False)


def build_analytic_stack(
    topography: str,
    *,
    grid_delta: float = 0.01,
) -> AnalyticStack:
    """Build the full 2D Si/stop/TaN/CuSeed/Cu qualification stack."""
    if topography not in TOPOGRAPHIES:
        raise ValueError(f"unknown CMP topography: {topography}")
    if grid_delta <= 0.0:
        raise ValueError("grid_delta must be positive")

    via_radius = 0.15
    via_depth = 1.25
    geometry = ps.Domain(gridDelta=grid_delta, xExtent=1.0, yExtent=1.5)
    ps.MakeHole(
        domain=geometry,
        holeRadius=via_radius,
        holeDepth=via_depth,
        maskHeight=0.30,
        holeShape=ps.HoleShape.FULL,
    ).apply()
    tp.strip_pattern_mask(geometry)
    for material, thickness in (
        (ps.Material.SiO2, 0.030),
        (ps.Material.TaN, 0.010),
        (CU_SEED_MATERIAL, 0.010),
    ):
        geometry.duplicateTopLevelSet(material)
        ps.Process(
            geometry,
            ps.IsotropicProcess(rate=thickness),
            1.0,
        ).apply()

    meshes = tm.raw_level_set_meshes(geometry)
    stop_y = _surface_height(meshes[1], 0.40)
    design = TOPOGRAPHIES[topography]
    base_top = stop_y + design["overburden"]
    ps.MakePlane(
        domain=geometry,
        height=base_top,
        material=ps.Material.Cu,
        addToExisting=True,
    ).apply()
    for x_min, x_max, relief in design["boxes"]:
        _add_topography_box(
            geometry,
            x_min,
            x_max,
            base_top - 2.0 * grid_delta,
            base_top + relief,
        )

    materials = _material_tuple(geometry)
    expected = (
        ps.Material.Si,
        ps.Material.SiO2,
        ps.Material.TaN,
        CU_SEED_MATERIAL,
        ps.Material.Cu,
    )
    if materials != expected:
        raise ValueError(f"unexpected CMP material stack: {materials}")
    pattern_mask_absent = ps.Material.Mask not in materials
    if not pattern_mask_absent:
        raise ValueError("temporary pattern mask must be absent before CMP")
    cu_nodes = tm.raw_level_set_meshes(geometry)[4]["nodes"]
    return AnalyticStack(
        geometry=geometry,
        topography=topography,
        grid_delta=float(grid_delta),
        stop_y=stop_y,
        cu_top_y=float(np.max(cu_nodes[:, 1])),
        via_radius=via_radius,
        via_depth=via_depth,
        materials=materials,
        pattern_mask_absent=pattern_mask_absent,
    )


def control_capabilities() -> dict:
    exact_combined = hasattr(ps, "HeightMaterialCMP")
    return {
        "planarize_ideal": {
            "exact": True,
            "api": "Planarize",
            "evidence": "ideal geometry and metric control; not CMP physics",
        },
        "cu_only_isotropic": {
            "exact": True,
            "api": "IsotropicProcess.materialRates",
            "evidence": "perfect-selectivity limiting control",
        },
        "uniform_material_selective": {
            "exact": True,
            "api": "IsotropicProcess.materialRates",
            "evidence": "material-selectivity control without topography",
        },
        "height_only_equal_material": {
            "exact": True,
            "api": "CSVFileProcess custom scalar interpolator",
            "evidence": "height control without material selectivity",
        },
        "combined_height_material": {
            "exact": exact_combined,
            "api": (
                "HeightMaterialCMP no-ray scalar velocity field"
                if exact_combined
                else "missing Python binding"
            ),
            "evidence": (
                EVIDENCE_LABEL
                if exact_combined
                else (
                    "CSVFileProcess callbacks receive coordinates but not "
                    "material; IsotropicProcess receives material but not "
                    "coordinates"
                )
            ),
        },
        "destructive_one_rate": {
            "exact": True,
            "api": "IsotropicProcess(rate=-1)",
            "evidence": "destructive negative control",
        },
    }


def make_combined_viennaps_model(law: HeightMaterialRemovalLaw):
    if not hasattr(ps, "HeightMaterialCMP"):
        raise ExactControlUnavailable(
            "The installed Python API exposes coordinate callbacks and material "
            "rates on separate velocity models; it cannot give one scalar "
            "velocity field both coordinate and material without the narrow "
            "HeightMaterialCMP C++ binding."
        )
    params = ps.HeightMaterialCMPParams()
    params.stopHeight = law.stop_y
    params.complianceLength = law.compliance_length
    params.residualContact = law.residual_contact
    params.platedCuRemovalRate = law.material_rate_ratios.get(
        ps.Material.Cu, 0.0
    )
    params.cuSeedMaterial = CU_SEED_MATERIAL
    params.cuSeedRemovalRate = law.material_rate_ratios.get(
        CU_SEED_MATERIAL, 0.0
    )
    params.tantalumNitrideRemovalRate = law.material_rate_ratios.get(
        ps.Material.TaN, 0.0
    )
    params.siliconDioxideRemovalRate = law.material_rate_ratios.get(
        ps.Material.SiO2, 0.0
    )
    params.siliconRemovalRate = law.material_rate_ratios.get(
        ps.Material.Si, 0.0
    )
    return ps.HeightMaterialCMP(params)


def _height_only_model(law: HeightMaterialRemovalLaw):
    model = ps.CSVFileProcess(
        ratesFile=str(RATE_SEED_FILE),
        direction=[0.0, -1.0, 0.0],
        offset=[0.0, 0.0],
        isotropicComponent=1.0,
        directionalComponent=0.0,
        maskMaterials=[],
        calculateVisibility=False,
    )
    model.setCustomInterpolator(
        lambda coordinate: -law.contact_weight(coordinate[1])
    )
    return model


def _uniform_material_model(law: HeightMaterialRemovalLaw):
    return ps.IsotropicProcess(
        materialRates={
            material: -float(rate)
            for material, rate in law.material_rate_ratios.items()
        },
        defaultRate=0.0,
    )


def apply_native_control(
    stack: AnalyticStack,
    arm: str,
    *,
    duration: float | None = None,
    law: HeightMaterialRemovalLaw | None = None,
):
    """Apply an exact native control; never substitute for the combined arm."""
    geometry = stack.geometry
    if arm == "planarize_ideal":
        ps.Planarize(geometry, stack.stop_y).apply()
        return geometry
    if arm == "combined_height_material":
        model = make_combined_viennaps_model(
            law or default_candidate_law(stack.stop_y)
        )
        run_duration = 0.01 if duration is None else duration
    elif arm == "cu_only_isotropic":
        model = ps.IsotropicProcess(
            materialRates={ps.Material.Cu: -1.0},
            defaultRate=0.0,
        )
        run_duration = 0.01 if duration is None else duration
    elif arm == "uniform_material_selective":
        model = _uniform_material_model(
            law or default_candidate_law(stack.stop_y)
        )
        run_duration = 0.01 if duration is None else duration
    elif arm == "height_only_equal_material":
        model = _height_only_model(law or default_candidate_law(stack.stop_y))
        run_duration = 0.01 if duration is None else duration
    elif arm == "destructive_one_rate":
        model = ps.IsotropicProcess(rate=-1.0)
        run_duration = 0.30 if duration is None else duration
    else:
        raise ValueError(f"unknown CMP control arm: {arm}")
    ps.Process(geometry, model, run_duration).apply()
    return geometry


def _sample_interface(mesh, xs, fallback=None):
    values = []
    for index, x in enumerate(xs):
        value = tm.surface_height_at_x(mesh["nodes"], mesh["lines"], x)
        if value is None:
            if fallback is None:
                values.append(np.nan)
            else:
                values.append(float(fallback[index]))
        else:
            values.append(float(value))
    return np.asarray(values, dtype=float)


def _minimum_via_layer_thickness(
    inner_mesh,
    outer_mesh,
    *,
    field_y,
    floor_y,
    via_radius,
    grid_delta,
):
    points = np.asarray(inner_mesh["nodes"], dtype=float)
    if points.ndim != 2 or not len(points):
        return 0.0
    sample_mask = (
        (np.abs(points[:, 0]) <= via_radius + 3.0 * grid_delta)
        & (points[:, 1] >= floor_y - 2.0 * grid_delta)
        & (points[:, 1] <= field_y - 2.0 * grid_delta)
    )
    samples = points[sample_mask]
    if not len(samples):
        return 0.0
    distances = tm.point_to_polyline_distances(
        samples,
        outer_mesh["nodes"],
        outer_mesh["lines"],
    )
    finite = distances[np.isfinite(distances)]
    return float(np.min(finite)) if len(finite) else 0.0


def _material_component_spans(geometry, material):
    mesh = tm.material_region_mesh(geometry, material)
    return tuple(
        (float(summary["bounds_min"][1]), float(summary["bounds_max"][1]))
        for summary in tm.component_summaries(mesh["nodes"], mesh["lines"])
    )


def profile_from_geometry(
    stack: AnalyticStack,
    sample_count: int | None = None,
) -> CMPProfile:
    """Extract dense, material-resolved CMP evidence without legacy CMP scoring."""
    if sample_count is None:
        sample_count = max(
            181,
            int(np.ceil(0.90 / (0.5 * stack.grid_delta))) + 1,
        )
    if sample_count < 41:
        raise ValueError("sample_count must be at least 41")
    meshes = tm.raw_level_set_meshes(stack.geometry)
    if len(meshes) != 5:
        raise ValueError(f"expected five CMP level sets, found {len(meshes)}")
    current_materials = _material_tuple(stack.geometry)
    geometry_invalid_reasons = ()
    if current_materials != stack.materials:
        geometry_invalid_reasons = (
            "unexpected_material_or_level_set_state:"
            f"expected={stack.materials},observed={current_materials}",
        )
    xs = np.linspace(-0.45, 0.45, sample_count)
    substrate = _sample_interface(meshes[0], xs)
    stop = _sample_interface(meshes[1], xs, substrate)
    barrier = _sample_interface(meshes[2], xs, stop)
    seed = _sample_interface(meshes[3], xs, barrier)
    cu = _sample_interface(meshes[4], xs, seed)
    center_floor = tm.surface_height_at_x(
        meshes[0]["nodes"], meshes[0]["lines"], 0.0
    )
    if center_floor is None:
        layer_minimums = (0.0, 0.0, 0.0)
    else:
        layer_minimums = (
            _minimum_via_layer_thickness(
                meshes[0],
                meshes[1],
                field_y=stack.stop_y,
                floor_y=center_floor,
                via_radius=stack.via_radius,
                grid_delta=stack.grid_delta,
            ),
            _minimum_via_layer_thickness(
                meshes[1],
                meshes[2],
                field_y=stack.stop_y,
                floor_y=center_floor,
                via_radius=stack.via_radius,
                grid_delta=stack.grid_delta,
            ),
            _minimum_via_layer_thickness(
                meshes[2],
                meshes[3],
                field_y=stack.stop_y,
                floor_y=center_floor,
                via_radius=stack.via_radius,
                grid_delta=stack.grid_delta,
            ),
        )
    connectivity_floor_ys = (
        stack.stop_y - stack.via_depth,
        stack.stop_y - stack.via_depth + 0.010,
        stack.stop_y - stack.via_depth + 0.020,
        stack.stop_y - stack.via_depth + 0.020,
    )
    connectivities = tuple(
        tm.material_region_connectivity_2d(
            stack.geometry,
            material,
            floor_y=floor_anchor_y,
            field_y=stack.stop_y,
            via_radius=stack.via_radius,
            grid_delta=stack.grid_delta,
            local_minimum_thickness=minimum_thickness,
        )
        for material, floor_anchor_y, minimum_thickness in zip(
            (
                ps.Material.SiO2,
                ps.Material.TaN,
                CU_SEED_MATERIAL,
                ps.Material.Cu,
            ),
            connectivity_floor_ys,
            (*layer_minimums, None),
        )
    )
    return CMPProfile(
        x=xs,
        field_mask=np.abs(xs) >= 0.25,
        via_mask=np.abs(xs) <= 0.12,
        grid_delta=stack.grid_delta,
        substrate_y=substrate,
        stop_top_y=stop,
        barrier_top_y=barrier,
        seed_top_y=seed,
        cu_top_y=cu,
        liner_thickness=np.full_like(xs, layer_minimums[0]),
        barrier_thickness=np.full_like(xs, layer_minimums[1]),
        seed_thickness=np.full_like(xs, layer_minimums[2]),
        liner_component_y_spans=_material_component_spans(
            stack.geometry, ps.Material.SiO2
        ),
        barrier_component_y_spans=_material_component_spans(
            stack.geometry, ps.Material.TaN
        ),
        seed_component_y_spans=_material_component_spans(
            stack.geometry, CU_SEED_MATERIAL
        ),
        cu_component_y_spans=_material_component_spans(
            stack.geometry, ps.Material.Cu
        ),
        liner_region_connectivity=connectivities[0],
        barrier_region_connectivity=connectivities[1],
        seed_region_connectivity=connectivities[2],
        cu_region_connectivity=connectivities[3],
        geometry_invalid_reasons=geometry_invalid_reasons,
    )


def _maximum(values) -> float:
    return float(np.max(np.asarray(values, dtype=float)))


def _minimum(values) -> float:
    return float(np.min(np.asarray(values, dtype=float)))


def _profile_invalid_reasons(profile: CMPProfile) -> list[str]:
    reasons = list(profile.geometry_invalid_reasons)
    interfaces = (
        ("substrate_y", profile.substrate_y),
        ("stop_top_y", profile.stop_top_y),
        ("barrier_top_y", profile.barrier_top_y),
        ("seed_top_y", profile.seed_top_y),
        ("cu_top_y", profile.cu_top_y),
    )
    for name, values in interfaces:
        if not np.all(np.isfinite(values)):
            reasons.append(f"nonfinite_interface:{name}")

    for (lower_name, lower), (upper_name, upper) in zip(
        interfaces, interfaces[1:]
    ):
        if np.any(np.asarray(lower) > np.asarray(upper) + 1e-12):
            reasons.append(f"interface_inversion:{lower_name}>{upper_name}")

    connectivities = {
        "liner": profile.liner_region_connectivity,
        "barrier": profile.barrier_region_connectivity,
        "seed": profile.seed_region_connectivity,
        "plated_cu": profile.cu_region_connectivity,
    }
    component_counts = []
    for material, connectivity in connectivities.items():
        if not isinstance(connectivity, Mapping):
            reasons.append(f"unexpected_connectivity_state:{material}")
            component_counts.append(0)
            continue
        count = connectivity.get("negative_component_count")
        if not isinstance(count, int) or count < 0:
            reasons.append(f"unexpected_connectivity_state:{material}")
            component_counts.append(0)
            continue
        component_counts.append(count)
        if count == 0:
            reasons.append(f"missing_material_component:{material}")
        for required in (
            "resolved",
            "unresolved_reasons",
            "floor_to_both_mouths_connected",
            "detached_fragment_count",
        ):
            if required not in connectivity:
                reasons.append(f"unexpected_connectivity_state:{material}")
                break
    if not any(component_counts):
        reasons.append("empty_or_erased_geometry")
    return reasons


def _connectivity_confirms_region(connectivity: Mapping) -> bool:
    return bool(
        connectivity.get("resolved", False)
        and connectivity.get("floor_to_both_mouths_connected", False)
    )


def _research_survival_thresholds(thresholds):
    values = dict(REQUIRED_RESEARCH_SURVIVAL_THRESHOLDS)
    if thresholds is not None:
        unexpected = set(thresholds) - set(values)
        if unexpected:
            raise ValueError(
                "unknown CMP survival threshold(s): "
                + ", ".join(sorted(unexpected))
            )
        values.update(thresholds)
    for name, value in values.items():
        if value is not None and (not np.isfinite(value) or value < 0.0):
            raise ValueError(f"{name} must be finite and nonnegative")
    missing = tuple(name for name, value in values.items() if value is None)
    return values, missing


def _passes_minimum(value, threshold):
    return None if threshold is None else bool(value >= threshold)


def _passes_maximum(value, threshold):
    return None if threshold is None else bool(value <= threshold)


def evaluate_hard_gates(
    post: CMPProfile,
    pre: CMPProfile,
    *,
    survival_thresholds=None,
) -> dict:
    """Evaluate endpoint, survival, and planarity without a scalar loss."""
    if not np.array_equal(post.x, pre.x):
        raise ValueError("pre/post profiles must share the same sample locations")
    if not np.array_equal(post.field_mask, pre.field_mask):
        raise ValueError("pre/post profiles must share the same field mask")
    if not np.array_equal(post.via_mask, pre.via_mask):
        raise ValueError("pre/post profiles must share the same via mask")
    field = post.field_mask
    via = post.via_mask
    if not np.any(field) or not np.any(via):
        raise ValueError("profile requires nonempty field and via samples")
    expected_shape = post.x.shape
    for profile_name, profile in (("pre", pre), ("post", post)):
        for value_name in (
            "substrate_y",
            "stop_top_y",
            "barrier_top_y",
            "seed_top_y",
            "cu_top_y",
            "liner_thickness",
            "barrier_thickness",
            "seed_thickness",
        ):
            if np.asarray(getattr(profile, value_name)).shape != expected_shape:
                raise ValueError(
                    f"{profile_name}.{value_name} must match profile.x"
                )
    detection_limit = 2.0 * max(post.grid_delta, pre.grid_delta)
    detection_comparison_tolerance = max(1e-12, detection_limit * 1e-9)
    invalid_reasons = tuple(
        [f"pre:{reason}" for reason in _profile_invalid_reasons(pre)]
        + [f"post:{reason}" for reason in _profile_invalid_reasons(post)]
    )
    valid = not invalid_reasons
    thresholds, missing_thresholds = _research_survival_thresholds(
        survival_thresholds
    )

    residual_tan = np.maximum(
        0.0, post.barrier_top_y[field] - post.stop_top_y[field]
    )
    residual_seed = np.maximum(
        0.0, post.seed_top_y[field] - post.barrier_top_y[field]
    )
    residual_plated = np.maximum(
        0.0, post.cu_top_y[field] - post.seed_top_y[field]
    )
    stop_thickness = post.stop_top_y[field] - post.substrate_y[field]
    stop_erosion = np.maximum(
        0.0, pre.stop_top_y[field] - post.stop_top_y[field]
    )
    substrate_loss = np.maximum(
        0.0, pre.substrate_y[field] - post.substrate_y[field]
    )

    field_stop = float(np.mean(post.stop_top_y[field]))
    via_cu = post.cu_top_y[via]
    dish = max(0.0, field_stop - _minimum(via_cu)) if valid else np.nan
    protrusion = max(0.0, _maximum(via_cu) - field_stop) if valid else np.nan

    pre_field_stop = float(np.mean(pre.stop_top_y[field]))
    pre_functional_top = np.minimum(pre.cu_top_y[via], pre_field_stop)
    post_functional_top = np.minimum(post.cu_top_y[via], pre_field_stop)
    plug_height_loss = _maximum(
        np.maximum(0.0, pre_functional_top - post_functional_top)
    )
    pre_seed_floor = _minimum(pre.seed_top_y[via])
    pre_area = float(np.trapezoid(
        np.maximum(0.0, pre_functional_top - pre_seed_floor),
        pre.x[via],
    ))
    post_area = float(np.trapezoid(
        np.maximum(0.0, post_functional_top - pre_seed_floor),
        post.x[via],
    ))
    plug_area_loss = max(0.0, pre_area - post_area)
    plug_area_loss_fraction = (
        plug_area_loss / pre_area if pre_area > 0.0 else np.nan
    )

    plug_connected = bool(
        valid and _connectivity_confirms_region(post.cu_region_connectivity)
    )
    liner_min = _minimum(post.liner_thickness[via])
    barrier_min = _minimum(post.barrier_thickness[via])
    seed_min = _minimum(post.seed_thickness[via])
    field_plated_clear = (
        _maximum(residual_plated)
        <= detection_limit + detection_comparison_tolerance
    )
    field_seed_clear = (
        _maximum(residual_seed)
        <= detection_limit + detection_comparison_tolerance
    )
    field_tan_clear = (
        _maximum(residual_tan)
        <= detection_limit + detection_comparison_tolerance
    )
    plated_cu_first_clear = bool(field_plated_clear)
    all_field_metals_clear = bool(
        field_plated_clear and field_seed_clear and field_tan_clear
    )
    stop_continuous = bool(_minimum(stop_thickness) > detection_limit)
    liner_continuous = bool(
        liner_min > detection_limit
        and _connectivity_confirms_region(post.liner_region_connectivity)
    )
    barrier_continuous = bool(
        barrier_min > detection_limit
        and _connectivity_confirms_region(post.barrier_region_connectivity)
    )
    seed_continuous = bool(
        seed_min > detection_limit
        and _connectivity_confirms_region(post.seed_region_connectivity)
    )
    liner_functional = bool(liner_min >= 0.020)
    barrier_seed_functional = bool(barrier_min + seed_min >= 0.012)
    substrate_survives = bool(_maximum(substrate_loss) <= detection_limit)
    structural_survival = bool(
        valid
        and stop_continuous
        and liner_continuous
        and barrier_continuous
        and seed_continuous
        and liner_functional
        and barrier_seed_functional
        and plug_connected
        and substrate_survives
    )
    stop_retention_within_limit = _passes_minimum(
        _minimum(stop_thickness),
        thresholds["minimum_stop_retained_thickness"],
    )
    stop_erosion_within_limit = _passes_maximum(
        _maximum(stop_erosion),
        thresholds["maximum_stop_erosion"],
    )
    plug_height_loss_within_limit = _passes_maximum(
        plug_height_loss,
        thresholds["maximum_plug_height_loss"],
    )
    plug_area_loss_within_limit = _passes_maximum(
        plug_area_loss_fraction,
        thresholds["maximum_plug_area_loss_fraction"],
    )
    quantitative_survival = bool(
        not missing_thresholds
        and stop_retention_within_limit
        and stop_erosion_within_limit
        and plug_height_loss_within_limit
        and plug_area_loss_within_limit
    )
    survival_hard_gates_pass = bool(
        structural_survival and quantitative_survival
    )
    survival_window_checkpoint_pass = bool(
        all_field_metals_clear and survival_hard_gates_pass
    )
    planarity = bool(
        valid and dish <= detection_limit and protrusion <= detection_limit
    )
    return {
        "valid": valid,
        "invalid_reasons": invalid_reasons,
        "detection_limit": detection_limit,
        "plated_cu_first_clear": plated_cu_first_clear,
        "all_field_metals_clear": all_field_metals_clear,
        "endpoint_reached": all_field_metals_clear,
        "field_plated_cu_clear": field_plated_clear,
        "field_seed_clear": field_seed_clear,
        "field_tan_clear": field_tan_clear,
        "residual_field_plated_cu_max": _maximum(residual_plated),
        "residual_field_seed_max": _maximum(residual_seed),
        "residual_field_tan_max": _maximum(residual_tan),
        "material_region_connectivity": {
            "liner": post.liner_region_connectivity,
            "barrier": post.barrier_region_connectivity,
            "seed": post.seed_region_connectivity,
            "plated_cu": post.cu_region_connectivity,
        },
        "stop_continuous": stop_continuous,
        "stop_minimum_thickness": _minimum(stop_thickness),
        "stop_maximum_erosion": _maximum(stop_erosion),
        "stop_retention_within_research_limit": stop_retention_within_limit,
        "stop_erosion_within_research_limit": stop_erosion_within_limit,
        "liner_continuous": liner_continuous,
        "liner_connectivity_resolved": bool(
            post.liner_region_connectivity.get("resolved", False)
        ),
        "liner_connectivity_unresolved_reasons": tuple(
            post.liner_region_connectivity.get("unresolved_reasons", ())
        ),
        "liner_detached_fragment_count": int(
            post.liner_region_connectivity.get("detached_fragment_count", 0)
        ),
        "liner_minimum_thickness": liner_min,
        "liner_functional_minimum": liner_functional,
        "barrier_continuous": barrier_continuous,
        "barrier_connectivity_resolved": bool(
            post.barrier_region_connectivity.get("resolved", False)
        ),
        "barrier_connectivity_unresolved_reasons": tuple(
            post.barrier_region_connectivity.get("unresolved_reasons", ())
        ),
        "barrier_detached_fragment_count": int(
            post.barrier_region_connectivity.get("detached_fragment_count", 0)
        ),
        "barrier_minimum_thickness": barrier_min,
        "seed_continuous": seed_continuous,
        "seed_connectivity_resolved": bool(
            post.seed_region_connectivity.get("resolved", False)
        ),
        "seed_connectivity_unresolved_reasons": tuple(
            post.seed_region_connectivity.get("unresolved_reasons", ())
        ),
        "seed_detached_fragment_count": int(
            post.seed_region_connectivity.get("detached_fragment_count", 0)
        ),
        "seed_minimum_thickness": seed_min,
        "barrier_seed_functional_minimum": barrier_seed_functional,
        "plug_connected": plug_connected,
        "plug_connectivity_resolved": bool(
            post.cu_region_connectivity.get("resolved", False)
        ),
        "plug_connectivity_unresolved_reasons": tuple(
            post.cu_region_connectivity.get("unresolved_reasons", ())
        ),
        "plug_detached_fragment_count": int(
            post.cu_region_connectivity.get("detached_fragment_count", 0)
        ),
        "plug_height_loss": plug_height_loss,
        "plug_area_loss": plug_area_loss,
        "plug_area_loss_fraction": plug_area_loss_fraction,
        "plug_height_loss_within_research_limit": (
            plug_height_loss_within_limit
        ),
        "plug_area_loss_within_research_limit": plug_area_loss_within_limit,
        "substrate_loss": _maximum(substrate_loss),
        "substrate_survives": substrate_survives,
        "dish": dish,
        "protrusion": protrusion,
        "planarity_within_detection": planarity,
        "research_survival_thresholds": thresholds,
        "research_survival_thresholds_declared": not missing_thresholds,
        "qualification_blocked_reasons": tuple(
            f"required_research_survival_threshold_unset:{name}"
            for name in missing_thresholds
        ),
        "qualification_blocked": bool(missing_thresholds),
        "structural_survival_pass": structural_survival,
        "survival_hard_gates_pass": survival_hard_gates_pass,
        "survival_window_checkpoint_pass": survival_window_checkpoint_pass,
        "all_protected_materials_survive": survival_hard_gates_pass,
        "all_hard_gates_pass": survival_window_checkpoint_pass,
        "all_step_targets_pass": bool(
            survival_window_checkpoint_pass and planarity
        ),
    }


def synthetic_profiles() -> tuple[CMPProfile, CMPProfile]:
    """Return a known pre-CMP state and an ideal endpoint fixture."""
    x = np.linspace(-0.50, 0.50, 201)
    field = np.abs(x) >= 0.25
    via = np.abs(x) <= 0.12
    substrate = np.where(via, -1.25, 0.0)
    stop = substrate + 0.030
    barrier = stop + 0.010
    seed = barrier + 0.010
    pre_cu = np.full_like(x, 0.180)
    seed_floor = float(np.min(seed[via]))
    layer_030 = np.full_like(x, 0.030)
    layer_010 = np.full_like(x, 0.010)

    def connected_region():
        return {
            "resolved": True,
            "unresolved_reasons": (),
            "negative_component_count": 1,
            "floor_to_both_mouths_connected": True,
            "detached_fragment_count": 0,
        }

    pre = CMPProfile(
        x=x,
        field_mask=field,
        via_mask=via,
        grid_delta=0.001,
        substrate_y=substrate,
        stop_top_y=stop,
        barrier_top_y=barrier,
        seed_top_y=seed,
        cu_top_y=pre_cu,
        liner_thickness=layer_030,
        barrier_thickness=layer_010,
        seed_thickness=layer_010,
        liner_component_y_spans=((-1.25, 0.030),),
        barrier_component_y_spans=((seed_floor - 0.020, 0.040),),
        seed_component_y_spans=((seed_floor - 0.010, 0.050),),
        cu_component_y_spans=((seed_floor, 0.180),),
        liner_region_connectivity=connected_region(),
        barrier_region_connectivity=connected_region(),
        seed_region_connectivity=connected_region(),
        cu_region_connectivity=connected_region(),
    )
    endpoint_barrier = barrier.copy()
    endpoint_seed = seed.copy()
    endpoint_cu = np.maximum(seed, 0.030)
    endpoint_barrier[field] = stop[field]
    endpoint_seed[field] = stop[field]
    endpoint_cu[field] = stop[field]
    ideal = replace(
        pre,
        barrier_top_y=endpoint_barrier,
        seed_top_y=endpoint_seed,
        cu_top_y=endpoint_cu,
        cu_component_y_spans=((seed_floor, 0.030),),
    )
    return pre, ideal


def synthetic_failure(profile: CMPProfile, failure: str) -> CMPProfile:
    """Create one isolated known-direction metric failure."""
    if failure == "hidden_residual_island":
        cu = profile.cu_top_y.copy()
        field_indices = np.flatnonzero(profile.field_mask)
        cu[field_indices[len(field_indices) // 3]] += 0.005
        return replace(profile, cu_top_y=cu)
    if failure == "under_clear":
        cu = profile.cu_top_y.copy()
        cu[profile.field_mask] += 0.010
        return replace(profile, cu_top_y=cu)
    if failure == "local_stop_breach":
        stop = profile.stop_top_y.copy()
        field_indices = np.flatnonzero(profile.field_mask)
        index = field_indices[len(field_indices) // 2]
        stop[index] = profile.substrate_y[index]
        return replace(profile, stop_top_y=stop)
    if failure == "disconnected_plug":
        floor = float(np.min(profile.seed_top_y[profile.via_mask]))
        return replace(
            profile,
            cu_component_y_spans=((floor, -0.60), (-0.50, 0.030)),
            cu_region_connectivity={
                "resolved": True,
                "unresolved_reasons": (),
                "negative_component_count": 2,
                "floor_to_both_mouths_connected": False,
                "detached_fragment_count": 0,
            },
        )
    if failure == "dish":
        cu = profile.cu_top_y.copy()
        cu[profile.via_mask] = 0.020
        return replace(profile, cu_top_y=cu)
    if failure == "protrusion":
        cu = profile.cu_top_y.copy()
        cu[profile.via_mask] = 0.040
        return replace(profile, cu_top_y=cu)
    raise ValueError(f"unknown synthetic CMP failure: {failure}")
