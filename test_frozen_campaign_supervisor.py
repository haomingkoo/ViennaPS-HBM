"""Standalone guards for the no-LLM frozen-campaign supervisor."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).parent
RUN = ROOT / "scripts/run-frozen-campaign.sh"
LAUNCH = ROOT / "scripts/launch-frozen-campaign.sh"


def status(root: Path, campaign: str) -> dict:
    return json.loads((root / campaign / "status.json").read_text())


def wait_for(root: Path, campaign: str, expected: str, seconds: float = 8.0):
    deadline = time.monotonic() + seconds
    path = root / campaign / "status.json"
    while time.monotonic() < deadline:
        if path.exists() and status(root, campaign)["status"] == expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"{campaign} did not reach {expected}: {path}")


def main():
    subprocess.run(["zsh", "-n", RUN, LAUNCH], check=True)
    with tempfile.TemporaryDirectory() as temporary:
        runtime = Path(temporary)
        env = {
            **os.environ,
            "FROZEN_CAMPAIGN_RUNTIME_ROOT": str(runtime),
            "FROZEN_CAMPAIGN_HEARTBEAT_SECONDS": "1",
            "FROZEN_CAMPAIGN_RETRY_SECONDS": "0",
        }

        subprocess.run(
            [RUN, "success", "--max-restarts", "0", "--", "/bin/echo", "row"],
            check=True,
            env=env,
        )
        assert status(runtime, "success")["status"] == "complete"
        assert status(runtime, "success")["attempt"] == 1
        assert "row" in (runtime / "success/run.log").read_text()

        failed = subprocess.run(
            [RUN, "failure", "--max-restarts", "1", "--", "/usr/bin/false"],
            env=env,
        )
        assert failed.returncode != 0
        assert status(runtime, "failure")["status"] == "failed"
        assert status(runtime, "failure")["attempt"] == 2

        first = subprocess.Popen(
            [RUN, "locked", "--max-restarts", "0", "--", "/bin/sleep", "2"],
            env=env,
        )
        wait_for(runtime, "locked", "running")
        duplicate = subprocess.run(
            [RUN, "locked", "--max-restarts", "0", "--", "/bin/true"],
            env=env,
        )
        assert duplicate.returncode == 3
        assert first.wait(timeout=6) == 0
        assert status(runtime, "locked")["status"] == "complete"

        tree = subprocess.Popen(
            [
                RUN,
                "interrupt-tree",
                "--max-restarts",
                "0",
                "--",
                "/bin/sh",
                "-c",
                "sleep 20 & wait",
            ],
            env=env,
        )
        wait_for(runtime, "interrupt-tree", "running")
        tree_status = status(runtime, "interrupt-tree")
        direct_child = int(tree_status["child_pid"])
        descendants = []
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and not descendants:
            found = subprocess.run(
                ["pgrep", "-P", str(direct_child)],
                capture_output=True,
                text=True,
                check=False,
            )
            descendants = [
                int(value) for value in found.stdout.split() if value.isdigit()
            ]
            if not descendants:
                time.sleep(0.05)
        assert descendants, "nested campaign child was not observed"
        tree.terminate()
        assert tree.wait(timeout=6) == 130
        wait_for(runtime, "interrupt-tree", "interrupted")
        for pid in [direct_child, *descendants]:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            raise AssertionError(f"interrupted campaign left PID {pid} alive")

        subprocess.run(
            [LAUNCH, "detached", "--max-restarts", "0", "--", "/bin/echo", "detached"],
            check=True,
            env=env,
        )
        wait_for(runtime, "detached", "complete")
        assert "detached" in (runtime / "detached/run.log").read_text()
        assert (runtime / "detached/command.txt").read_text().strip()

    print("frozen campaign supervisor checks: PASS")


if __name__ == "__main__":
    main()
