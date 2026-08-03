# Hybrid Test Execution — Prototype

A small end-to-end demonstration of hybrid test execution: capture a test
from a natural-language intent, run it deterministically, force a UI-drift
failure, watch an LLM agent recover it live, and promote that recovery back
into the deterministic script.

Target application: [demoblaze.com](https://www.demoblaze.com) (a real
public e-commerce demo, not a QA-training site).

LLM: `gemma-4-31b-it` via the Gemini API (free tier). See "Why this model"
below for why this isn't Gemini itself.

See [architecture.md](./architecture.md) for the one-page architecture
diagram and design notes.

## How it works, in one paragraph

An intent like *"open the Laptops category, add a laptop to the cart, and
verify it appears in the cart"* drives an LLM agent that actually explores
demoblaze.com step by step, deciding each action from the page's live
accessibility tree and recording exactly what it did. That recorded
sequence becomes the deterministic script. On replay, each step runs with
no reasoning involved — just the recorded selector. If a step fails
(because we've deliberately staled a selector, simulating drift), the same
agent reasoning function is invoked again, now grounded on the live page,
to recover the step and keep going. What it did is logged as a promotion
candidate for a human to approve or reject.

## Setup (should take under 15 minutes)

Requires Python 3.10+ (uses modern `X | None` type-hint syntax throughout).

```bash
git clone https://github.com/parthdhoot/hybrid-test-exec.git
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
   > Open the Laptops category, view a laptop product, add it to the cart,
   > and verify it appears in the cart
   Click **Generate test**. This takes a bit — the agent is actually
   navigating the live site, taking a snapshot, asking the model for the
   next action, and repeating. When it finishes, the test appears below
   with its concrete recorded steps and its id (with a copy button — you'll
   need it in step 3).

2. **Run it clean.** Click **Run** on the new test. Every step should
   execute deterministically and pass — this is the baseline, no agent
   involvement.

3. **Force a fallback.**
   ```bash
   python scripts/inject_drift.py <test_id>          # lists steps + indices
   python scripts/inject_drift.py <test_id> <index>   # breaks that step's selector
   ```
   This is the one manual edit in the whole flow — it simulates "the UI
   changed since this script was recorded." Everything after this point runs
   for real.

4. **Run it again.** The drifted step now fails deterministically
   (Playwright's own error resolving the selector — no custom detection
   logic needed), the engine hands off to the recovery agent, which reads
   the live page and finds another way to accomplish the same step. The run
   trace shows which mode executed each step and why.

5. **Review the promotion.** The recovered step shows up under "Pending
   promotions." Click **Approve & promote** — the test's canonical script is
   rewritten with the agent's fix. Run the test once more: it's fully
   deterministic again.

## Troubleshooting

- **429 / quota error from the model**: free-tier limits are real but generous
  enough for this workload; wait a minute and retry. If it persists, check
  your key's usage at https://aistudio.google.com/apikey.
- **"Capture produced no usable steps" / a capture request fails outright**:
  the agent stopped rather than save a broken test — that's deliberate (see
  `CaptureFailedError` in `app/execution/capture.py`), not a bug. Try the
  exact intent under "Walking through the demo" above, or a more specific one.

## Why this model

Originally built against Gemini directly. Two real problems showed up
running it live, both worth knowing about if you swap models via
`GEMINI_MODEL` in `.env`:

- Model names go stale fast — `gemini-2.0-flash` and `gemini-2.5-flash` were
  both already past end-of-life for new API keys by the time this was
  built. `gemini-flash-latest`/`gemma-4-31b-it`-style aliases age better
  than pinned version names.
- Gemini's free tier is capped at a small number of requests/day, too tight
  to develop against and demo in the same day. `gemma-4-31b-it` (served
  through the same Gemini API/key) has enough headroom for both.

Gemma also needed a stricter prompt than Gemini did — it would drop the
required `role=`/`text=` selector-engine prefix Playwright needs unless the
prompt gave explicit right/wrong examples (see `app/llm/agent.py`). There's
also a defensive selector-repair fallback in `app/execution/actions.py` for
the same reason: prompt compliance alone isn't a reliable enough contract
across models of different capability, so the executor repairs the common
malformed pattern rather than trusting the model to always get the format
right.

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
- The original target app pick (demo.opencart.com) turned out to be behind
  Cloudflare bot protection by the time this was built — swapped to
  demoblaze.com. A live reminder that depending on someone else's public
  demo site is itself a reliability risk, not just a theoretical one.
