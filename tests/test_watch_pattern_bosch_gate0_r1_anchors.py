import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

import foundation_pattern_bosch_gate0_r1 as r1
import watch_pattern_bosch_gate0_r1_anchors as watcher


ROOT = Path(__file__).resolve().parents[1]


class AnchorRowGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = r1.gate0.strict_json_loads(watcher.DEFAULT_MANIFEST.read_text())
        cls.cases = r1.expand_cases(manifest)
        cls.anchors = {
            case["case_id"]: case
            for case in cls.cases
            if case["arm"] == r1.RAY_ANCHOR_ARM
        }

    def _write_rows(self, path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_requires_all_four_expected_case_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            rows_path = Path(temporary) / "rows.jsonl"
            rows = [
                {
                    "case_id": case["case_id"],
                    "case_payload_sha256": case["case_payload_sha256"],
                    "ok": True,
                }
                for case in list(self.anchors.values())[:3]
            ]
            self._write_rows(rows_path, rows)
            result = watcher.check_anchor_rows(
                rows_path, self.cases, self.anchors, audit_fn=lambda *_: ({}, 0)
            )
            self.assertFalse(result["ready"])
            self.assertEqual(result["validated"], 3)

            rows[0]["case_payload_sha256"] = "0" * 64
            self._write_rows(rows_path, rows)
            with self.assertRaisesRegex(watcher.WatcherError, "case hash differs"):
                watcher.check_anchor_rows(
                    rows_path, self.cases, self.anchors, audit_fn=lambda *_: ({}, 0)
                )

    def test_ready_only_after_auditor_accepts_all_four(self):
        with tempfile.TemporaryDirectory() as temporary:
            rows_path = Path(temporary) / "rows.jsonl"
            rows = [
                {
                    "case_id": case["case_id"],
                    "case_payload_sha256": case["case_payload_sha256"],
                    "ok": True,
                }
                for case in self.anchors.values()
            ]
            self._write_rows(rows_path, rows)
            accepted = {
                case["case_id"]: {**case, "ok": True}
                for case in self.anchors.values()
            }
            original_matches = r1.row_matches_case
            original_validate = r1.validate_success_row
            try:
                r1.row_matches_case = lambda row, case: (
                    row["case_id"] == case["case_id"]
                    and row["case_payload_sha256"] == case["case_payload_sha256"]
                )
                r1.validate_success_row = lambda *_: []
                result = watcher.check_anchor_rows(
                    rows_path,
                    self.cases,
                    self.anchors,
                    audit_fn=lambda *_: (accepted, 4),
                )
            finally:
                r1.row_matches_case = original_matches
                r1.validate_success_row = original_validate
            self.assertEqual(
                result,
                {"ready": True, "validated": 4, "reason": "anchors_valid"},
            )


class SupervisorStopTest(unittest.TestCase):
    def test_term_wakes_heartbeat_and_records_interrupted(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime_root = Path(temporary) / "runtime"
            campaign = "watcher-stop-fixture"
            environment = os.environ.copy()
            environment["FROZEN_CAMPAIGN_RUNTIME_ROOT"] = str(runtime_root)
            environment["FROZEN_CAMPAIGN_HEARTBEAT_SECONDS"] = "60"
            process = subprocess.Popen(
                [
                    str(ROOT / "scripts/run-frozen-campaign.sh"),
                    campaign,
                    "--max-restarts",
                    "2",
                    "--",
                    "/bin/zsh",
                    "-c",
                    "sleep 1000",
                ],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            runtime_dir = runtime_root / campaign
            status_path = runtime_dir / "status.json"
            deadline = time.monotonic() + 5
            while not status_path.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(status_path.exists())
            status = json.loads(status_path.read_text())
            terminal = watcher.stop_supervisor(
                runtime_dir,
                status["supervisor_pid"],
                status["child_pid"],
                timeout=5,
            )
            process.wait(timeout=5)
            self.assertEqual(terminal["status"], "interrupted")
            self.assertEqual(terminal["last_exit_code"], 130)
            self.assertFalse((runtime_dir / "active.lock").exists())


class HeartbeatPolicyTest(unittest.TestCase):
    def test_busy_host_heartbeat_window_exceeds_observed_delay(self):
        self.assertGreaterEqual(watcher.MAX_HEARTBEAT_AGE_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
