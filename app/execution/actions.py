"""Executes one concrete action against a live page via Playwright.

Deliberately the one place that touches Playwright's action APIs. Both the
capture-time exploration loop and the deterministic replay engine call this
same function - so "deterministic execution" and "agentic execution" differ
only in *who chose the action*, never in how it's carried out.
"""

import re

from playwright.async_api import Page

ACTION_TIMEOUT_MS = 5000

_ENGINE_PREFIXES = ("text=", "role=", "css=", "xpath=", "#", ".")
_BARE_ROLE_ATTR = re.compile(r'^[a-zA-Z][\w-]*\[name="[^"]*"\]$')


def normalize_selector(selector: str | None) -> str | None:
    """Best-effort repair for selectors missing a Playwright engine prefix.

    Prompt instructions alone don't reliably get every model to include the
    `role=`/`text=` prefix (weaker/smaller models especially tend to drop
    it) - this is a defensive net so a plausible-but-malformed selector
    still resolves instead of failing on a technicality.
    """
    if not selector:
        return selector
    s = selector.strip()
    if s.startswith(_ENGINE_PREFIXES):
        return s
    if _BARE_ROLE_ATTR.match(s):
        return f"role={s}"
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        return f"text={s[1:-1]}"
    return s


async def apply_action(
    page: Page,
    action: str,
    selector: str | None,
    value: str | None,
    expected_text: str | None = None,
) -> None:
    selector = normalize_selector(selector)

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

    if action in ("goto", "click"):
        # click() waits for the click itself, not for a navigation - or an
        # async side effect like an add-to-cart request - it might trigger.
        # Without this, the next snapshot/action can run before the page (or
        # the target app's own backend call) has actually settled. Matches
        # ACTION_TIMEOUT_MS rather than using a shorter window, so this wait
        # isn't the tightest constraint in the step - see the note on why 5s
        # specifically in the leadership document. Best-effort: don't fail
        # the step if the page was already settled (e.g. an in-page click
        # with no navigation).
        try:
            await page.wait_for_load_state("networkidle", timeout=ACTION_TIMEOUT_MS)
        except Exception:
            pass
