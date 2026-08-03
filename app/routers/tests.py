from fastapi import APIRouter, HTTPException

from app import db
from app.execution.capture import capture_test_from_intent, CaptureFailedError
from app.models import CreateTestRequest

router = APIRouter(prefix="/api/tests", tags=["tests"])


@router.post("")
async def create_test(payload: CreateTestRequest):
    try:
        steps = await capture_test_from_intent(payload.intent)
    except CaptureFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    
    if len(steps) <= 1:
        raise HTTPException(
            status_code=422,
            detail="Capture produced no usable steps beyond the initial navigation - "
            "try a more specific intent.",
        )
    name = payload.name or payload.intent[:60]
    return db.insert_test(name=name, intent_text=payload.intent, steps=steps)


@router.get("")
def list_tests():
    return db.list_tests()


@router.get("/{test_id}")
def get_test(test_id: str):
    test = db.get_test(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="test not found")
    return test
