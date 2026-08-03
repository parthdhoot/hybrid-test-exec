"""Runs a test's canonical step list against the target app.

Each step is attempted deterministically first (the stored selector, no
reasoning). Playwright's own failure - a TimeoutError when the selector
doesn't resolve - is the "UI drift detected" signal; no separate detection
logic is needed. On failure, the same decide_next_action() used at capture
time is invoked again, now framed as a recovery: given the step's intent and
the live page, find a different way to do it. What it did is recorded as a
promotion candidate for a human to review.
"""

from app import db
from app.config import MAX_RECOVERY_ATTEMPTS_PER_STEP
from app.execution.actions import apply_action
from app.execution.browser import browser_page, get_snapshot_text
from app.llm.agent import decide_next_action


def _explain_deterministic(step: dict) -> str:
    action = step["action"]
    if action == "goto":
        return f"Navigated to {step['value']}, as scripted."
    if action == "click":
        return f"Clicked '{step['selector']}', as scripted."
    if action == "fill":
        return f"Filled '{step['selector']}' with the expected value, as scripted."
    if action == "assert_text":
        return f"Confirmed '{step['selector']}' contains the expected text, as scripted."
    return f"Executed {action} as scripted."


def _explain_recovery(step: dict, failure: Exception, decision) -> str:
    return (
        f"The scripted step (\"{step['action']} {step['selector']}\") failed: "
        f"{failure}. This looks like the page changed since the script was "
        f"written. The system found an alternative on the current page - "
        f"{decision.action} '{decision.selector}' - and continued. "
        f"Reasoning: {decision.reasoning}"
    )


async def run_test(test_id: str) -> str:
    test = db.get_test(test_id)
    if test is None:
        raise ValueError(f"test {test_id} not found")

    run_id = db.insert_run(test_id)
    history: list[dict] = []
    any_failed = False
    any_recovered = False

    async with browser_page() as page:
        for index, step in enumerate(test["steps"]):
            step_uuid = step["step_uuid"]
            failure: Exception | None = None
            try:
                await apply_action(page, step["action"], step["selector"], step["value"])
                db.insert_run_step(
                    run_id=run_id,
                    step_uuid=step_uuid,
                    step_index=index,
                    action=step["action"],
                    selector=step["selector"],
                    value=step["value"],
                    expected_outcome=step.get("expected_outcome"),
                    mode_used="deterministic",
                    status="pass",
                    customer_explanation=_explain_deterministic(step),
                )
                history.append({**step, "outcome": "ok"})
                continue
            except Exception as exc:
                failure = exc  # exception objects don't survive past the except block, so stash it

            # --- recovery ---
            recovered = False
            last_error: Exception | None = failure
            for _attempt in range(MAX_RECOVERY_ATTEMPTS_PER_STEP):
                snapshot = await get_snapshot_text(page)
                decision = decide_next_action(
                    goal=step.get("expected_outcome") or f"{step['action']} {step['selector']}",
                    snapshot_text=snapshot,
                    history=history,
                    failure_note=str(last_error),
                )
                try:
                    await apply_action(
                        page, decision.action, decision.selector, decision.value, decision.expected_text
                    )
                    recovered = True
                    break
                except Exception as retry_error:
                    last_error = retry_error
                    continue

            if recovered:
                any_recovered = True
                run_step_id = db.insert_run_step(
                    run_id=run_id,
                    step_uuid=step_uuid,
                    step_index=index,
                    action=step["action"],
                    selector=step["selector"],
                    value=step["value"],
                    expected_outcome=step.get("expected_outcome"),
                    mode_used="agentic",
                    status="pass",
                    customer_explanation=_explain_recovery(step, failure, decision),
                    agent_reasoning=decision.reasoning,
                    agent_new_selector=decision.selector,
                )
                db.insert_promotion_candidate(
                    run_step_id=run_step_id,
                    test_id=test_id,
                    step_uuid=step_uuid,
                    proposed_action=decision.action,
                    proposed_selector=decision.selector,
                    proposed_value=decision.value,
                    reasoning=decision.reasoning,
                )
                history.append(
                    {
                        "action": decision.action,
                        "selector": decision.selector,
                        "value": decision.value,
                        "outcome": "recovered",
                    }
                )
            else:
                any_failed = True
                db.insert_run_step(
                    run_id=run_id,
                    step_uuid=step_uuid,
                    step_index=index,
                    action=step["action"],
                    selector=step["selector"],
                    value=step["value"],
                    expected_outcome=step.get("expected_outcome"),
                    mode_used="agentic",
                    status="fail",
                    customer_explanation=(
                        f"The scripted step failed ({failure}), and the recovery "
                        f"attempt(s) also failed ({last_error}). The run was stopped "
                        f"here rather than reporting a false pass."
                    ),
                    agent_reasoning=str(last_error),
                )
                break  # can't meaningfully continue past an unrecovered step

    status = "failed" if any_failed else ("passed_with_recovery" if any_recovered else "passed")
    db.finish_run(run_id, status)
    return run_id
