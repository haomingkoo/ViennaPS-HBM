"""Stop Gate-0 R1 after its four validated 2000-ray anchors finish."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import foundation_pattern_bosch_gate0_r1 as r1


DEFAULT_MANIFEST = Path(
    ".scratch/full-traveler-autoresearch/"
    "foundation_pattern_bosch_gate0_r1_manifest.json"
)
DEFAULT_ROWS = Path(
    "autoresearch-results/restart_audit/pattern_bosch_gate0_r1_rows.jsonl"
)
DEFAULT_RUNTIME = Path(
    "autoresearch-results/runtime/pattern-bosch-gate0-r1-final-20260713"
)
MAX_HEARTBEAT_AGE_SECONDS = 900


class WatcherError(RuntimeError):
    pass


def load_contract(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = r1.gate0.strict_json_loads(manifest_path.read_text())
    cases = r1.expand_cases(manifest)
    errors = r1.validate_manifest(manifest, cases)
    if errors:
        raise WatcherError("frozen R1 contract is invalid: " + "; ".join(errors))
    anchors = {
        case["case_id"]: case
        for case in cases
        if case["arm"] == r1.RAY_ANCHOR_ARM
    }
    seeds = {case["rng_seed"] for case in anchors.values()}
    if len(anchors) != 4 or seeds != set(r1.EXPECTED_SEEDS):
        raise WatcherError("frozen R1 contract does not contain four anchor cases")
    if any(
        case["numerics"]["rays_per_point"] != 2000
        or case["role"] != "ray_anchor"
        for case in anchors.values()
    ):
        raise WatcherError("frozen R1 anchor role or ray count differs")
    return cases, anchors


def _parse_stable_rows(rows_path):
    rows_path = Path(rows_path)
    before = rows_path.read_bytes() if rows_path.exists() else b""
    if before and not before.endswith(b"\n"):
        return None, before
    try:
        rows = [
            r1.gate0.strict_json_loads(line)
            for line in before.decode().splitlines()
            if line
        ]
    except Exception as error:
        after = rows_path.read_bytes() if rows_path.exists() else b""
        if after != before or (after and not after.endswith(b"\n")):
            return None, after
        raise WatcherError(f"R1 row ledger is malformed: {error}") from error
    return rows, before


def check_anchor_rows(rows_path, cases, anchors, *, audit_fn=None):
    rows_path = Path(rows_path)
    rows, snapshot = _parse_stable_rows(rows_path)
    if rows is None:
        return {"ready": False, "validated": 0, "reason": "row_write_in_progress"}

    found = {}
    for row in rows:
        current_id = row.get("case_id")
        if current_id not in anchors or row.get("ok") is not True:
            continue
        case = anchors[current_id]
        if row.get("case_payload_sha256") != case["case_payload_sha256"]:
            raise WatcherError(f"anchor case hash differs: {current_id}")
        if current_id in found:
            raise WatcherError(f"duplicate successful anchor row: {current_id}")
        found[current_id] = row

    if len(found) < len(anchors):
        return {
            "ready": False,
            "validated": len(found),
            "reason": "anchors_pending",
        }

    audit = audit_fn or r1.audit_existing_rows
    try:
        successes, _ = audit(rows_path, cases)
    except Exception as error:
        after = rows_path.read_bytes() if rows_path.exists() else b""
        if after != snapshot:
            return {
                "ready": False,
                "validated": len(found),
                "reason": "row_ledger_changed_during_audit",
            }
        raise WatcherError(f"R1 row audit failed: {error}") from error
    after = rows_path.read_bytes() if rows_path.exists() else b""
    if after != snapshot:
        return {
            "ready": False,
            "validated": len(found),
            "reason": "row_ledger_changed_during_audit",
        }

    for current_id, case in anchors.items():
        row = successes.get(current_id)
        if row is None:
            raise WatcherError(f"auditor did not accept anchor: {current_id}")
        if not r1.row_matches_case(row, case):
            raise WatcherError(f"audited anchor payload differs: {current_id}")
        errors = r1.validate_success_row(row, case, rows_path)
        if errors:
            raise WatcherError(
                f"anchor validation failed {current_id}: " + "; ".join(errors)
            )
    return {"ready": True, "validated": 4, "reason": "anchors_valid"}


def _process_field(pid, field):
    result = subprocess.run(
        ["ps", "-o", f"{field}=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    state = _process_field(pid, "state")
    return bool(state and not state.startswith("Z"))


def _status(runtime_dir):
    path = Path(runtime_dir) / "status.json"
    try:
        return r1.gate0.strict_json_loads(path.read_text())
    except Exception as error:
        raise WatcherError(f"runtime status is invalid: {error}") from error


def validate_runtime(runtime_dir, manifest_path, rows_path):
    runtime_dir = Path(runtime_dir)
    status = _status(runtime_dir)
    if status.get("campaign") != runtime_dir.name:
        raise WatcherError("runtime campaign name differs")
    if status.get("status") != "running":
        raise WatcherError(f"R1 is not running: {status.get('status')}")
    supervisor = status.get("supervisor_pid")
    child = status.get("child_pid")
    if not isinstance(supervisor, int) or not isinstance(child, int):
        raise WatcherError("runtime PIDs are not integers")
    if not _is_alive(supervisor) or not _is_alive(child):
        raise WatcherError("runtime PID is not alive")

    supervisor_command = _process_field(supervisor, "command") or ""
    child_command = _process_field(child, "command") or ""
    child_parent = _process_field(child, "ppid")
    supervisor_group = _process_field(supervisor, "pgid")
    child_group = _process_field(child, "pgid")
    if "run-frozen-campaign.sh" not in supervisor_command:
        raise WatcherError("supervisor PID command differs")
    if runtime_dir.name not in supervisor_command:
        raise WatcherError("supervisor command campaign differs")
    if "foundation_pattern_bosch_gate0_r1.py" not in child_command:
        raise WatcherError("child PID command differs")
    if str(manifest_path) not in child_command or str(rows_path) not in child_command:
        raise WatcherError("child command paths differ")
    if child_parent is None or int(child_parent) != supervisor:
        raise WatcherError("runtime child is not owned by the supervisor")
    if (
        supervisor_group is None
        or child_group is None
        or int(supervisor_group) != int(child_group)
    ):
        raise WatcherError("runtime process groups differ")

    lock_path = runtime_dir / "active.lock" / "supervisor.pid"
    if not lock_path.is_file() or lock_path.read_text().strip() != str(supervisor):
        raise WatcherError("runtime lock does not match the supervisor")
    command_text = (runtime_dir / "command.txt").read_text()
    for required in (
        "foundation_pattern_bosch_gate0_r1.py",
        str(manifest_path),
        str(rows_path),
        "--workers 2",
    ):
        if required not in command_text:
            raise WatcherError(f"frozen runtime command lacks: {required}")

    heartbeat = status.get("heartbeat")
    try:
        heartbeat_time = dt.datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
    except Exception as error:
        raise WatcherError("runtime heartbeat is invalid") from error
    age = (dt.datetime.now(dt.UTC) - heartbeat_time).total_seconds()
    if age < -5 or age > MAX_HEARTBEAT_AGE_SECONDS:
        raise WatcherError(f"runtime heartbeat is stale: {age:.1f}s")
    return status


def _direct_children(pid):
    result = subprocess.run(
        ["pgrep", "-P", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise WatcherError("could not inspect supervisor children")
    return [int(value) for value in result.stdout.split()]


def stop_supervisor(runtime_dir, supervisor, child, *, timeout=10.0):
    if not _is_alive(supervisor) or not _is_alive(child):
        raise WatcherError("refusing to signal a dead runtime PID")
    os.kill(supervisor, signal.SIGTERM)

    deadline = time.monotonic() + timeout
    while _is_alive(supervisor) and time.monotonic() < deadline:
        for current in _direct_children(supervisor):
            if current == child:
                continue
            command = _process_field(current, "command") or ""
            if command == "sleep" or command.startswith("sleep "):
                try:
                    os.kill(current, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        time.sleep(0.05)
    if _is_alive(supervisor):
        raise WatcherError("supervisor did not stop after its TERM trap was woken")

    deadline = time.monotonic() + timeout
    while _is_alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    if _is_alive(child):
        raise WatcherError("R1 child remained alive after supervisor shutdown")

    status = _status(runtime_dir)
    if status.get("status") != "interrupted" or status.get("last_exit_code") != 130:
        raise WatcherError("supervisor did not record an interrupted terminal state")
    if (Path(runtime_dir) / "active.lock").exists():
        raise WatcherError("runtime lock remained after supervisor shutdown")
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument(
        "--arm",
        action="store_true",
        help="allow the watcher to signal the validated R1 supervisor",
    )
    args = parser.parse_args()
    if not 0.1 <= args.poll_seconds <= 30.0:
        parser.error("--poll-seconds must be between 0.1 and 30")

    cases, anchors = load_contract(args.manifest)
    status = validate_runtime(args.runtime, args.manifest, args.rows)
    readiness = check_anchor_rows(args.rows, cases, anchors)
    print(json.dumps({
        "armed": args.arm,
        "runtime_status": status["status"],
        **readiness,
    }, sort_keys=True), flush=True)
    if not args.arm:
        return

    while not readiness["ready"]:
        time.sleep(args.poll_seconds)
        status = validate_runtime(args.runtime, args.manifest, args.rows)
        readiness = check_anchor_rows(args.rows, cases, anchors)
        print(json.dumps({
            "armed": True,
            "runtime_status": status["status"],
            **readiness,
        }, sort_keys=True), flush=True)

    status = validate_runtime(args.runtime, args.manifest, args.rows)
    terminal = stop_supervisor(
        args.runtime,
        status["supervisor_pid"],
        status["child_pid"],
    )
    final_readiness = check_anchor_rows(args.rows, cases, anchors)
    if not final_readiness["ready"]:
        raise WatcherError("validated anchors changed during shutdown")
    print(json.dumps({
        "armed": True,
        "runtime_status": terminal["status"],
        "stopped": True,
        **final_readiness,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
