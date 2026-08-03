from fastapi import APIRouter, HTTPException

from app import db

router = APIRouter(prefix="/api/promotions", tags=["promotions"])


@router.get("")
def list_promotions(status: str | None = None):
    return db.list_promotion_candidates(status)


@router.post("/{candidate_id}/approve")
def approve_promotion(candidate_id: str):
    candidate = db.get_promotion_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="promotion candidate not found")
    if candidate["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"candidate already {candidate['status']}")

    updated_test = db.update_test_step(
        test_id=candidate["test_id"],
        step_uuid=candidate["step_uuid"],
        action=candidate["proposed_action"],
        selector=candidate["proposed_selector"],
        value=candidate["proposed_value"],
    )
    db.set_promotion_status(candidate_id, "approved")
    return {"candidate": db.get_promotion_candidate(candidate_id), "test": updated_test}


@router.post("/{candidate_id}/reject")
def reject_promotion(candidate_id: str):
    candidate = db.get_promotion_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="promotion candidate not found")
    if candidate["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"candidate already {candidate['status']}")

    db.set_promotion_status(candidate_id, "rejected")
    return db.get_promotion_candidate(candidate_id)
