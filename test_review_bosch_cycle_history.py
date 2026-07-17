"""Recovery selection guard for the Bosch cycle-history review."""

import review_bosch_cycle_history as review


def test_recovered_seed_replaces_failed_attempt_without_hiding_it():
    failed = {"case_id": "failed", "rng_seed": 7, "ok": False, "error": "disk"}
    recovered = {"case_id": "recovered", "rng_seed": 7, "ok": True}
    other = {"case_id": "other", "rng_seed": 8, "ok": True}
    valid, errors, superseded = review.select_logical_rows(
        [failed, recovered, other]
    )
    assert [row["case_id"] for row in valid] == ["recovered", "other"]
    assert errors == [failed]
    assert superseded == []


if __name__ == "__main__":
    test_recovered_seed_replaces_failed_attempt_without_hiding_it()
    print("Bosch recovery review checks: PASS")
