"""Turns a natural-language intent into a concrete, grounded step list.

This is an agentic exploration pass: it actually drives a browser against
the real target app and lets the LLM decide each action from what's really
on screen, recording every action it takes as a step. The resulting step
list is what gets replayed deterministically afterward.

This is why selectors in the generated test are trustworthy - they were
never hallucinated from the model's training data, they were resolved
against the live page.
"""
import sys
from app.config import MAX_CAPTURE_STEPS, TARGET_APP_URL
from app.db import new_id
from app.execution.actions import apply_action
from app.execution.browser import browser_page, get_snapshot_text
from app.llm.agent import decide_next_action

class CaptureFailedError(RuntimeError):
    """The exploration loop couldn't complete. Never return a partial step
    list on failure - a test that silently stops mid-exploration is worse
    than no test, because it looks identical to one that succeeded."""

async def capture_test_from_intent(intent: str) -> list[dict]:
    steps: list[dict] = []
    history: list[dict] = []

    async with browser_page() as page:
        await apply_action(page, "goto", None, TARGET_APP_URL)
        steps.append(
            {
                "step_uuid": new_id(),
                "action": "goto",
                "selector": None,
                "value": TARGET_APP_URL,
                "expected_outcome": "Target application loads",
            }
        )
        history.append(
            {"action": "goto", "selector": None, "value": TARGET_APP_URL, "outcome": "ok"}
        )

        for _ in range(MAX_CAPTURE_STEPS):
            snapshot = await get_snapshot_text(page)
            decision = decide_next_action(goal=intent, snapshot_text=snapshot, history=history)

            if decision.action == "done":
                break

            try:
                await apply_action(
                    page, decision.action, decision.selector, decision.value, decision.expected_text
                )
            except Exception as exc:
                # The exploring agent itself got stuck - stop rather than
                # record a step that didn't actually happen.
                print(f"[capture] step failed: {decision.action} {decision.selector!r} -> {exc!r}", file=sys.stderr)
                raise CaptureFailedError(
                    f"The agent tried to {decision.action} '{decision.selector}' while exploring "
                    f"the app, and it failed: {exc}. Capture stopped rather than saving an "
                    f"incomplete test."
                ) from exc
            steps.append(
                {
                    "step_uuid": new_id(),
                    "action": decision.action,
                    "selector": decision.selector,
                    "value": decision.value,
                    "expected_outcome": decision.expected_text or decision.reasoning,
                }
            )
            history.append(
                {
                    "action": decision.action,
                    "selector": decision.selector,
                    "value": decision.value,
                    "outcome": "ok",
                }
            )

    return steps
