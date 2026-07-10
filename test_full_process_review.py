import review_joint_process_results as review


def row(name, score, passes=6, *, mask_consumed=False, ok=True, replicate=0):
    steps = {
        step: {"target_pass": i < passes, "target_score": score / 6}
        for i, step in enumerate(review.STEPS)
    }
    return {
        "recipe_hash": name,
        "name": name,
        "recipe": {"name": name},
        "replicate": replicate,
        "ok": ok,
        "step_scores": steps,
        "step_pass_count": passes,
        "full_target_pass": passes == 6,
        "total_score": score,
        "cmp_mask_consumed": mask_consumed,
    }


def test_full_traveler_hard_gates_and_stability_precede_raw_score():
    rows = [
        row("stable", 1.0, replicate=0),
        row("stable", 1.2, replicate=1),
        row("unstable", 0.4, replicate=0),
        row("unstable", 0.5, passes=5, replicate=1),
        row("missing", 0.1, passes=5),
        row("mask-consumed", 0.01, mask_consumed=True),
        row("invalid", float("nan")),
        row("runner-error", 0.0, ok=False),
    ]

    ranked = review.aggregate(rows)
    names = [candidate["name"] for candidate in ranked]

    assert names[:3] == ["stable", "unstable", "missing"]
    assert names.index("mask-consumed") > names.index("missing")
    assert names.index("invalid") > names.index("missing")
    assert names[-1] == "runner-error"
    assert review.best_loss(rows) == 1.2


def test_boundary_notes_require_sampled_ranges():
    ranked = [{"recipe": {"cmp_mult": 2.2}}]
    assert review.boundary_notes(ranked) == []
    assert review.boundary_notes(ranked, {"cmp_mult": [1.5, 2.0, 2.2]}) == [
        "top 1 all at high boundary cmp_mult=2.2; expand higher if physically valid"
    ]


if __name__ == "__main__":
    test_full_traveler_hard_gates_and_stability_precede_raw_score()
    test_boundary_notes_require_sampled_ranges()
    print("full-process review checks: PASS")
