#!/usr/bin/env python3
"""Run live API pytest suite and write a pass/fail markdown report.

Usage (credentials via env — never argv/logs):
  export MESIGO_API_BASE=http://72.60.210.117:8000
  set -a; source /tmp/mesigo_test_creds.env; set +a
  python scripts/run_live_tests.py --report /path/to/test-report.md
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        required=True,
        help="Markdown report output path",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("MESIGO_API_BASE", "http://127.0.0.1:8000"),
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    api_root = Path(__file__).resolve().parents[1]
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    junit = api_root / ".pytest_live_junit.xml"
    env = os.environ.copy()
    env["MESIGO_API_BASE"] = args.api_base.rstrip("/")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        f"--api-base={env['MESIGO_API_BASE']}",
        f"--junitxml={junit}",
        "-v",
    ]
    if args.quiet:
        cmd.append("-q")

    print("Running:", " ".join(cmd))
    print("API base:", env["MESIGO_API_BASE"])
    print("Owner user set:", bool(env.get("MESIGO_OWNER_USERNAME")))
    # Do not print password presence beyond boolean
    print("Owner password set:", bool(env.get("MESIGO_OWNER_PASSWORD")))

    proc = subprocess.run(cmd, cwd=str(api_root), env=env, capture_output=True, text=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined = (stdout + "\n" + stderr).strip()

    # Parse summary line like "===== 12 passed, 1 failed in 3.2s ====="
    passed = failed = skipped = errors = 0
    import re

    m = re.search(
        r"=+\s*(?:(\d+)\s+failed)?(?:,\s*)?(?:(\d+)\s+passed)?(?:,\s*)?(?:(\d+)\s+skipped)?(?:,\s*)?(?:(\d+)\s+error)?",
        combined,
    )
    # Prefer collecting from pytest terminal summary more carefully
    for line in combined.splitlines()[::-1]:
        if "passed" in line or "failed" in line or "error" in line:
            if line.strip().startswith("="):
                fp = re.search(r"(\d+)\s+failed", line)
                pp = re.search(r"(\d+)\s+passed", line)
                sp = re.search(r"(\d+)\s+skipped", line)
                ep = re.search(r"(\d+)\s+error", line)
                failed = int(fp.group(1)) if fp else 0
                passed = int(pp.group(1)) if pp else 0
                skipped = int(sp.group(1)) if sp else 0
                errors = int(ep.group(1)) if ep else 0
                break

    # Collect per-test outcomes from verbose lines
    rows: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        # e.g. tests/test_live_auth.py::test_health PASSED
        if "::" in line and any(x in line for x in (" PASSED", " FAILED", " SKIPPED", " ERROR")):
            parts = line.strip().split()
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))

    total = passed + failed + skipped + errors
    overall = "PASS" if proc.returncode == 0 and failed == 0 and errors == 0 else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Mesigo API live test report",
        "",
        f"- **Overall:** {overall}",
        f"- **When:** {now}",
        f"- **API base:** `{env['MESIGO_API_BASE']}`",
        f"- **Exit code:** {proc.returncode}",
        f"- **Counts:** {passed} passed · {failed} failed · {skipped} skipped · {errors} errors"
        + (f" · {total} total" if total else ""),
        "",
        "## Results",
        "",
        "| Test | Result |",
        "|---|---|",
    ]
    if rows:
        for name, result in rows:
            mark = "✅" if result == "PASSED" else ("⏭️" if result == "SKIPPED" else "❌")
            lines.append(f"| `{name}` | {mark} {result} |")
    else:
        lines.append("| _(see pytest output)_ | — |")

    lines += [
        "",
        "## Pytest output",
        "",
        "```",
        combined[-12000:],
        "```",
        "",
        "## Notes",
        "",
        "- Credentials loaded from environment only (never written to this report).",
        "- Wizard LLM assertions check masked keys / configured path; secrets are not printed.",
        "",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report: {report_path}")
    print(f"Overall {overall}: {passed} passed, {failed} failed, {skipped} skipped, {errors} errors")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
