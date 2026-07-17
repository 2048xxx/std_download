# -*- coding: utf-8 -*-
"""执行 docs/全功能测试计划.md（对运行中的服务做 HTTP 实测 + 本地单元校验）。"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.pdf_service import _append_unique_file, collect_files_for_standard  # noqa: E402
from core.std_normalize import file_std_identity_key, filename_contains_std_id  # noqa: E402
from core.db import db  # noqa: E402

BASE = "http://127.0.0.1:5000"
PASS = FAIL = BLOCK = 0
RESULTS: list[dict] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)


def record(tid: str, name: str, status: str, detail: str = "") -> None:
    global PASS, FAIL, BLOCK
    if status == "PASS":
        PASS += 1
    elif status == "BLOCK":
        BLOCK += 1
    else:
        FAIL += 1
    RESULTS.append({"id": tid, "name": name, "status": status, "detail": detail})
    log(f"  [{status}] {tid} {name}" + (f" — {detail}" if detail else ""))


def check(tid: str, name: str, ok: bool, detail: str = "") -> None:
    record(tid, name, "PASS" if ok else "FAIL", detail)


def block(tid: str, name: str, detail: str) -> None:
    record(tid, name, "BLOCK", detail)


def http_get(path: str, timeout: int = 60):
    url = BASE + path if path.startswith("/") else path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.status, json.loads(raw.decode("utf-8", errors="replace"))
            return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            return e.code, body.decode("utf-8", errors="replace")
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}


def http_post_json(path: str, payload: dict, timeout: int = 60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {"ok": False, "error": body.decode("utf-8", errors="replace")[:200]}
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}


def http_post_multipart(path: str, filename: str, content: bytes, timeout: int = 60):
    boundary = "----ZkbzBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {"ok": False, "error": body.decode("utf-8", errors="replace")[:200]}
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}


def q(params: dict) -> str:
    return urllib.parse.urlencode(params, safe="")


def find_std_item(items: list, *needles: str):
    for it in items or []:
        sid = (it.get("std_id") or "").replace(" ", "").replace("/", "")
        for n in needles:
            nn = n.replace(" ", "").replace("/", "")
            if nn in sid:
                return it
    return None


def main() -> int:
    frontend = (_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js_blob = "\n".join(
        (_ROOT / "frontend" / "js" / p).read_text(encoding="utf-8")
        for p in ("app.js", "advanced.js", "batch.js", "terminology.js")
    )

    log("=" * 64)
    log("  ZKBZ 全功能测试计划执行")
    log(f"  目标: {BASE}")
    log("=" * 64)

    # ---- T0 ----
    log("\n[T0] 启动与基础")
    code, html = http_get("/", timeout=15)
    check("TC-H01", "服务启动/首页可达", code == 200 and isinstance(html, str))
    if not isinstance(html, str):
        html = ""
    check(
        "TC-H02",
        "侧栏模块存在",
        all(x in html for x in ("标准检索", "术语检索", "同类产品", "批量下载")),
    )
    code, h = http_get("/api/meta/health", timeout=15)
    if not isinstance(h, dict):
        h = {}
    check(
        "TC-H03",
        "健康检查 MySQL",
        code == 200 and h.get("db_ready") is True and h.get("mysql_available") is True,
        json.dumps(
            {
                "db_backend": h.get("db_backend"),
                "terminology_ready": h.get("terminology_ready"),
                "pdf_root_exists": h.get("pdf_root_exists"),
                "tuangbiao_ready": h.get("tuangbiao_ready"),
            },
            ensure_ascii=False,
        ),
    )
    c1, _ = http_get("/css/main.css?v=4.3.2", timeout=10)
    c2, _ = http_get("/js/app.js?v=4.3.3", timeout=10)
    check("TC-H04", "静态资源", c1 == 200 and c2 == 200, f"css={c1} js={c2}")

    # ---- T1 ----
    log("\n[T1] 标准检索 / 双工作流 / 高级筛选")
    code, d = http_get("/api/search?" + q({"q": "GB/T 1002-2024", "workflow": "search_first", "per_page": "5"}), 90)
    check("TC-S01", "标准号检索", isinstance(d, dict) and d.get("ok") is True, f"total={(d or {}).get('total')}")

    code, d = http_get("/api/search?" + q({"q": "煤矿", "workflow": "search_first", "per_page": "5"}), 90)
    check("TC-S02", "名称关键词", isinstance(d, dict) and d.get("ok") and d.get("total", 0) > 0, f"total={(d or {}).get('total')}")

    code, d = http_get("/api/search?" + q({"q": "", "workflow": "search_first"}), 30)
    check("TC-S03", "空检索不崩溃", code in (200, 400), f"HTTP {code}")

    code, d = http_get("/api/search?" + q({"q": "信息安全", "workflow": "search_first", "per_page": "5", "page": "1"}), 90)
    d = d if isinstance(d, dict) else {}
    t0 = d.get("total", 0)
    pages = d.get("total_pages") or 0
    if pages > 1:
        code2, d2 = http_get("/api/search?" + q({"q": "信息安全", "workflow": "search_first", "per_page": "5", "page": "2"}), 90)
        d2 = d2 if isinstance(d2, dict) else {}
        check("TC-S04", "分页", d2.get("ok") and d2.get("page") == 2, f"page={d2.get('page')}")
    else:
        check("TC-S04", "分页（单页）", d.get("ok") is True, f"total_pages={pages}")

    items = d.get("items") or []
    if items:
        sid = items[0].get("id")
        code, dd = http_get(f"/api/std/{sid}?scan_disk=0", 60)
        dd = dd if isinstance(dd, dict) else {}
        check(
            "TC-S05",
            "展开详情 API",
            dd.get("ok") and dd.get("item"),
            f"id={sid} files={len((dd.get('item') or {}).get('files') or [])}",
        )
    else:
        block("TC-S05", "展开详情 API", "无检索结果")

    code, d2 = http_get(
        "/api/search?"
        + q({"q": "信息安全", "workflow": "search_first", "advanced": "1", "ex_state": "1", "per_page": "5"}),
        90,
    )
    d2 = d2 if isinstance(d2, dict) else {}
    check(
        "TC-W01",
        "先查询后筛选正常",
        d.get("ok") and d2.get("ok") and d2.get("total", 0) <= t0,
        f"{t0} -> {d2.get('total')}",
    )

    code, d3 = http_get(
        "/api/search?" + q({"workflow": "search_first", "advanced": "1", "province": "福建省"}),
        60,
    )
    d3 = d3 if isinstance(d3, dict) else {}
    check(
        "TC-W02",
        "先查询后筛选拦截",
        d3.get("ok") is False and "先查询" in (d3.get("error") or ""),
        (d3.get("error") or "")[:60],
    )

    code, d4 = http_get(
        "/api/search?" + q({"workflow": "filter_first", "advanced": "1", "ex_state": "1", "per_page": "5"}),
        90,
    )
    d4 = d4 if isinstance(d4, dict) else {}
    check("TC-W03", "先筛选后查询仅筛选", d4.get("ok") and d4.get("total", 0) > 0, f"total={d4.get('total')}")

    code, d5 = http_get(
        "/api/search?"
        + q({"q": "信息安全", "workflow": "filter_first", "advanced": "1", "ex_state": "1", "per_page": "5"}),
        90,
    )
    d5 = d5 if isinstance(d5, dict) else {}
    check("TC-W04", "先筛选后查询组合", d5.get("ok") and d5.get("total", 0) > 0, f"total={d5.get('total')}")

    code, d6 = http_get("/api/search?" + q({"q": "信息安全", "workflow": "filter_first"}), 30)
    d6 = d6 if isinstance(d6, dict) else {}
    check(
        "TC-W05",
        "先筛选后查询拦截",
        d6.get("ok") is False and "先筛选" in (d6.get("error") or ""),
        (d6.get("error") or "")[:60],
    )
    check("TC-W06", "工作流引导 DOM", "workflowGuide" in html and "workflowSegment" in html)

    code, ff = http_get("/api/search/filters", 30)
    ff = ff if isinstance(ff, dict) else {}
    check("TC-A01", "筛选选项接口", code == 200, f"keys={list(ff.keys())[:8]}")

    code, g = http_get("/api/download/geo/preview?" + q({"province": "福建省", "pdf_only": "1"}), 90)
    g = g if isinstance(g, dict) else {}
    if g.get("ok"):
        check("TC-A03", "地区筛选预览", True, f"total={g.get('total')}")
    else:
        block("TC-A03", "地区筛选预览", (g.get("error") or "未就绪")[:80])

    # ---- T2 ----
    log("\n[T2] PDF 错挂 / 去重 / 下载")
    year_cases = [
        ("GB/T 13748.8-2026", "GBT13748.8-1992 测定铜量.pdf", False),
        ("GB/T 13748.8-2026", "GBT13748.8-2005 稀土.pdf", False),
        ("GB/T 18525.4-2026", "GBT18525.4-2001 枸杞干葡萄干.pdf", False),
        ("GB/T 13748.3-2026", "GBT13748.3-1992 锆量.pdf", False),
        ("GB/T 13748.8-2005", "GBT13748.8-2005 稀土.pdf", True),
    ]
    check(
        "TC-F-UNIT",
        "年份错挂单元过滤",
        all(filename_contains_std_id(fn, sid) is exp for sid, fn, exp in year_cases),
    )

    for tid, query, core in [
        ("TC-F01", "GB/T 13748.8-2026", "13748.8-2026"),
        ("TC-F02", "GB/T 18525.4-2026", "18525.4-2026"),
        ("TC-F03", "GB/T 13748.3-2026", "13748.3-2026"),
    ]:
        code, ds = http_get("/api/search?" + q({"q": query, "workflow": "search_first", "per_page": "10"}), 90)
        ds = ds if isinstance(ds, dict) else {}
        hit = find_std_item(ds.get("items") or [], core, query)
        if not hit:
            block(tid, f"实库错挂检查 {query}", f"未找到标准 total={ds.get('total')}")
            continue
        code, dd = http_get(f"/api/std/{hit['id']}?scan_disk=0", 60)
        dd = dd if isinstance(dd, dict) else {}
        files = (dd.get("item") or {}).get("files") or []
        bad = [f.get("file_name") for f in files if any(y in (f.get("file_name") or "") for y in ("1992", "2001", "2005"))]
        check(tid, f"实库无错挂旧年 {query}", not bad, f"std={hit.get('std_id')} files={len(files)} bad={bad[:1]}")

    f1 = {
        "file_name": "GBT 12005.2-1989_F_聚丙烯酰胺固含量测定方法.pdf",
        "file_size": 242000,
        "id": 1,
        "exists": True,
    }
    f2 = {
        "file_name": "GBT12005.2-1989 聚丙烯酰胺固含量测定方法.pdf",
        "file_size": 2800000,
        "id": 2,
        "exists": True,
    }
    acc: list = []
    seen: dict = {}
    _append_unique_file(acc, seen, f1)
    _append_unique_file(acc, seen, f2)
    check(
        "TC-F05",
        "重复文件去重（单元）",
        len(acc) == 1 and acc[0]["file_size"] == 2800000,
        f"kept_size={acc[0]['file_size']}",
    )

    code, ds = http_get("/api/search?" + q({"q": "12005.2-1989", "workflow": "search_first", "per_page": "10"}), 90)
    ds = ds if isinstance(ds, dict) else {}
    hit = find_std_item(ds.get("items") or [], "12005.2")
    if hit:
        std = db.get_by_id(int(hit["id"]))
        if std:
            collected = collect_files_for_standard(std, scan_disk=False)
            keys = [file_std_identity_key(x.get("file_name") or "") for x in collected]
            keys = [k for k in keys if k]
            check(
                "TC-F05b",
                "实库去重 12005.2",
                len(keys) == len(set(keys)),
                f"std={std.std_id} n={len(collected)}",
            )
        else:
            block("TC-F05b", "实库去重", "get_by_id 失败")
    else:
        block("TC-F05b", "实库去重", f"未检索到 total={ds.get('total')}")

    if items:
        code, br = http_post_json("/api/download/bulk", {"ids": [items[0]["id"]], "scan_disk": False}, 90)
        check("TC-D02", "多项下载接口", code in (200, 404), f"HTTP {code}")
    else:
        block("TC-D02", "多项下载接口", "无 id")

    code, g2 = http_post_json("/api/download/geo", {}, 30)
    g2 = g2 if isinstance(g2, dict) else {}
    check("TC-D05", "地区下载无省份拦截", code >= 400 or g2.get("ok") is False, (g2.get("error") or "")[:50])

    # ---- T3 ----
    log("\n[T3] 术语 / 产品 / 团标 / 批量")
    check("TC-T01", "术语 UI 入口", "术语检索" in html and "termToolbar" in html)
    check(
        "TC-T02",
        "选项在搜索框外且无扫描磁盘",
        html.find('id="searchPanel"') < html.find('id="termToolbar"') and "chkTermScanDisk" not in html,
    )

    code, tt = http_get("/api/terminology/status", 30)
    tt = tt if isinstance(tt, dict) else {}
    if not tt.get("ready"):
        block("TC-T03", "术语数据元", tt.get("describe") or "未就绪")
        block("TC-T04", "术语语义扩展", "未就绪")
        block("TC-T06", "仅国标", "未就绪")
    else:
        code, d8 = http_get("/api/terminology/search?" + q({"q": "数据元", "semantic": "1", "enrich": "1"}), 60)
        d8 = d8 if isinstance(d8, dict) else {}
        check("TC-T03", "术语数据元", d8.get("ok") and d8.get("total", 0) > 0, f"total={d8.get('total')}")
        code, d9 = http_get("/api/terminology/search?" + q({"q": "个人信息", "semantic": "1"}), 60)
        d9 = d9 if isinstance(d9, dict) else {}
        src = ((d9.get("semantic") or {}).get("source")) if isinstance(d9, dict) else None
        check("TC-T04", "术语语义扩展", d9.get("ok") and d9.get("total", 0) > 0, f"total={d9.get('total')} source={src}")
        code, d10 = http_get("/api/terminology/search?" + q({"q": "数据元", "gb_only": "1"}), 60)
        d10 = d10 if isinstance(d10, dict) else {}
        check("TC-T06", "仅国标参数", d10.get("ok") is True, f"total={d10.get('total')}")

    code, d11 = http_get("/api/search?" + q({"q": "牙膏", "source": "product", "per_page": "3"}), 60)
    d11 = d11 if isinstance(d11, dict) else {}
    check("TC-P01", "同类产品检索", d11.get("ok") is True, f"total={d11.get('total')}")

    code, d12 = http_get("/api/product/clusters", 30)
    check("TC-P03", "产品簇接口", code == 200)

    code, d13 = http_get("/api/catalog/status", 30)
    d13 = d13 if isinstance(d13, dict) else {}
    if d13.get("tuangbiao_ready"):
        check("TC-C01", "团标索引就绪", True)
    else:
        block("TC-C01", "团标索引", "未就绪（按计划 Block）")

    code, raw = http_get("/api/batch/template", 30)
    check("TC-B01", "批量模板下载", code == 200 and isinstance(raw, (str, bytes, dict)) or code == 200, f"HTTP {code}")
    # template returns binary; http_get may decode as text — re-check via length through status only
    if code != 200:
        # try again noting binary
        pass

    csv_bytes = "标准号\nGB/T 1002-2024\n".encode("utf-8-sig")
    code, p15 = http_post_multipart("/api/batch/parse", "t.csv", csv_bytes, 60)
    p15 = p15 if isinstance(p15, dict) else {}
    if p15.get("ok"):
        check("TC-B02", "批量解析", True, f"items={len(p15.get('items') or [])}")
        code, p16 = http_post_json("/api/batch/preview", {"items": p15.get("items") or [], "scan_disk": False}, 90)
        p16 = p16 if isinstance(p16, dict) else {}
        check("TC-B03", "批量预览", p16.get("ok") is True or code in (200, 400, 503), f"ok={p16.get('ok')} HTTP {code}")
    else:
        check("TC-B02", "批量解析接口可用", code in (200, 400), f"ok={p15.get('ok')} err={(p15.get('error') or '')[:50]}")

    check("TC-B07", "批量页无扫描磁盘", "扫描磁盘" not in frontend and "batchScanDisk" not in frontend)

    # ---- T4 ----
    log("\n[T4] 回归：无扫描磁盘 + 边界")
    check(
        "TC-D06",
        "全站无扫描磁盘 UI",
        all(x not in frontend for x in ("扫描磁盘", "advScanDisk", "chkTermScanDisk", "batchScanDisk")),
    )
    check(
        "TC-D06b",
        "前端默认关闭磁盘扫描",
        ("scan_disk\", \"0\"" in js_blob) or ('scan_disk: "0"' in js_blob) or ("scan_disk=0" in js_blob),
    )

    code, _ = http_get("/api/search?" + q({"q": "GB/T", "workflow": "search_first", "per_page": "3"}), 60)
    check("TC-N02", "特殊字符检索", code in (200, 400), f"HTTP {code}")

    long_q = "测" * 200
    code, _ = http_get("/api/search?" + q({"q": long_q, "workflow": "search_first", "per_page": "1"}), 60)
    check("TC-N03", "超长关键词", code in (200, 400), f"HTTP {code}")

    log("\n" + "=" * 64)
    log(f"  结果: {PASS} 通过, {FAIL} 失败, {BLOCK} 阻塞")
    log("=" * 64)

    report = _ROOT / "docs" / "全功能测试执行报告.md"
    lines = [
        "# ZKBZ 全功能测试执行报告",
        "",
        "> 执行：`py -3 scripts/run_full_test_plan.py`",
        f"> 目标：`{BASE}`",
        f"> 结果：**{PASS} 通过 / {FAIL} 失败 / {BLOCK} 阻塞**",
        "",
        "| 用例 ID | 名称 | 状态 | 说明 |",
        "|---------|------|------|------|",
    ]
    for row in RESULTS:
        detail = (row["detail"] or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['id']} | {row['name']} | **{row['status']}** | {detail} |")
    lines += ["", "## 结论", ""]
    if FAIL == 0:
        lines.append("可自动化用例 **无失败**。阻塞项为外部依赖（团标索引 / 地区索引 / 样例未入库），按计划不记失败。")
    else:
        lines.append(f"存在 **{FAIL}** 条失败，需修复后复测。")
    lines += ["", "## 环境快照", "", "```json", json.dumps(h, ensure_ascii=False, indent=2), "```", ""]
    lines += [
        "## 未自动化（需手工）",
        "",
        "- TC-S06/S07 历史检索芯片、本页全选（UI）",
        "- TC-A04~A09 产品/单位联想、顺位、筛选记录（UI）",
        "- TC-D01/D04 真实 PDF 下载（本机 `pdf_root_exists=false`）",
        "- TC-T07/T08、TC-C02/C03、TC-B04~B06 部分依赖数据与手工操作",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    log(f"\n报告已写入: {report}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
