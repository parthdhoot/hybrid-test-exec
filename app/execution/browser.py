import asyncio
from contextlib import asynccontextmanager

from playwright.async_api import Dialog, Page, async_playwright


@asynccontextmanager
async def browser_page():
    """One fresh browser + context + page per call.

    Slower than a pooled/reused session (~1-2s launch overhead) but avoids an
    entire class of stale-state bugs between runs - the right trade for a
    prototype over a long-lived shared session.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        # Some target apps trigger native JS dialogs (e.g. alert() on "add to
        # cart"). Left unhandled these block headless automation indefinitely.
        # dialog.accept() is itself async, so a plain lambda wouldn't actually
        # await it - schedule it explicitly instead.
        def _auto_accept_dialog(dialog: Dialog) -> None:
            asyncio.ensure_future(dialog.accept())

        page.on("dialog", _auto_accept_dialog)
        try:
            yield page
        finally:
            await context.close()
            await browser.close()


async def get_snapshot_text(page: Page, max_chars: int = 6000) -> str:
    """Render the page's accessibility tree as compact indented text.

    This - not raw HTML - is what the LLM reasons over. It's what a real
    accessibility-based agent perceives, it's far cheaper in tokens than a
    screenshot or full DOM dump, and it naturally excludes non-interactive
    visual noise.
    """
    snapshot = await page.accessibility.snapshot(interesting_only=True)
    lines: list[str] = []

    def walk(node: dict | None, depth: int = 0) -> None:
        if node is None:
            return
        role = node.get("role", "")
        name = node.get("name", "")
        value = node.get("value", "")
        parts = [f"{'  ' * depth}- {role}"]
        if name:
            parts.append(f'"{name}"')
        if value:
            parts.append(f"value={value!r}")
        lines.append(" ".join(parts))
        for child in node.get("children", []) or []:
            walk(child, depth + 1)

    walk(snapshot)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(truncated)"
    return text
