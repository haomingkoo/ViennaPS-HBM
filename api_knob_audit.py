"""Capture the actual wrapper and ViennaPS API parameter surfaces as JSON."""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import viennaps as ps

import layer_process_models as layer_models
import tsv_process as tp


LOCAL_FUNCTIONS = (
    "make_initial_geometry",
    "strip_pattern_mask",
    "bosch_etch",
    "deposit_conformal",
    "cu_fill",
    "cmp_planarize",
)

API_CLASSES = (
    "MakeHole",
    "SingleParticleProcess",
    "MultiParticleProcess",
    "DirectionalProcess",
    "IsotropicProcess",
    "Planarize",
    "CSVFileProcess",
    "TEOSDeposition",
    "TEOSPECVD",
    "SingleParticleALD",
    "NeutralTransport",
    "Process",
)

PARAMETER_OBJECTS = (
    "RayTracingParameters",
    "AdvectionParameters",
    "CoverageParameters",
    "AtomicLayerProcessParameters",
    "SingleParticleALDParams",
    "SurfaceDiffusionParameters",
    "NeutralTransportParameters",
)


def json_value(value):
    if value is inspect.Parameter.empty:
        return {"required": True}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def local_signature(name):
    signature = inspect.signature(getattr(tp, name))
    return {
        parameter: {
            "default": json_value(item.default),
            "kind": str(item.kind),
        }
        for parameter, item in signature.parameters.items()
    }


def parameter_defaults(name):
    instance = getattr(ps, name)()
    result = {}
    for attribute in dir(instance):
        if attribute.startswith("_"):
            continue
        value = getattr(instance, attribute)
        if callable(value):
            continue
        result[attribute] = json_value(value)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("autoresearch-results/restart_audit/api_signature_audit.json"),
    )
    args = parser.parse_args()

    data = {
        "viennaps_version": ps.version,
        "dimension": 2,
        "local_functions": {
            name: local_signature(name) for name in LOCAL_FUNCTIONS
        },
        "layer_model_functions": {
            name: {
                parameter: {
                    "default": json_value(item.default),
                    "kind": str(item.kind),
                }
                for parameter, item in inspect.signature(
                    getattr(layer_models, name)
                ).parameters.items()
            }
            for name in (
                "ray_parameters",
                "deposit_single_particle",
                "deposit_teos",
                "directional_components",
                "deposit_directional_fraction",
                "deposit_isotropic_control",
            )
        },
        "viennaps_constructors": {
            name: getattr(getattr(ps, name), "__init__").__doc__
            for name in API_CLASSES
        },
        "viennaps_methods": {
            "MultiParticleProcess.addNeutralParticle": ps.MultiParticleProcess.addNeutralParticle.__doc__,
            "MultiParticleProcess.addIonParticle": ps.MultiParticleProcess.addIonParticle.__doc__,
            "MultiParticleProcess.setRateFunction": ps.MultiParticleProcess.setRateFunction.__doc__,
            "CSVFileProcess.setCustomInterpolator": ps.CSVFileProcess.setCustomInterpolator.__doc__,
        },
        "parameter_defaults": {
            name: parameter_defaults(name) for name in PARAMETER_OBJECTS
        },
        "explicit_materials": {
            "liner": str(ps.Material.SiO2),
            "barrier": str(ps.Material.TaN),
            "cu_seed": str(tp.CU_SEED_MATERIAL),
            "plated_cu": str(ps.Material.Cu),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
