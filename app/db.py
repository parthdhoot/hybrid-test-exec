import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS tests (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    intent_text TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL REFERENCES tests(id),
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS run_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    step_uuid TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    action TEXT NOT NULL,
    selector TEXT,
    value TEXT,
    expected_outcome TEXT,
    mode_used TEXT NOT NULL,
    status TEXT NOT NULL,
    agent_reasoning TEXT,
    agent_new_selector TEXT,
    customer_explanation TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotion_candidates (
    id TEXT PRIMARY KEY,
    run_step_id TEXT NOT NULL REFERENCES run_steps(id),
    test_id TEXT NOT NULL REFERENCES tests(id),
    step_uuid TEXT NOT NULL,
    proposed_action TEXT NOT NULL,
    proposed_selector TEXT,
    proposed_value TEXT,
    reasoning TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---- tests ----

def insert_test(name: str, intent_text: str, steps: list[dict]) -> dict:
    test_id = new_id()
    row = {
        "id": test_id,
        "name": name,
        "intent_text": intent_text,
        "steps_json": json.dumps(steps),
        "created_at": now(),
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tests (id, name, intent_text, steps_json, created_at) "
            "VALUES (:id, :name, :intent_text, :steps_json, :created_at)",
            row,
        )
    return get_test(test_id)


def get_test(test_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["steps"] = json.loads(d.pop("steps_json"))
    return d


def list_tests() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tests ORDER BY created_at DESC").fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["steps"] = json.loads(d.pop("steps_json"))
        out.append(d)
    return out


def update_test_step(test_id: str, step_uuid: str, action: str, selector: str | None, value: str | None) -> dict:
    """Rewrite one step of a test's canonical script (used on promotion approval)."""
    test = get_test(test_id)
    if test is None:
        raise ValueError(f"test {test_id} not found")
    steps = test["steps"]
    for step in steps:
        if step["step_uuid"] == step_uuid:
            step["action"] = action
            step["selector"] = selector
            step["value"] = value
            break
    with get_conn() as conn:
        conn.execute(
            "UPDATE tests SET steps_json = ? WHERE id = ?",
            (json.dumps(steps), test_id),
        )
    return get_test(test_id)


# ---- runs ----

def insert_run(test_id: str) -> str:
    run_id = new_id()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO runs (id, test_id, status, started_at, finished_at) "
            "VALUES (?, ?, 'running', ?, NULL)",
            (run_id, test_id, now()),
        )
    return run_id


def finish_run(run_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
            (status, now(), run_id),
        )


def get_run(run_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        steps = conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY step_index ASC",
            (run_id,),
        ).fetchall()
    d = dict(row)
    d["steps"] = [dict(s) for s in steps]
    return d


def list_runs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC").fetchall()
    return [dict(r) for r in rows]


def insert_run_step(
    run_id: str,
    step_uuid: str,
    step_index: int,
    action: str,
    selector: str | None,
    value: str | None,
    expected_outcome: str | None,
    mode_used: str,
    status: str,
    customer_explanation: str,
    agent_reasoning: str | None = None,
    agent_new_selector: str | None = None,
) -> str:
    run_step_id = new_id()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO run_steps (
                id, run_id, step_uuid, step_index, action, selector, value,
                expected_outcome, mode_used, status, agent_reasoning,
                agent_new_selector, customer_explanation, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_step_id, run_id, step_uuid, step_index, action, selector, value,
                expected_outcome, mode_used, status, agent_reasoning,
                agent_new_selector, customer_explanation, now(),
            ),
        )
    return run_step_id


# ---- promotion candidates ----

def insert_promotion_candidate(
    run_step_id: str,
    test_id: str,
    step_uuid: str,
    proposed_action: str,
    proposed_selector: str | None,
    proposed_value: str | None,
    reasoning: str,
) -> str:
    candidate_id = new_id()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO promotion_candidates (
                id, run_step_id, test_id, step_uuid, proposed_action,
                proposed_selector, proposed_value, reasoning, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                candidate_id, run_step_id, test_id, step_uuid, proposed_action,
                proposed_selector, proposed_value, reasoning, now(),
            ),
        )
    return candidate_id


def list_promotion_candidates(status: str | None = None) -> list[dict]:
    # Joined with tests/run_steps so the UI can show *which* test and *which*
    # step a candidate belongs to - without this, multiple pending candidates
    # (e.g. several drifted steps in one suite, or drifts across several
    # tests) are indistinguishable except by their proposed selector.
    query = """
        SELECT pc.*, t.name AS test_name, rs.step_index AS step_index
        FROM promotion_candidates pc
        JOIN tests t ON pc.test_id = t.id
        JOIN run_steps rs ON pc.run_step_id = rs.id
    """
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                query + " WHERE pc.status = ? ORDER BY pc.created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(query + " ORDER BY pc.created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_promotion_candidate(candidate_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM promotion_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
    return dict(row) if row else None


def set_promotion_status(candidate_id: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE promotion_candidates SET status = ? WHERE id = ?",
            (status, candidate_id),
        )
