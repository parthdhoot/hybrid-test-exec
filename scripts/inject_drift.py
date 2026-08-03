"""Deliberately breaks one step's selector in a captured test, simulating a
UI change that happened after the script was written. This is the one
manual edit in the whole system - everything downstream of it (failure
detection, recovery, promotion) runs for real against the live site.

Usage:
    python scripts/inject_drift.py <test_id> <step_index>

Run `python scripts/inject_drift.py <test_id>` with no step index to list
the test's steps and their indices first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402

DRIFT_SUFFIX = "-drifted-no-longer-exists"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    test_id = sys.argv[1]
    test = db.get_test(test_id)
    if test is None:
        print(f"test {test_id} not found")
        sys.exit(1)

    steps = test["steps"]

    if len(sys.argv) == 2:
        print(f"Steps for test {test_id!r} ({test['name']}):")
        for i, s in enumerate(steps):
            print(f"  [{i}] {s['action']:12s} selector={s['selector']!r} value={s['value']!r}")
        print("\nRe-run with a step index to inject drift into that step's selector.")
        return

    step_index = int(sys.argv[2])
    if step_index < 0 or step_index >= len(steps):
        print(f"step index out of range (0..{len(steps) - 1})")
        sys.exit(1)

    step = steps[step_index]
    if step["action"] not in ("click", "fill", "assert_text"):
        print(f"step {step_index} is a {step['action']!r} step with no selector to break")
        sys.exit(1)

    original = step["selector"]
    drifted = original + DRIFT_SUFFIX
    db.update_test_step(
        test_id=test_id,
        step_uuid=step["step_uuid"],
        action=step["action"],
        selector=drifted,
        value=step["value"],
    )
    print(f"Step {step_index}: selector changed from {original!r} to {drifted!r}.")
    print("The next run of this test will fail this step deterministically and fall back to the agent.")


if __name__ == "__main__":
    main()
