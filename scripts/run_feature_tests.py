"""功能回归测试（MySQL + 双工作流 + 术语检索）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.app import app

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    client = app.test_client()
    print("=" * 56)
    print("  ZKBZ 功能测试")
    print("=" * 56)

    # 1. 健康检查 / MySQL
    print("\n[1] 基础连接")
    r = client.get("/api/meta/health")
    h = r.get_json() or {}
    check("健康检查 HTTP 200", r.status_code == 200)
    check("MySQL 后端", h.get("db_backend") == "MySQL", str(h.get("db_backend")))
    check("数据库就绪", h.get("db_ready") is True)
    check("MySQL 可用", h.get("mysql_available") is True)

    # 2. 先查询后筛选
    print("\n[2] 先查询后筛选 (search_first)")
    r = client.get("/api/search?q=信息安全&workflow=search_first&per_page=5")
    d = r.get_json() or {}
    check("关键词检索成功", d.get("ok") and d.get("total", 0) > 0, f"total={d.get('total')}")
    check("返回 workflow", d.get("workflow") == "search_first")

    r2 = client.get("/api/search?q=信息安全&workflow=search_first&advanced=1&ex_state=1&per_page=5")
    d2 = r2.get_json() or {}
    check("叠加筛选（现行）", d2.get("ok") and d2.get("total", 0) >= 0, f"total={d2.get('total')}")

    r3 = client.get("/api/search?workflow=search_first&advanced=1&province=福建省")
    d3 = r3.get_json() or {}
    check("无关键词仅筛选应拒绝", d3.get("ok") is False and "先查询" in (d3.get("error") or ""))

    # 3. 先筛选后查询
    print("\n[3] 先筛选后查询 (filter_first)")
    r4 = client.get("/api/search?workflow=filter_first&advanced=1&ex_state=1&per_page=5")
    d4 = r4.get_json() or {}
    check("仅筛选（现行）", d4.get("ok") and d4.get("total", 0) > 0, f"total={d4.get('total')}")

    r5 = client.get("/api/search?q=信息安全&workflow=filter_first&advanced=1&ex_state=1&per_page=5")
    d5 = r5.get_json() or {}
    check("筛选+关键词", d5.get("ok") and d5.get("total", 0) > 0, f"total={d5.get('total')}")

    r6 = client.get("/api/search?q=信息安全&workflow=filter_first")
    d6 = r6.get_json() or {}
    check("无筛选仅关键词应拒绝", d6.get("ok") is False and "先筛选" in (d6.get("error") or ""))

    # 4. 术语检索
    print("\n[4] 术语检索")
    r7 = client.get("/api/terminology/status")
    t7 = r7.get_json() or {}
    check("术语状态", t7.get("ok") and t7.get("ready") is True, t7.get("describe", ""))

    r8 = client.get("/api/terminology/search?q=数据元&semantic=1&enrich=1")
    d8 = r8.get_json() or {}
    check("术语「数据元」", d8.get("ok") and d8.get("total", 0) > 0, f"total={d8.get('total')}")
    if d8.get("items"):
        item = d8["items"][0]
        check("含定义字段", bool(item.get("definition")), (item.get("definition") or "")[:40])
        check("含国标编号", bool(item.get("std_id")), item.get("std_id"))

    r9 = client.get("/api/terminology/search?q=个人信息&semantic=1")
    d9 = r9.get_json() or {}
    check("术语「个人信息」语义扩展", d9.get("ok") and d9.get("total", 0) > 0, f"total={d9.get('total')}, source={((d9.get('semantic') or {}).get('source'))}")

    # 5. 同类产品
    print("\n[5] 其他模块")
    r10 = client.get("/api/search?q=牙膏&source=product&per_page=3")
    d10 = r10.get_json() or {}
    check("同类产品检索", d10.get("ok"), f"total={d10.get('total')}")

    print("\n" + "=" * 56)
    print(f"  结果: {PASS} 通过, {FAIL} 失败")
    print("=" * 56)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
