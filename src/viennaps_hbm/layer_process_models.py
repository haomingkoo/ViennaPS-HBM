"""Directional film deposition used for barrier and seed."""

import math

import viennaps as ps


def deposit_directional_fraction(
    domain,
    material,
    *,
    field_dose,
    isotropic_fraction,
    direction=(0.0, -1.0, 0.0),
):
    """Split one field dose into directional and all-angle growth."""
    field_dose = float(field_dose)
    isotropic_fraction = float(isotropic_fraction)
    if not math.isfinite(field_dose) or field_dose <= 0.0:
        raise ValueError("field_dose must be finite and positive")
    if not math.isfinite(isotropic_fraction) or not 0.0 <= isotropic_fraction <= 1.0:
        raise ValueError("isotropic_fraction must be in [0, 1]")
    direction = tuple(float(value) for value in direction)
    magnitude = math.sqrt(sum(value * value for value in direction))
    if len(direction) != 3 or not math.isclose(magnitude, 1.0, abs_tol=1e-12):
        raise ValueError("direction must be a three-component unit vector")

    domain.duplicateTopLevelSet(material)
    model = ps.DirectionalProcess(
        direction=direction,
        directionalVelocity=field_dose * (1.0 - isotropic_fraction),
        isotropicVelocity=field_dose * isotropic_fraction,
    )
    ps.Process(domain, model, 1.0).apply()
