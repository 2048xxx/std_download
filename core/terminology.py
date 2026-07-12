"""标准术语检索：按术语查国标定义及所属标准。"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from core.term_ai import ai_ready, expand_term_semantics
from paths import SQLITE_PATH, TERMS_DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(TERMS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_ready() -> bool:
    if not TERMS_DB_PATH.is_file():
        return False
    try:
        with _connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM std_term").fetchone()[0]
            return int(n) > 0
    except sqlite3.Error:
        return False


def indexed_count() -> int:
    if not TERMS_DB_PATH.is_file():
        return 0
    try:
        with _connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM std_term").fetchone()[0])
    except sqlite3.Error:
        return 0


def describe() -> str:
    if not is_ready():
        return "术语索引未就绪（请运行 python scripts/build_terminology_index.py 或 seed_demo_index.py）"
    return f"术语索引已就绪（{indexed_count():,} 条）"


def _fts_query(keywords: list[str]) -> str:
    tokens: list[str] = []
    for kw in keywords:
        t = re.sub(r"\s+", "", (kw or "").strip())
        if len(t) >= 1:
            tokens.append(f'"{t.replace(chr(34), chr(34) * 2)}"*')
    return " OR ".join(tokens[:10])


def _row_to_item(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "base_id": row.get("base_id"),
        "term": row.get("term") or "",
        "definition": row.get("definition") or "",
        "std_id": row.get("std_id") or "",
        "std_chinesename": row.get("std_chinesename") or "",
        "std_type": row.get("std_type") or "",
        "ex_state_label": row.get("std_status") or "—",
        "has_pdf": bool(row.get("has_pdf")),
        "match_type": "term_index",
    }


def _empty_page(page: int, per_page: int) -> dict[str, Any]:
    return {
        "total": 0,
        "page": page,
        "per_page": per_page,
        "total_pages": 0,
        "items": [],
        "search_mode": "terminology",
    }


def _search_fts(keywords: list[str], *, page: int, per_page: int, gb_only: bool) -> dict[str, Any]:
    fts_q = _fts_query(keywords)
    if not fts_q:
        return _empty_page(page, per_page)
    offset = (page - 1) * per_page
    gb_clause = " AND (t.std_id LIKE 'GB%' OR t.std_type LIKE '%国标%')" if gb_only else ""
    with _connect() as conn:
        total = int(
            conn.execute(
                f"SELECT COUNT(*) FROM std_term t WHERE t.id IN "
                f"(SELECT rowid FROM std_term_fts WHERE std_term_fts MATCH ?){gb_clause}",
                (fts_q,),
            ).fetchone()[0]
        )
        rows = conn.execute(
            f"""
            SELECT t.* FROM std_term t
            WHERE t.id IN (SELECT rowid FROM std_term_fts WHERE std_term_fts MATCH ?){gb_clause}
            ORDER BY CASE WHEN t.term = ? THEN 0 WHEN t.term LIKE ? THEN 1 ELSE 2 END, t.std_id
            LIMIT ? OFFSET ?
            """,
            (fts_q, keywords[0], f"%{keywords[0]}%", per_page, offset),
        ).fetchall()
    items = [_row_to_item(dict(r)) for r in rows]
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "items": items,
        "search_mode": "terminology",
        "gb_only": gb_only,
    }


def _search_like(keywords: list[str], *, page: int, per_page: int, gb_only: bool) -> dict[str, Any]:
    if not keywords:
        return _empty_page(page, per_page)
    clauses, args = [], []
    for kw in keywords[:8]:
        clauses.append("(t.term LIKE ? OR t.definition LIKE ?)")
        args.extend([f"%{kw}%", f"%{kw}%"])
    gb_clause = " AND (t.std_id LIKE 'GB%' OR t.std_type LIKE '%国标%')" if gb_only else ""
    where = f"({' OR '.join(clauses)}){gb_clause}"
    offset = (page - 1) * per_page
    with _connect() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM std_term t WHERE {where}", args).fetchone()[0])
        rows = conn.execute(
            f"""
            SELECT t.* FROM std_term t WHERE {where}
            ORDER BY CASE WHEN t.term = ? THEN 0 WHEN t.term LIKE ? THEN 1 ELSE 2 END, t.std_id
            LIMIT ? OFFSET ?
            """,
            (*args, keywords[0], f"%{keywords[0]}%", per_page, offset),
        ).fetchall()
    items = [_row_to_item(dict(r)) for r in rows]
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "items": items,
        "search_mode": "terminology",
        "gb_only": gb_only,
    }


def _fallback_from_standards(keywords: list[str], *, page: int, per_page: int, gb_only: bool) -> dict[str, Any]:
    if not SQLITE_PATH.is_file() or not keywords:
        return _empty_page(page, per_page)
    primary = keywords[0]
    pattern = f"%{primary}%"
    gb_clause = " AND (b.std_id LIKE 'GB%' OR b.std_type LIKE '%国标%')" if gb_only else ""
    offset = (page - 1) * per_page
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = int(
            conn.execute(
                f"SELECT COUNT(*) FROM std_base b WHERE b.std_chinesename LIKE ?{gb_clause}",
                (pattern,),
            ).fetchone()[0]
        )
        rows = conn.execute(
            f"SELECT b.* FROM std_base b WHERE b.std_chinesename LIKE ?{gb_clause} ORDER BY b.std_id LIMIT ? OFFSET ?",
            (pattern, per_page, offset),
        ).fetchall()
    items = []
    for row in rows:
        d = dict(row)
        items.append(
            {
                "id": d["id"],
                "base_id": d["id"],
                "term": primary,
                "definition": f"（名称匹配，未收录术语定义）涉及：{d.get('std_chinesename') or ''}",
                "std_id": d.get("std_id") or "",
                "std_chinesename": d.get("std_chinesename") or "",
                "std_type": d.get("std_type") or "",
                "ex_state_label": d.get("std_status") or "—",
                "has_pdf": False,
                "match_type": "name_fallback",
            }
        )
    total_pages = (total + per_page - 1) // per_page if total else 0
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "items": items,
        "search_mode": "terminology_fallback",
        "gb_only": gb_only,
        "fallback": True,
    }


def search_page(
    query: str,
    *,
    page: int = 1,
    per_page: int = 10,
    gb_only: bool = True,
    semantic: bool = True,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"error": "请输入术语关键词"}

    page = max(1, page)
    per_page = min(max(per_page, 1), 50)
    expanded = expand_term_semantics(q, use_ai=semantic)
    keywords = expanded.get("keywords") or [q]

    if is_ready():
        try:
            data = _search_fts(keywords, page=page, per_page=per_page, gb_only=gb_only)
            if data["total"] == 0:
                data = _search_like(keywords, page=page, per_page=per_page, gb_only=gb_only)
        except sqlite3.Error:
            data = _search_like(keywords, page=page, per_page=per_page, gb_only=gb_only)
    else:
        data = _fallback_from_standards(keywords, page=page, per_page=per_page, gb_only=gb_only)

    return {
        **data,
        "query": q,
        "semantic": expanded,
        "ai_ready": ai_ready(),
        "index_ready": is_ready(),
    }


class TerminologyService:
    is_ready = staticmethod(is_ready)
    indexed_count = staticmethod(indexed_count)
    describe = staticmethod(describe)
    search_page = staticmethod(search_page)


terminology = TerminologyService()
