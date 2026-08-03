# Hybrid Test Execution — Prototype

A small end-to-end demonstration of hybrid test execution: capture a test
from a natural-language intent, run it deterministically, force a UI-drift
failure, watch an LLM agent recover it live, and promote that recovery back
into the deterministic script.

Target application: [demo.opencart.com](https://demo.opencart.com) (a real
public e-commerce platform demo, not a QA-training site).

See [architecture.md](./architecture.md) for the one-page architecture
diagram and design notes.

## How it works, in one paragraph

An intent like *"log in as a returning customer and check the order
history"* drives an LLM agent that actually explores demo.opencart.com step
by step, deciding each action from the page's live accessibility tree and
recording exactly what it did. That recorded sequence becomes the
deterministic script. On replay, each step runs with no reasoning involved —
just the recorded selector. If a step fails (because we've deliberately
staled a selector, simulating drift), the same agent reasoning function is
invoked again, now grounded on the live page, to recover the step and keep
going. What it did is logged as a promotion candidate for a human to
approve or reject.

## Setup (should take under 15 minutes)

```bash
git clone <this-repo-url>
cd hybrid-test-exec
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY` — get a free key (no credit card) at
https://aistudio.google.com/apikey.

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Walking through the demo

1. **Capture a test.** In the "Capture a test from intent" box, enter
   something like:
   > Log in with a demo account and view the order history page
   Click **Generate test**. This takes a bit — the agent is actually
   navigating the live site, taking a snapshot, asking Gemini for the next
   action, and repeating. When it finishes, the test appears below with its
   concrete recorded steps.

2. **Run it clean.** Click **Run** on the new test. Every step should
   execute deterministically and pass — this is the baseline, no agent
   involvement.

3. **Force a fallback.** Copy the test's id (shown in the browser's network
   tab, or list it via the API: `curl localhost:8000/api/tests`), then run:
   ```bash
   python scripts/inject_drift.py <test_id>          # lists steps + indices
   python scripts/inject_drift.py <test_id> <index>   # breaks that step's selector
   ```
   This is the one manual edit in the whole flow — it simulates "the UI
   changed since this script was recorded." Everything after this point runs
   for real.

4. **Run it again.** The drifted step now fails deterministically
   (Playwright's own `TimeoutError` — no custom detection logic needed), the
   engine hands off to the recovery agent, which reads the live page and
   finds another way to accomplish the same step. The run trace shows which
   mode executed each step and why.

5. **Review the promotion.** The recovered step shows up under "Pending
   promotions." Click **Approve & promote** — the test's canonical script is
   rewritten with the agent's fix. Run the test once more: it's fully
   deterministic again.

## Notes on scope

- One target app, one test, one engineered failure, one promotion — per the
  assignment's own scope guidance, this is a prototype proving the
  architecture is honest, not a polished product.
- No WebSocket/live-streaming run view: a run blocks until finished and
  returns its full trace in one response. Simpler, and honest about being a
  synchronous demo rather than faking real-time UI.
- SQLite, accessed synchronously — negligible cost at this scale, avoids
  pulling in an async driver for no real benefit.
- A fresh Playwright browser context is launched per run rather than reusing
  a pooled session — slower per run, avoids stale-state bugs.
