"""Executes one concrete action against a live page via Playwright.

Deliberately the one place that touches Playwright's action APIs. Both the
capture-time exploration loop and the deterministic replay engine call this
same function - so "deterministic execution" and "agentic execution" differ
only in *who chose the action*, never in how it's carried out.
"""

from playwright.async_api import Page

ACTION_TIMEOUT_MS = 5000


async def apply_action(
    page: Page,
    action: str,
    selector: str | None,
    value: str | None,
    expected_text: str | None = None,
) -> None:
    if action == "goto":
        if not value:
            raise ValueError("goto requires a value (url)")
        await page.goto(value, timeout=ACTION_TIMEOUT_MS * 3)

    elif action == "click":
        if not selector:
            raise ValueError("click requires a selector")
        await page.click(selector, timeout=ACTION_TIMEOUT_MS)

    elif action == "fill":
        if not selector:
            raise ValueError("fill requires a selector")
        await page.fill(selector, value or "", timeout=ACTION_TIMEOUT_MS)

    elif action == "assert_text":
        if not selector:
            raise ValueError("assert_text requires a selector")
        content = await page.text_content(selector, timeout=ACTION_TIMEOUT_MS)
        if expected_text and expected_text not in (content or ""):
            raise AssertionError(
                f"expected text {expected_text!r} not found in element "
                f"{selector!r} (actual: {content!r})"
            )

    elif action == "done":
        return

    else:
        raise ValueError(f"unknown action type: {action!r}")
