"""Fail closed before executing a script that uses retired phase-one metrics."""

from __future__ import annotations

import os
import sys


WARNING = (
    "Phase-one traveler metrics are under foundation re-audit and are not "
    "authorized for optimization or recipe selection. Use "
    "--allow-legacy-metrics only for explicit historical reproduction."
)


def require_legacy_metric_override(argv=None, environ=None):
    args = sys.argv if argv is None else argv
    environment = os.environ if environ is None else environ
    if environment.get("VIENNAPS_HBM_ALLOW_LEGACY_METRICS") == "1":
        return
    if "--allow-legacy-metrics" in args[1:]:
        args.remove("--allow-legacy-metrics")
        return
    raise SystemExit(WARNING)
