from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Candidate
router = APIRouter(prefix="/candidates", tags=["candidates"])

def _cand_dict(r: Candidate) -> dict:
    return {"id": r.id, "hall_id": r.hall_id, "name": r.name, "ticket_no": r.ticket_no,
            "paper_id": r.paper_id, "special": r.special}

class CandidateUpdate(BaseModel):
    special: bool | None = None

@router.get("")
def list_candidates(db: Session = Depends(get_db)):
    return [_cand_dict(r) for r in db.scalars(select(Candidate).order_by(Candidate.id)).all()]

@router.patch("/{candidate_id}")
def update_candidate(candidate_id: int, body: CandidateUpdate, db: Session = Depends(get_db)):
    cand = db.get(Candidate, candidate_id)
    if not cand: raise HTTPException(404, "考生不存在")
    # 改标记只动考生行：历史方案与台账钉死不动，下一次排座提交才重算
    if body.special is not None:
        cand.special = body.special
    db.commit(); db.refresh(cand)
    return _cand_dict(cand)
