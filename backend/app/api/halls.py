from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Hall
router = APIRouter(prefix="/halls", tags=["halls"])

def _hall_dict(r: Hall) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "rows": r.rows, "cols": r.cols,
            "min_manhattan": r.min_manhattan, "front_row_rows": r.front_row_rows}

class HallUpdate(BaseModel):
    rows: int | None = None
    cols: int | None = None
    min_manhattan: int | None = None
    front_row_rows: int | None = None

@router.get("")
def list_halls(db: Session = Depends(get_db)):
    return [_hall_dict(r) for r in db.scalars(select(Hall).order_by(Hall.id)).all()]

@router.patch("/{hall_id}")
def update_hall(hall_id: int, body: HallUpdate, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall: raise HTTPException(404, "考室不存在")
    new_rows = body.rows if body.rows is not None else hall.rows
    new_cols = body.cols if body.cols is not None else hall.cols
    new_mm = body.min_manhattan if body.min_manhattan is not None else hall.min_manhattan
    new_frr = body.front_row_rows if body.front_row_rows is not None else hall.front_row_rows
    # 先校验后落库：任何非法都拒绝保存，名额台账 / 最新方案 / 统计三处停在拒绝前
    if new_rows < 1 or new_cols < 1:
        raise HTTPException(422, "考室行列必须为正整数")
    if new_mm < 1:
        raise HTTPException(422, "最小间距必须为正整数")
    if new_frr < 0:
        raise HTTPException(422, "前排行数不能为负")
    if new_frr > new_rows:
        raise HTTPException(422, f"前排行数 {new_frr} 不能大于考室行数 {new_rows}")
    hall.rows, hall.cols, hall.min_manhattan, hall.front_row_rows = new_rows, new_cols, new_mm, new_frr
    db.commit(); db.refresh(hall)
    return _hall_dict(hall)
