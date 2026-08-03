from fastapi import APIRouter, HTTPException

from app import db
from app.execution.engine import run_test
from app.models import RunTestRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("")
async def create_run(payload: RunTestRequest):
    if db.get_test(payload.test_id) is None:
        raise HTTPException(status_code=404, detail="test not found")
    run_id = await run_test(payload.test_id)
    return db.get_run(run_id)


@router.get("")
def list_runs():
    return db.list_runs()


@router.get("/{run_id}")
def get_run(run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run
