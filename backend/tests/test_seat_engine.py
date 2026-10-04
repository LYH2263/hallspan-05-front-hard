import pytest

from app.services.seat_engine import (
    QuotaError, SeatAssign, find_violations, manhattan, place_candidates, reconcile_front_row,
)

def test_manhattan():
    assert manhattan((0, 0), (2, 1)) == 3

def test_min_distance_placement():
    cands = [{"id": i, "name": f"C{i}", "ticket_no": f"T{i}", "paper_id": 1 + (i % 2)} for i in range(4)]
    assigns, unplaced = place_candidates(4, 4, 2, cands)
    assert len(assigns) + len(unplaced) == 4
    for i, a in enumerate(assigns):
        for b in assigns[i+1:]:
            assert manhattan((a.row, a.col), (b.row, b.col)) >= 2

def test_same_paper_not_adjacent_in_result():
    # Force two same paper — engine should avoid 4-neigh
    cands = [
        {"id": 1, "name": "A", "ticket_no": "T1", "paper_id": 1},
        {"id": 2, "name": "B", "ticket_no": "T2", "paper_id": 1},
        {"id": 3, "name": "C", "ticket_no": "T3", "paper_id": 2},
    ]
    assigns, _ = place_candidates(3, 3, 1, cands)
    viols = find_violations(3, 3, 1, assigns)
    assert not any(v.kind == "same_paper_adjacent" for v in viols)

def test_violation_detection():
    assigns = [
        SeatAssign(1, "A", "T1", 1, 0, 0),
        SeatAssign(2, "B", "T2", 1, 0, 1),
    ]
    viols = find_violations(2, 2, 2, assigns)
    kinds = {v.kind for v in viols}
    assert "distance" in kinds
    assert "same_paper_adjacent" in kinds

def _cand(i: int, special: bool = False, papers: int = 3) -> dict:
    return {"id": i, "name": f"C{i}", "ticket_no": f"T{i}",
            "paper_id": 1 + (i % papers), "special": special}

def test_quota_two_specials_land_in_row_zero():
    # 种子场景：两名特殊考生 + 前排行数 1 → 两人都落第 0 行，名额已耗与图一致
    cands = [_cand(i, special=i < 2) for i in range(12)]
    assigns, _ = place_candidates(5, 6, 2, cands, front_row_rows=1)
    front = [a for a in assigns if a.row == 0]
    assert {a.candidate_id for a in front} == {0, 1}
    assert all(a.row >= 1 for a in assigns if a.candidate_id not in (0, 1))
    slots, used, problems = reconcile_front_row(assigns, cands, 1, 6)
    assert problems == []
    assert slots == 6
    assert used == len(front) == 2

def test_quota_normals_never_fill_leftover_quota_slots():
    # 名额格有剩、普通人排不下：普通人进未排，也不许占名额格凑满
    cands = [_cand(0, special=True, papers=1)] + [_cand(i, papers=1) for i in range(1, 9)]
    for i, c in enumerate(cands):
        c["paper_id"] = 10 + i  # 排除同卷相邻干扰，只考名额规则
    assigns, unplaced = place_candidates(3, 3, 1, cands, front_row_rows=1)
    front = [a for a in assigns if a.row == 0]
    assert len(front) == 1 and front[0].candidate_id == 0
    assert len(unplaced) == 2  # 名额区外 6 格坐 8 个普通人，余 2 人未排
    assert all(a.row >= 1 for a in assigns if a.candidate_id != 0)
    slots, used, problems = reconcile_front_row(assigns, cands, 1, 3)
    assert problems == []
    assert (slots, used) == (3, 1)

def test_quota_insufficient_fails_instead_of_normal_first():
    # 名额不够：抛 QuotaError 整场失败，禁止先排普通人再把特殊考生丢进未排
    cands = [_cand(i, special=i < 3, papers=1) for i in range(5)]
    for i, c in enumerate(cands):
        c["paper_id"] = 10 + i
    with pytest.raises(QuotaError):
        place_candidates(2, 4, 2, cands, front_row_rows=1)  # 第 0 行间距 2 最多坐 2 人 < 3 名特殊

def test_quota_zero_falls_back_to_current_behavior():
    # 前排行数 0 = 关闭名额账：特殊标记不影响排座，不抛名额错
    cands = [_cand(i, special=i < 3) for i in range(6)]
    assigns, unplaced = place_candidates(2, 4, 2, cands, front_row_rows=0)
    assert len(assigns) + len(unplaced) == 6
    slots, used, problems = reconcile_front_row(assigns, cands, 0, 4)
    assert (slots, used, problems) == (0, 0, [])

def test_reconcile_rejects_normal_in_front_row():
    assigns = [SeatAssign(1, "A", "T1", 1, 0, 0, True),
               SeatAssign(2, "B", "T2", 2, 0, 2, False)]
    cands = [{"id": 1, "special": True}, {"id": 2, "special": False}]
    _, _, problems = reconcile_front_row(assigns, cands, 1, 6)
    assert any("普通考生" in p for p in problems)

def test_reconcile_rejects_special_outside_quota_zone():
    assigns = [SeatAssign(1, "A", "T1", 1, 2, 0, True)]
    cands = [{"id": 1, "special": True}]
    _, _, problems = reconcile_front_row(assigns, cands, 1, 6)
    assert problems
