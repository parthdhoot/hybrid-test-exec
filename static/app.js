function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (body && body.detail) || res.statusText;
    throw new Error(detail);
  }
  return body;
}

// ---- tests ----

async function loadTests() {
  const el = document.getElementById("tests-list");
  try {
    const tests = await api("/api/tests");
    if (tests.length === 0) {
      el.innerHTML = '<p class="muted">No tests yet - generate one above.</p>';
      return;
    }
    el.innerHTML = tests.map(renderTestItem).join("");
    tests.forEach((t) => {
      document
        .getElementById(`run-btn-${t.id}`)
        .addEventListener("click", () => runTest(t.id));
    });
  } catch (err) {
    el.innerHTML = `<p class="status error">Failed to load tests: ${escapeHtml(err.message)}</p>`;
  }
}

function renderTestItem(test) {
  const stepsRows = test.steps
    .map(
      (s, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${escapeHtml(s.action)}</td>
        <td>${escapeHtml(s.selector || "")}</td>
        <td>${escapeHtml(s.value || "")}</td>
      </tr>`
    )
    .join("");

  return `
    <div class="test-item">
      <h3>${escapeHtml(test.name)}</h3>
      <p class="muted">${escapeHtml(test.intent_text)}</p>
      <table class="steps-table">
        <thead><tr><th>#</th><th>action</th><th>selector</th><th>value</th></tr></thead>
        <tbody>${stepsRows}</tbody>
      </table>
      <button id="run-btn-${test.id}">Run</button>
    </div>`;
}

document.getElementById("capture-btn").addEventListener("click", async () => {
  const intentInput = document.getElementById("intent-input");
  const statusEl = document.getElementById("capture-status");
  const btn = document.getElementById("capture-btn");
  const intent = intentInput.value.trim();
  if (!intent) return;

  btn.disabled = true;
  statusEl.className = "status";
  statusEl.textContent = "Exploring the target app and generating steps - this can take a bit...";
  try {
    await api("/api/tests", { method: "POST", body: JSON.stringify({ intent }) });
    statusEl.textContent = "Test captured.";
    intentInput.value = "";
    await loadTests();
  } catch (err) {
    statusEl.className = "status error";
    statusEl.textContent = `Failed: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
});

// ---- runs ----

async function runTest(testId) {
  const traceSection = document.getElementById("run-trace-section");
  const summaryEl = document.getElementById("run-summary");
  traceSection.classList.remove("hidden");
  summaryEl.textContent = "Running...";
  document.getElementById("run-steps").innerHTML = "";
  traceSection.scrollIntoView({ behavior: "smooth" });

  try {
    const run = await api("/api/runs", {
      method: "POST",
      body: JSON.stringify({ test_id: testId }),
    });
    renderRun(run);
    await loadPromotions();
  } catch (err) {
    summaryEl.innerHTML = `<p class="status error">Run failed to start: ${escapeHtml(err.message)}</p>`;
  }
}

function renderRun(run) {
  const summaryEl = document.getElementById("run-summary");
  const stepsEl = document.getElementById("run-steps");

  summaryEl.innerHTML = `<span class="badge ${run.status === "failed" ? "fail" : "pass"}">${escapeHtml(
    run.status
  )}</span>`;

  stepsEl.innerHTML = run.steps
    .map((s) => {
      const modeBadge = `<span class="badge ${s.mode_used}">${s.mode_used}</span>`;
      const statusBadge = `<span class="badge ${s.status}">${s.status}</span>`;
      const reasoning = s.agent_reasoning
        ? `<div class="reasoning">Agent reasoning: ${escapeHtml(s.agent_reasoning)}</div>`
        : "";
      return `
        <div class="run-step ${s.mode_used}">
          <div><strong>Step ${s.step_index + 1}</strong> ${modeBadge} ${statusBadge}</div>
          <div class="explanation">${escapeHtml(s.customer_explanation)}</div>
          ${reasoning}
        </div>`;
    })
    .join("");
}

// ---- promotions ----

async function loadPromotions() {
  const el = document.getElementById("promotions-list");
  try {
    const candidates = await api("/api/promotions?status=pending");
    if (candidates.length === 0) {
      el.innerHTML = '<p class="muted">No pending promotions.</p>';
      return;
    }
    el.innerHTML = candidates.map(renderPromotionItem).join("");
    candidates.forEach((c) => {
      document
        .getElementById(`approve-${c.id}`)
        .addEventListener("click", () => decidePromotion(c.id, "approve"));
      document
        .getElementById(`reject-${c.id}`)
        .addEventListener("click", () => decidePromotion(c.id, "reject"));
    });
  } catch (err) {
    el.innerHTML = `<p class="status error">Failed to load promotions: ${escapeHtml(err.message)}</p>`;
  }
}

function renderPromotionItem(c) {
  return `
    <div class="promo-item">
      <h3>${escapeHtml(c.proposed_action)} &rarr; ${escapeHtml(c.proposed_selector || "")}</h3>
      <p class="muted">${escapeHtml(c.reasoning)}</p>
      <button id="approve-${c.id}">Approve &amp; promote</button>
      <button id="reject-${c.id}" class="reject">Reject</button>
    </div>`;
}

async function decidePromotion(id, decision) {
  try {
    await api(`/api/promotions/${id}/${decision}`, { method: "POST" });
    await loadPromotions();
    await loadTests();
  } catch (err) {
    alert(`Failed to ${decision}: ${err.message}`);
  }
}

loadTests();
loadPromotions();
