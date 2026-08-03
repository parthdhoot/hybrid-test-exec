"""The single reasoning primitive shared by two different callers:

1. Capture-time (app/execution/capture.py) uses it to explore the real
   target app and author a concrete, deterministic step list from a
   natural-language intent.
2. Runtime recovery (app/execution/engine.py) uses it when a deterministic
   step fails, to recover the same step's intent against the live page.

Same function, same prompt shape, same output contract, two call sites.
That's a deliberate architectural choice: "agentic execution" isn't a
separate code path bolted on for fallback, it's the same capability the
system already needed to author tests in the first place.
"""

from app.llm.client import generate_structured
from app.models import AgentAction

_SYSTEM_PREAMBLE = """You are a browser test automation agent. You control a real \
web browser one action at a time. You are given:
- GOAL: the natural-language intent the test is trying to accomplish
- PAGE SNAPSHOT: an accessibility-tree view of what's currently on screen \
(role, accessible name, and value of each visible element)
- HISTORY: the actions already taken so far in this run

Decide the SINGLE next action that moves toward the goal. Do not plan multiple \
steps ahead - one decision at a time, based only on what's visible now.

Rules for the `selector` field:
- The snapshot does not expose CSS ids or classes, only roles and accessible names.
- Prefer `text=<exact visible text>` matching text you can see in the snapshot \
(e.g. `text=Login`), or `role=<role>[name="<accessible name>"]` when a role is clearer.
- Never invent a selector for something not present in the snapshot.

Action types:
- goto: navigate to a URL (value = the URL)
- click: click an element (selector required)
- fill: type into an input (selector + value required)
- assert_text: confirm an element contains expected text (selector + expected_text required)
- done: the goal is already fully satisfied by the current page state - stop here

Always fill in `reasoning` with one concise sentence explaining the decision.
"""


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(none yet - this is the first action)"
    lines = []
    for i, item in enumerate(history, start=1):
        lines.append(
            f"{i}. {item.get('action')} selector={item.get('selector')!r} "
            f"value={item.get('value')!r} -> {item.get('outcome', 'ok')}"
        )
    return "\n".join(lines)


def decide_next_action(
    goal: str,
    snapshot_text: str,
    history: list[dict],
    failure_note: str | None = None,
) -> AgentAction:
    recovery_block = ""
    if failure_note:
        recovery_block = (
            f"\nIMPORTANT: A previously working deterministic script just failed "
            f"this step: {failure_note}\n"
            "The application's UI has likely changed since that script was written. "
            "Find a different way to accomplish the same step intent using what's "
            "actually on the page now.\n"
        )

    prompt = (
        f"{_SYSTEM_PREAMBLE}\n"
        f"GOAL: {goal}\n"
        f"{recovery_block}\n"
        f"HISTORY:\n{_format_history(history)}\n\n"
        f"PAGE SNAPSHOT:\n{snapshot_text}\n\n"
        "Respond with the single next action."
    )
    return generate_structured(prompt, AgentAction)
