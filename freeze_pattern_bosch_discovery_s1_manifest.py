"""Fail-closed guard for the superseded Bosch-only S1 study."""

SUPERSEDED_REASON = (
    "the Bosch-only S1 draft is superseded pending the RESEARCH_PLAN_V3.md "
    "screening and downstream-propagation rebuild"
)


def build_manifest(*_args, **_kwargs):
    raise ValueError(SUPERSEDED_REASON)


def main():
    raise SystemExit(SUPERSEDED_REASON)


if __name__ == "__main__":
    main()
