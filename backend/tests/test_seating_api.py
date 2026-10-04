"""端到端：前排名额台账与座位方案必须同成功同失败。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import FrontRowLedger, SeatPlan


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:  # 进入 lifespan：ensure_schema + 种子（两名特殊考生，前排行数 1）
        yield c


def _counts() -> tuple[int, int]:
    """(方案条数, 台账行数) —— 失败场景两者都不许增加。"""
    db = SessionLocal()
    try:
        plans = db.scalar(select(func.count()).select_from(SeatPlan)) or 0
        ledgers = db.scalar(select(func.count()).select_from(FrontRowLedger)) or 0
        return plans, ledgers
    finally:
        db.close()


def _special_ids(client: TestClient) -> set[int]:
    return {c["id"] for c in client.get("/api/candidates").json() if c["special"]}


def test_seed_two_specials_both_in_row_zero_and_quota_matches(client):
    assert _counts() == (0, 0)
    resp = client.post("/api/seating/run", params={"hall_id": 1})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 两名特殊考生都必须落在第 0 行
    specials = _special_ids(client)
    assert len(specials) == 2
    front = [a for a in data["assignments"] if a["row"] < 1]
    assert {a["candidate_id"] for a in front} == specials
    # 排座图、名额已耗、统计前排占用同一套数
    assert data["quota"] == {"front_row_rows": 1, "quota_slots": 6, "quota_used": 2}
    stats = client.get("/api/seating/stats", params={"hall_id": 1}).json()
    assert stats["front_row_occupied"] == len(front) == data["quota"]["quota_used"]
    assert stats["quota_slots"] == 6
    # 台账与方案同事务入库，且钉死当次数字
    ledger = client.get("/api/seating/ledger", params={"hall_id": 1}).json()
    assert len(ledger) == 1
    assert ledger[0]["plan_id"] == data["id"]
    assert (ledger[0]["quota_slots"], ledger[0]["quota_used"]) == (6, 2)
    assert _counts() == (1, 1)


def test_quota_insufficient_fails_without_half_plan_or_half_ledger(client):
    assert client.post("/api/seating/run", params={"hall_id": 1}).status_code == 200
    assert _counts() == (1, 1)
    latest_before = client.get("/api/seating/latest", params={"hall_id": 1}).json()
    # 把 6 名普通考生改标为特殊 → 共 8 名特殊，第 0 行间距 2 最多坐 3 人
    normal_ids = [c["id"] for c in client.get("/api/candidates").json() if not c["special"]]
    for cid in normal_ids[:6]:
        assert client.patch(f"/api/candidates/{cid}", json={"special": True}).status_code == 200
    resp = client.post("/api/seating/run", params={"hall_id": 1})
    assert resp.status_code == 409
    # 不增方案、不增台账；最新方案仍是改标记前那一套数字
    assert _counts() == (1, 1)
    latest_after = client.get("/api/seating/latest", params={"hall_id": 1}).json()
    assert latest_after["id"] == latest_before["id"]
    assert latest_after["quota"]["quota_used"] == latest_before["quota"]["quota_used"] == 2


def test_invalid_front_row_rows_rejected_and_state_untouched(client):
    assert client.post("/api/seating/run", params={"hall_id": 1}).status_code == 200
    assert _counts() == (1, 1)
    stats_before = client.get("/api/seating/stats", params={"hall_id": 1}).json()
    # 行数为负、大于考室行数：都拒绝保存
    assert client.patch("/api/halls/1", json={"front_row_rows": -1}).status_code == 422
    assert client.patch("/api/halls/1", json={"front_row_rows": 6}).status_code == 422
    # 三处停在拒绝前：考室配置、方案/台账条数、统计都不变
    hall = client.get("/api/halls").json()[0]
    assert hall["front_row_rows"] == 1
    assert _counts() == (1, 1)
    assert client.get("/api/seating/stats", params={"hall_id": 1}).json() == stats_before


def test_change_front_row_rows_then_run_writes_new_ledger_keeps_history(client):
    first_id = client.post("/api/seating/run", params={"hall_id": 1}).json()["id"]
    assert client.patch("/api/halls/1", json={"front_row_rows": 2}).status_code == 200
    resp = client.post("/api/seating/run", params={"hall_id": 1})
    assert resp.status_code == 200, resp.text
    # 提交瞬间重算名额：2 行 × 6 列 = 12 格，而不是沿用上次缓存的 6
    assert resp.json()["quota"]["quota_slots"] == 12
    ledger = client.get("/api/seating/ledger", params={"hall_id": 1}).json()
    assert _counts() == (2, 2)
    # 历史方案钉死生成当时的名额数字，禁止回刷
    old = [r for r in ledger if r["plan_id"] == first_id]
    assert old and (old[0]["quota_slots"], old[0]["quota_used"]) == (6, 2)


def test_zero_front_row_rows_closes_ledger_and_reverts(client):
    assert client.patch("/api/halls/1", json={"front_row_rows": 0}).status_code == 200
    resp = client.post("/api/seating/run", params={"hall_id": 1})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 关闭名额账、退回现网：名额字段全 0，不写台账
    assert data["quota"] == {"front_row_rows": 0, "quota_slots": 0, "quota_used": 0}
    stats = client.get("/api/seating/stats", params={"hall_id": 1}).json()
    assert stats["front_row_occupied"] == 0
    assert stats["seated"] + stats["unplaced"] == 12
    assert _counts() == (1, 0)


def test_mark_toggle_keeps_history_until_next_run(client):
    assert client.post("/api/seating/run", params={"hall_id": 1}).status_code == 200
    # 改标记：最新方案与台账不动（同成功）；历史数字禁止回刷
    normal = next(c for c in client.get("/api/candidates").json() if not c["special"])
    assert client.patch(f"/api/candidates/{normal['id']}", json={"special": True}).status_code == 200
    latest = client.get("/api/seating/latest", params={"hall_id": 1}).json()
    assert latest["quota"]["quota_used"] == 2
    # 下一次排座提交才按新标记重算：3 名特殊考生都落第 0 行
    resp = client.post("/api/seating/run", params={"hall_id": 1})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    specials = _special_ids(client)
    assert len(specials) == 3
    front = [a for a in data["assignments"] if a["row"] < 1]
    assert {a["candidate_id"] for a in front} == specials
    assert data["quota"]["quota_used"] == 3
    ledger = client.get("/api/seating/ledger", params={"hall_id": 1}).json()
    assert [r["quota_used"] for r in sorted(ledger, key=lambda r: r["id"])] == [2, 3]
    assert _counts() == (2, 2)
