#!/usr/bin/env python3
"""Run all unit tests and report results.

Runs each test module as a subprocess for isolation, captures output,
and produces a unified summary report.

Usage: python -m tests.run_all  (from project root)
   or: python tests/run_all.py
"""

import os
import sys
import time
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

TEST_MODULES = [
    "tests.test_combat",
    "tests.test_economy",
    "tests.test_npc",
    "tests.test_quests",
    "tests.test_divine",
    "tests.test_world_gen",
    "tests.test_save_load",
]

TIMEOUT = 300  # 5 minutes per module


def run_module(module: str):
    """Run a test module as subprocess. Returns (ok, output, elapsed)."""
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, "-m", module],
            capture_output=True, text=True,
            timeout=TIMEOUT, cwd=ROOT,
            env={**os.environ,
                 'SDL_VIDEODRIVER': 'dummy',
                 'SDL_AUDIODRIVER': 'dummy'},
        )
        elapsed = time.time() - t0
        output = result.stdout + result.stderr
        return result.returncode == 0, output, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return False, f"TIMEOUT after {TIMEOUT}s", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        return False, f"ERROR: {e}", elapsed


def extract_summary(output: str):
    """Extract PASS/FAIL counts from test output."""
    passed = failed = 0
    for line in output.split('\n'):
        line = line.strip()
        if line.startswith('[PASS]'):
            passed += 1
        elif line.startswith('[FAIL]'):
            failed += 1
    return passed, failed


def main():
    print("=" * 70)
    print("AUTONOMOUS WORLD — FULL TEST SUITE")
    print("=" * 70)
    print()

    total_passed = 0
    total_failed = 0
    total_time = 0.0
    module_results = []

    for module in TEST_MODULES:
        short = module.split('.')[-1]
        print(f"Running {short}...", end=" ", flush=True)
        ok, output, elapsed = run_module(module)
        passed, failed = extract_summary(output)
        total_passed += passed
        total_failed += failed
        total_time += elapsed

        status = "OK" if ok else "FAIL"
        print(f"{status} ({passed} passed, {failed} failed, {elapsed:.1f}s)")

        if failed > 0 or not ok:
            # Print failure details
            for line in output.split('\n'):
                if '[FAIL]' in line or 'FAIL:' in line:
                    print(f"    {line.strip()}")

        module_results.append((short, ok, passed, failed, elapsed))

    # Summary
    total = total_passed + total_failed
    print()
    print("=" * 70)
    print(f"TOTAL: {total_passed}/{total} passed, "
          f"{total_failed} failed, {total_time:.1f}s elapsed")
    print("=" * 70)

    for short, ok, passed, failed, elapsed in module_results:
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {short:20s}  {passed:3d} passed  "
              f"{failed:3d} failed  {elapsed:5.1f}s")

    print("=" * 70)
    if total_failed == 0:
        print("All tests passed.")
    else:
        print(f"{total_failed} test(s) FAILED.")

    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
