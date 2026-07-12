"""从种子 JSON 构建演示用 standards.db + terms.db。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from paths import DATA_DIR, SQLITE_PATH, TERMS_DB_PATH

SEED_PATH = DATA_DIR / "seed" / "terminology_seed.json"


def build() -> None:
    if not SEED_PATH.is_file():
        raise FileNotFoundError(f"未找到 {SEED_PATH}")
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    standards = list(raw.get("standards") or [])
    terms = list(raw.get("terms") or [])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    if TERMS_DB_PATH.exists():
        TERMS_DB_PATH.unlink()

    t0 = time.time()
    conn = sqlite3.connect(SQLITE_PATH)
    conn.executescript(
        """
        CREATE TABLE std_base (
            id INTEGER PRIMARY KEY, std_id TEXT NOT NULL, std_type TEXT,
            std_chinesename TEXT, std_status TEXT, ex_state INTEGER,
            release_date TEXT, implement_date TEXT, std_id_norm TEXT NOT NULL
        );
        CREATE TABLE std_filepath (
            id INTEGER PRIMARY KEY, base_id INTEGER NOT NULL,
            file_path TEXT NOT NULL, file_name TEXT NOT NULL, file_size INTEGER
        );
        """
    )
    id_by_std: dict[str, int] = {}
    for i, row in enumerate(standards, start=1):
        std_id = str(row.get("std_id") or "").strip()
        norm = "".join(std_id.upper().split())
        conn.execute(
            "INSERT INTO std_base VALUES (?,?,?,?,?,?,?,?,?)",
            (i, std_id, row.get("std_type"), row.get("std_chinesename"), row.get("std_status"),
             row.get("ex_state"), row.get("release_date"), row.get("implement_date"), norm),
        )
        conn.execute(
            "INSERT INTO std_filepath VALUES (?,?,?,?,?)",
            (i, i, f"demo/{norm}.pdf", f"{norm}.pdf", None),
        )
        id_by_std[std_id] = i
    conn.commit()
    conn.close()

    tconn = sqlite3.connect(TERMS_DB_PATH)
    tconn.executescript(
        """
        CREATE TABLE std_term (
            id INTEGER PRIMARY KEY AUTOINCREMENT, base_id INTEGER, std_id TEXT NOT NULL,
            std_chinesename TEXT, std_type TEXT, std_status TEXT,
            term TEXT NOT NULL, definition TEXT, has_pdf INTEGER DEFAULT 0
        );
        CREATE VIRTUAL TABLE std_term_fts USING fts5(
            term, definition, std_chinesename, content='std_term', content_rowid='id', tokenize='unicode61'
        );
        CREATE TRIGGER std_term_ai AFTER INSERT ON std_term BEGIN
          INSERT INTO std_term_fts(rowid, term, definition, std_chinesename)
          VALUES (new.id, new.term, new.definition, new.std_chinesename);
        END;
        """
    )
    meta = {r[0]: r for r in sqlite3.connect(SQLITE_PATH).execute(
        "SELECT std_id, std_chinesename, std_type, std_status FROM std_base"
    )}
    count = 0
    for row in terms:
        std_id = str(row.get("std_id") or "").strip()
        term = str(row.get("term") or "").strip()
        definition = str(row.get("definition") or "").strip()
        if not std_id or not term:
            continue
        m = meta.get(std_id, (std_id, "", "国标", "现行"))
        tconn.execute(
            "INSERT INTO std_term (base_id,std_id,std_chinesename,std_type,std_status,term,definition,has_pdf) VALUES (?,?,?,?,?,?,?,1)",
            (id_by_std.get(std_id), std_id, m[1], m[2], m[3], term, definition),
        )
        count += 1
    tconn.commit()
    tconn.close()
    print(f"完成: {len(standards)} 标准, {count} 术语 ({time.time()-t0:.1f}s)", flush=True)


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"[错误] {exc}", flush=True)
        sys.exit(1)
