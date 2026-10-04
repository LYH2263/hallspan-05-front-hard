"""Exam seating: min Manhattan distance; same paper_id cannot be 4-neighbor adjacent.

前排名额账（front_row_rows > 0 时启用）：
- 名额区为第 0..front_row_rows-1 行，提交排座的瞬间按 行数×列数 重算名额格数；
- 特殊考生（special）只能消耗名额格，且先于普通人落座；
- 普通人不得占用名额格凑满，只坐名额区之外；
- 特殊考生落不下名额区 → QuotaError，整场失败，不留半张方案。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class SeatAssign:
    candidate_id: int
    name: str
    ticket_no: str
    paper_id: int
    row: int
    col: int
    special: bool = False

@dataclass
class Violation:
    kind: str
    a_id: int
    b_id: int
    detail: str

class QuotaError(Exception):
    """名额账保不住：特殊考生无法全部落入名额区。整场排座必须失败回滚。"""

def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def neighbors4(r: int, c: int, rows: int, cols: int) -> list[tuple[int, int]]:
    out = []
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((nr, nc))
    return out

def _try_place(cand: dict, occupied: dict[tuple[int, int], SeatAssign],
               rows: int, cols: int, min_dist: int,
               row_lo: int, row_hi: int) -> SeatAssign | None:
    """Greedy: scan seats row-major within [row_lo, row_hi); accept if manhattan >= min_dist
    to all placed AND no same paper 4-neigh. Returns the assignment or None."""
    for r in range(row_lo, row_hi):
        for c in range(cols):
            if (r, c) in occupied:
                continue
            ok = True
            for pos, other in occupied.items():
                if manhattan((r, c), pos) < min_dist:
                    ok = False
                    break
                if other.paper_id == cand["paper_id"] and (r, c) in neighbors4(pos[0], pos[1], rows, cols):
                    ok = False
                    break
            if not ok:
                continue
            # also check 4-neigh same paper against current neighbors
            for nr, nc in neighbors4(r, c, rows, cols):
                if (nr, nc) in occupied and occupied[(nr, nc)].paper_id == cand["paper_id"]:
                    ok = False
                    break
            if not ok:
                continue
            assign = SeatAssign(cand["id"], cand["name"], cand["ticket_no"], cand["paper_id"],
                                r, c, bool(cand.get("special")))
            occupied[(r, c)] = assign
            return assign
    return None

def place_candidates(rows: int, cols: int, min_dist: int, candidates: list[dict],
                     front_row_rows: int = 0) -> tuple[list[SeatAssign], list[dict]]:
    """front_row_rows <= 0：关闭名额账，退回现网行为（全员同规则）。
    front_row_rows > 0：特殊考生先落名额区，普通人只落名额区外；
    特殊考生落不下即抛 QuotaError —— 「保住名额账」与「先排普通人」互斥。"""
    occupied: dict[tuple[int, int], SeatAssign] = {}
    unplaced: list[dict] = []
    if front_row_rows > 0:
        quota_hi = min(front_row_rows, rows)
        specials = [c for c in candidates if c.get("special")]
        normals = [c for c in candidates if not c.get("special")]
        for cand in specials:
            if _try_place(cand, occupied, rows, cols, min_dist, 0, quota_hi) is None:
                raise QuotaError(
                    f"前排名额不足：特殊考生 {cand['name']}({cand['ticket_no']}) 无法落入前 {front_row_rows} 行名额区")
        for cand in normals:
            if _try_place(cand, occupied, rows, cols, min_dist, quota_hi, rows) is None:
                unplaced.append(cand)
    else:
        for cand in candidates:
            if _try_place(cand, occupied, rows, cols, min_dist, 0, rows) is None:
                unplaced.append(cand)
    return list(occupied.values()), unplaced

def reconcile_front_row(assigns: list[SeatAssign], candidates: list[dict],
                        front_row_rows: int, cols: int) -> tuple[int, int, list[str]]:
    """对账：排座图、名额已耗、特殊考生落座数必须同一套数。
    返回 (quota_slots, quota_used, problems)；problems 非空即对不齐，整场不得入库。"""
    if front_row_rows <= 0:
        return 0, 0, []
    quota_slots = front_row_rows * cols
    special_ids = {c["id"] for c in candidates if c.get("special")}
    front_occupants = [a for a in assigns if a.row < front_row_rows]
    quota_used = len(front_occupants)
    problems: list[str] = []
    normals_in_front = [a for a in front_occupants if a.candidate_id not in special_ids]
    if normals_in_front:
        problems.append(f"{len(normals_in_front)} 名普通考生占用名额格")
    seated_specials = [a for a in assigns if a.candidate_id in special_ids]
    if any(a.row >= front_row_rows for a in seated_specials):
        problems.append("特殊考生落在名额区之外")
    if len(seated_specials) != len(special_ids):
        problems.append(f"特殊考生落座 {len(seated_specials)}/{len(special_ids)}，名额账对不齐")
    if quota_used != len(seated_specials):
        problems.append(f"前排占用 {quota_used} 与特殊考生落座 {len(seated_specials)} 不一致")
    if quota_used > quota_slots:
        problems.append(f"名额已耗 {quota_used} 超过名额格 {quota_slots}")
    return quota_slots, quota_used, problems

def find_violations(rows: int, cols: int, min_dist: int, assigns: list[SeatAssign]) -> list[Violation]:
    viols: list[Violation] = []
    for i, a in enumerate(assigns):
        for b in assigns[i + 1:]:
            d = manhattan((a.row, a.col), (b.row, b.col))
            if d < min_dist:
                viols.append(Violation("distance", a.candidate_id, b.candidate_id,
                                       f"曼哈顿距离 {d} < 最小要求 {min_dist}"))
            if a.paper_id == b.paper_id and (b.row, b.col) in neighbors4(a.row, a.col, rows, cols):
                viols.append(Violation("same_paper_adjacent", a.candidate_id, b.candidate_id,
                                       f"同试卷套 {a.paper_id} 四邻相邻"))
    return viols

def plan_to_dict(assigns: list[SeatAssign], unplaced: list[dict], viols: list[Violation],
                 rows: int, cols: int, front_row_rows: int = 0,
                 quota_slots: int = 0, quota_used: int = 0) -> dict:
    return {
        "rows": rows,
        "cols": cols,
        "front_row_rows": front_row_rows,
        "quota": {
            "front_row_rows": front_row_rows,
            "quota_slots": quota_slots,
            "quota_used": quota_used,
        },
        "assignments": [asdict(a) for a in assigns],
        "unplaced": unplaced,
        "violations": [asdict(v) for v in viols],
        "stats": {
            "seated": len(assigns),
            "unplaced": len(unplaced),
            "violations": len(viols),
            "capacity": rows * cols,
            "front_row_rows": front_row_rows,
            "quota_slots": quota_slots,
            "front_row_occupied": quota_used,
        },
    }
