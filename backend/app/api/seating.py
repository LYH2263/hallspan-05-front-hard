import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Candidate, FrontRowLedger, Hall, SeatPlan
from app.services.seat_engine import (
    QuotaError, find_violations, place_candidates, plan_to_dict, reconcile_front_row,
)
router = APIRouter(prefix="/seating", tags=["seating"])

@router.post("/run")
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall: raise HTTPException(404, "考室不存在")
    frr = hall.front_row_rows or 0
    if frr < 0 or frr > hall.rows:
        raise HTTPException(409, f"前排行数 {frr} 非法（考室共 {hall.rows} 行），请先修正考室配置")
    cands = [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id,
              "special": c.special}
             for c in db.scalars(select(Candidate).where(Candidate.hall_id == hall_id)).all()]
    # 提交瞬间按当前考室配置重算名额格数，禁止沿用上次排座缓存的名额
    try:
        assigns, unplaced = place_candidates(hall.rows, hall.cols, hall.min_manhattan, cands, frr)
    except QuotaError as e:
        # 名额不够：整场失败，不排普通人凑数，不留半张方案或半本台账
        raise HTTPException(409, str(e))
    viols = find_violations(hall.rows, hall.cols, hall.min_manhattan, assigns)
    quota_slots, quota_used, problems = reconcile_front_row(assigns, cands, frr, hall.cols)
    if problems:
        # 排座图 / 名额已耗 / 统计前排占用对不齐：整场失败且不增方案
        raise HTTPException(409, "名额台账对账失败：" + "；".join(problems))
    result = plan_to_dict(assigns, unplaced, viols, hall.rows, hall.cols, frr, quota_slots, quota_used)
    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan,
                      "front_row_rows": frr}
    plan = SeatPlan(hall_id=hall_id, created_at=datetime.utcnow(), result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan)
    if frr > 0:
        # 方案与名额台账同一事务：要么同成功，要么同失败
        db.flush()
        db.add(FrontRowLedger(hall_id=hall_id, plan_id=plan.id, front_row_rows=frr,
                              quota_slots=quota_slots, quota_used=quota_used))
    db.commit(); db.refresh(plan)
    return {"id": plan.id, **result}

@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    plan = db.scalars(select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())).first()
    if not plan:
        return run_seating(hall_id=hall_id, db=db)
    data = json.loads(plan.result_json)
    return {"id": plan.id, **data}

@router.get("/ledger")
def ledger(hall_id: int = 1, db: Session = Depends(get_db)):
    """名额台账：历史行钉死生成当时的名额数字，只追加、不回刷。"""
    rows = db.scalars(select(FrontRowLedger).where(FrontRowLedger.hall_id == hall_id)
                      .order_by(FrontRowLedger.id.desc())).all()
    return [{"id": r.id, "plan_id": r.plan_id, "front_row_rows": r.front_row_rows,
             "quota_slots": r.quota_slots, "quota_used": r.quota_used,
             "created_at": r.created_at.isoformat()} for r in rows]

@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id, "violations": data.get("violations", []), "unplaced": data.get("unplaced", [])}

@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id, **data.get("stats", {})}
