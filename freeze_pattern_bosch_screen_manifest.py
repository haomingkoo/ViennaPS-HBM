"""Fail-closed guard for the superseded repeat-heavy screen."""

SUPERSEDED_REASON = (
    "the repeat-heavy 640-case screen is superseded by RESEARCH_PLAN_V3.md; "
    "use broad skew screening, effect review, and downstream propagation"
)


def build_manifest(*_args, **_kwargs):
    raise ValueError(SUPERSEDED_REASON)


def main():
    raise SystemExit(SUPERSEDED_REASON)


if __name__ == "__main__":
    main()
