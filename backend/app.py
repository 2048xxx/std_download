"""标准 PDF 批量下载 — Flask API + 前端静态页。"""
from __future__ import annotations

import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND = _ROOT / "frontend"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import APP_VERSION, HOST, OPEN_BROWSER, PORT  # noqa: E402
from core.batch_download import (  # noqa: E402
    build_template_xlsx,
    build_zip_archive,
    build_zip_from_base_ids,
    build_zip_from_geo,
    parse_upload,
    preview_items,
)
from core.catalog_download import build_zip_from_catalog_ids  # noqa: E402
from core.geo_download import count_geo_matches, geo_download_status  # noqa: E402
from core.area_lookup import suggest_companies  # noqa: E402
from core.db import StandardInfo, db  # noqa: E402
from core.pdf_discovery import discover_pdfs_on_disk, start_background_scan  # noqa: E402
from core.pdf_service import collect_files_for_standard, find_pdf_on_disk  # noqa: E402
from core.product_clusters import list_clusters_brief  # noqa: E402
from core.product_search import product_search  # noqa: E402
from core.search_query import normalize_search_query
from core.search_filters import filter_options_payload, parse_advanced_filters  # noqa: E402
from paths import PDF_ROOT, PDF_SEARCH_ROOT, SQLITE_PATH, TUANGBIAO_DIR, ZHIDU_DIR  # noqa: E402
from core.tuangbiao_catalog import tuangbiao  # noqa: E402
from core.zhidu_catalog import zhidu  # noqa: E402

app = Flask(__name__, static_folder=None)

# Pre-populate disk PDF cache asynchronously on startup
try:
    start_background_scan()
except Exception:
    pass


def _api_error(message: str, status: int = 500):
    return jsonify({"ok": False, "error": message}), status


@app.errorhandler(404)
def api_not_found(e):
    if request.path.startswith("/api/"):
        return _api_error("接口不存在", 404)
    return e


@app.errorhandler(500)
def api_server_error(e):
    if request.path.startswith("/api/"):
        return _api_error("服务器内部错误，请稍后重试")
    return e


@app.after_request
def _no_cache_html(resp):
    if request.path.endswith(".html") or request.path in ("/", ""):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def create_app() -> Flask:
    return app


def _standard_json(std: StandardInfo, *, scan_disk: bool = True) -> dict:
    files = collect_files_for_standard(std, scan_disk=scan_disk)
    return {
        "id": std.id,
        "std_id": std.std_id,
        "std_type": std.std_type,
        "std_chinesename": std.std_chinesename,
        "std_status": std.std_status,
        "ex_state": std.ex_state,
        "ex_state_label": std.ex_state_label,
        "release_date": std.release_date,
        "implement_date": std.implement_date,
        "files": [
            {
                "id": f.get("id"),
                "file_name": f.get("file_name"),
                "file_path": f.get("file_path"),
                "file_size": f.get("file_size"),
                "exists": bool(f.get("exists")),
                "source": f.get("source", "db"),
                "disk_index": f.get("disk_index"),
            }
            for f in files
        ],
    }


def _enrich_items(items: list[dict], *, scan_disk: bool = True) -> list[dict]:
    out: list[dict] = []
    for it in items:
        std = db.get_by_id(int(it["id"]))
        if not std:
            out.append(it)
            continue
        full = _standard_json(std, scan_disk=scan_disk)
        full["has_pdf"] = any(f.get("exists") for f in full.get("files", []))
        out.append(full)
    return out


@app.route("/api/search")
def api_search():
    try:
        q = normalize_search_query(request.args.get("q") or "")
        src = (request.args.get("source") or "").strip()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 10))))
        scan_disk = request.args.get("scan_disk", "0") != "0"
        pdf_only = request.args.get("pdf_only", "1") != "0"
        enrich = request.args.get("enrich", "0") == "1"

        if not db.is_ready():
            return jsonify({"ok": False, "error": "标准库未就绪，请先运行 scripts/build_index.py"}), 503

        if src == "product":
            if not q:
                return jsonify({"ok": False, "error": "请输入产品名称，如：牙膏"}), 400
            data = product_search.search_page(
                q, page=page, per_page=per_page, pdf_only=pdf_only
            )
            if data.get("error"):
                return jsonify({"ok": False, "error": data["error"]}), 400
            if enrich:
                data["items"] = _enrich_items(
                    data.get("items") or [], scan_disk=scan_disk
                )
            return jsonify({"ok": True, "query": q, **data})

        if src == "tuangbiao":
            if not q:
                return jsonify({"ok": False, "error": "请输入团标名称或协会名关键词"}), 400
            if not tuangbiao.is_ready():
                return jsonify(
                    {
                        "ok": False,
                        "error": "团标索引未就绪，请运行 scripts/build_tuangbiao_index.py",
                    }
                ), 503
            data = tuangbiao.search_page(q, page=page, per_page=per_page)
            return jsonify({"ok": True, "query": q, **data})

        if src == "zhidu":
            if not q:
                return jsonify({"ok": False, "error": "请输入制度文件名称关键词"}), 400
            if not zhidu.is_ready():
                return jsonify(
                    {
                        "ok": False,
                        "error": "制度索引未就绪，请运行 scripts/build_zhidu_index.py",
                    }
                ), 503
            data = zhidu.search_page(q, page=page, per_page=per_page)
            return jsonify({"ok": True, "query": q, **data})

        filters = parse_advanced_filters(request.args)
        if not q and not filters.active():
            if request.args.get("browse") == "1":
                data = db.browse_page(
                    page=page, per_page=per_page, pdf_only=pdf_only
                )
                if enrich:
                    data["items"] = _enrich_items(
                        data.get("items") or [], scan_disk=scan_disk
                    )
                return jsonify({"ok": True, "query": "", **data})
            return jsonify({"ok": False, "error": "请输入关键词或设置高级筛选条件"}), 400

        from core.unit_geo import geo_index_ready, needs_geo_filter

        if needs_geo_filter(filters) and not db._mysql_available() and not geo_index_ready():
            return jsonify(
                {
                    "ok": False,
                    "error": "省/市/县/起草单位筛选需 units 地址索引，请运行 scripts/build_unit_index.py 或配置 MySQL mydate",
                }
            ), 503

        if (filters.unit_rank is not None or filters.unit_rank_gt3) and not filters.company:
            return jsonify(
                {
                    "ok": False,
                    "error": "「起草顺位」需同时填写「公司/起草单位」，否则无法按排序筛选",
                }
            ), 400

        if filters.active() or request.args.get("advanced") == "1":
            data = db.search_page_advanced(
                q,
                page=page,
                per_page=per_page,
                pdf_only=pdf_only,
                filters=filters,
            )
        else:
            data = db.search_page(q, page=page, per_page=per_page, pdf_only=pdf_only)

        if enrich:
            data["items"] = _enrich_items(
                data.get("items") or [], scan_disk=scan_disk
            )
        return jsonify({"ok": True, "query": q, **data})
    except ValueError:
        return jsonify({"ok": False, "error": "请求参数无效"}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"检索失败：{exc}"}), 500


@app.route("/api/search/filters")
def api_search_filters():
    province = (request.args.get("province") or "").strip()
    city = (request.args.get("city") or "").strip()
    company_q = (request.args.get("company_q") or "").strip()
    product_q = (request.args.get("product_q") or "").strip()
    from core import area_lookup
    from core.product_clusters import list_clusters_brief, suggest_phrases

    if company_q and not province and not city and not product_q:
        return jsonify({"ok": True, "companies": suggest_companies(company_q)})
    if product_q and not province and not city and not company_q:
        return jsonify(
            {
                "ok": True,
                "products": list_clusters_brief(),
                "product_suggestions": suggest_phrases(product_q, limit=16),
            }
        )

    products = list_clusters_brief()
    payload = filter_options_payload(
        std_types=db.list_std_types() if db.is_ready() else [],
        provinces=area_lookup.list_provinces(),
        cities=area_lookup.list_cities(province) if province else [],
        counties=area_lookup.list_counties(province, city) if province and city else [],
        products=products,
        companies=suggest_companies(company_q) if company_q else [],
        product_suggestions=suggest_phrases(product_q, limit=16) if product_q else [],
    )
    return jsonify({"ok": True, **payload})


@app.route("/api/product/clusters")
def api_product_clusters():
    return jsonify(
        {
            "ok": True,
            "clusters": product_search.list_clusters(),
            "ready": product_search.is_ready(),
            "describe": product_search.describe(),
        }
    )


@app.route("/api/download/geo/preview")
def api_download_geo_preview():
    filters = parse_advanced_filters(request.args)
    q = (request.args.get("q") or "").strip()
    pdf_only = request.args.get("pdf_only", "1") != "0"
    if not filters.province:
        return jsonify({"ok": False, "error": "请选择省份"}), 400
    if not geo_download_status()["ready"]:
        return jsonify(
            {
                "ok": False,
                "error": "地区批量下载未就绪，请配置 MySQL mydate 或运行 scripts/build_unit_index.py",
            }
        ), 503
    payload = count_geo_matches(filters, q=q, pdf_only=pdf_only)
    status = 200 if payload.get("ok") else 400
    return jsonify(payload), status


@app.route("/api/download/geo", methods=["POST"])
def api_download_geo():
    body = request.get_json(silent=True) or {}
    filters = parse_advanced_filters(body)
    q = (body.get("q") or "").strip()
    pdf_only = body.get("pdf_only", True) in (True, 1, "1", "true")
    scan_disk = body.get("scan_disk", True) in (True, 1, "1", "true")
    if not filters.province:
        return jsonify({"ok": False, "error": "请选择省份"}), 400
    if not geo_download_status()["ready"]:
        return jsonify(
            {
                "ok": False,
                "error": "地区批量下载未就绪，请配置 MySQL mydate 或运行 scripts/build_unit_index.py",
            }
        ), 503
    preview = count_geo_matches(filters, q=q, pdf_only=pdf_only)
    if not preview.get("ok"):
        return jsonify(preview), 400
    if preview.get("total", 0) < 1:
        return jsonify({"ok": False, "error": "当前条件下未找到可下载标准", **preview}), 404
    try:
        buf, summary = build_zip_from_geo(
            filters, q=q, scan_disk=scan_disk, pdf_only=pdf_only
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    if summary.get("success", 0) < 1:
        return jsonify(
            {
                "ok": False,
                "error": "未找到任何可打包的 PDF",
                "summary": summary,
                **preview,
            }
        ), 404
    region = preview.get("region") or "地区"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"地区批量下载_{region}_{stamp}.zip",
    )


@app.route("/api/download/bulk", methods=["POST"])
def api_download_bulk():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or data.get("base_ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "请勾选要下载的条目"}), 400
    source = (data.get("source") or "search").strip().lower()
    scan_disk = data.get("scan_disk") in (True, 1, "1", "true")
    try:
        if source == "tuangbiao":
            if not tuangbiao.is_ready():
                return jsonify({"ok": False, "error": "团标索引未就绪"}), 503
            buf, summary = build_zip_from_catalog_ids(tuangbiao, ids)
            zip_label = "团标PDF多项下载"
        elif source == "zhidu":
            if not zhidu.is_ready():
                return jsonify({"ok": False, "error": "制度索引未就绪"}), 503
            buf, summary = build_zip_from_catalog_ids(zhidu, ids)
            zip_label = "制度文件多项下载"
        else:
            buf, summary = build_zip_from_base_ids(ids, scan_disk=scan_disk)
            zip_label = "标准PDF多项下载"
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    if summary.get("success", 0) < 1:
        return jsonify(
            {
                "ok": False,
                "error": "所选条目均未找到可用文件",
                "summary": summary,
            }
        ), 404
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{zip_label}_{stamp}.zip",
    )


@app.route("/api/std/<int:base_id>")
def api_std_detail(base_id: int):
    scan_disk = request.args.get("scan_disk", "1") != "0"
    std = db.get_by_id(base_id)
    if not std:
        return jsonify({"ok": False, "error": "未找到该标准"}), 404
    return jsonify({"ok": True, "item": _standard_json(std, scan_disk=scan_disk)})


@app.route("/api/download/<int:file_id>")
def api_download_file(file_id: int):
    rec = db.get_filepath_record(file_id)
    if not rec:
        return jsonify({"ok": False, "error": "文件记录不存在"}), 404
    std = db.get_by_id(rec["base_id"])
    found = find_pdf_on_disk(
        rec.get("file_path") or "",
        rec.get("file_name") or "",
        std_id=std.std_id if std else None,
    )
    if not found or not found.is_file():
        return jsonify({"ok": False, "error": "磁盘上未找到 PDF 文件"}), 404
    return send_file(found, as_attachment=True, download_name=found.name)


@app.route("/api/download-std/<int:base_id>/<int:disk_index>")
def api_download_std_disk(base_id: int, disk_index: int):
    std = db.get_by_id(base_id)
    if not std:
        return jsonify({"ok": False, "error": "标准不存在"}), 404
    files = collect_files_for_standard(std, scan_disk=True)
    disk_files = [f for f in files if f.get("source") == "disk" and f.get("exists")]
    if disk_index < 0 or disk_index >= len(disk_files):
        return jsonify({"ok": False, "error": "磁盘文件索引无效"}), 404
    path = Path(disk_files[disk_index]["resolved_path"])
    if not path.is_file():
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/tuangbiao/<int:file_id>/download")
def api_tuangbiao_download(file_id: int):
    path = tuangbiao.resolve_path(file_id)
    if not path:
        return jsonify({"ok": False, "error": "文件不存在或索引已过期"}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/zhidu/<int:file_id>/download")
def api_zhidu_download(file_id: int):
    path = zhidu.resolve_path(file_id)
    if not path:
        return jsonify({"ok": False, "error": "文件不存在或索引已过期"}), 404
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return send_file(path, mimetype=mime, as_attachment=True, download_name=path.name)


@app.route("/api/catalog/status")
def api_catalog_status():
    return jsonify(
        {
            "ok": True,
            "tuangbiao": {
                "dir": str(TUANGBIAO_DIR),
                "dir_exists": tuangbiao.dir_exists(),
                "ready": tuangbiao.is_ready(),
                "indexed": tuangbiao.indexed_count(),
                "describe": tuangbiao.describe(),
            },
            "zhidu": {
                "dir": str(ZHIDU_DIR),
                "dir_exists": zhidu.dir_exists(),
                "ready": zhidu.is_ready(),
                "indexed": zhidu.indexed_count(),
                "describe": zhidu.describe(),
            },
        }
    )


@app.route("/")
def index_page():
    return send_from_directory(_FRONTEND, "index.html")


@app.route("/css/<path:filename>")
def static_css(filename: str):
    return send_from_directory(_FRONTEND / "css", filename)


@app.route("/js/<path:filename>")
def static_js(filename: str):
    return send_from_directory(_FRONTEND / "js", filename)


@app.route("/api/meta/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "version": APP_VERSION,
            "search_smart_v": 2,
            "db_ready": db.is_ready(),
            "db_backend": db.backend_name(),
            "geo_download": geo_download_status(),
            "sqlite_path": str(SQLITE_PATH),
            "sqlite_exists": SQLITE_PATH.is_file(),
            "pdf_root": str(PDF_ROOT),
            "pdf_root_exists": PDF_ROOT.is_dir(),
            "pdf_search_root": str(PDF_SEARCH_ROOT),
            "pdf_search_exists": PDF_SEARCH_ROOT.is_dir(),
            "tuangbiao": tuangbiao.describe(),
            "tuangbiao_ready": tuangbiao.is_ready(),
            "zhidu": zhidu.describe(),
            "zhidu_ready": zhidu.is_ready(),
        }
    )


@app.route("/api/batch/template")
def api_batch_template():
    data = build_template_xlsx()
    return send_file(
        __import__("io").BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="标准批量下载模板.xlsx",
    )


@app.route("/api/batch/parse", methods=["POST"])
def api_batch_parse():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "请上传 Excel 或 CSV 文件"}), 400
    data = upload.read()
    if not data:
        return jsonify({"ok": False, "error": "文件为空"}), 400
    if len(data) > 20 * 1024 * 1024:
        return jsonify({"ok": False, "error": "文件过大（上限 20MB）"}), 400
    result = parse_upload(upload.filename, data)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/batch/preview", methods=["POST"])
def api_batch_preview():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    if not items:
        return jsonify({"ok": False, "error": "无待预览条目"}), 400
    scan_disk = body.get("scan_disk", False)
    if not db.is_ready() and not scan_disk:
        return jsonify({"ok": False, "error": "标准库未就绪，请先构建索引或勾选「扫描磁盘」"}), 503
    return jsonify(preview_items(items, scan_disk=scan_disk))


@app.route("/api/batch/download", methods=["POST"])
def api_batch_download():
    scan_disk = request.args.get("scan_disk", "0") != "0"
    items: list[dict] = []
    original_data: bytes | None = None
    original_filename: str | None = None
    parse_meta: dict | None = None

    if request.files.get("file"):
        upload = request.files["file"]
        original_filename = upload.filename or "upload.xlsx"
        original_data = upload.read()
        parsed = parse_upload(original_filename, original_data)
        if not parsed.get("ok"):
            return jsonify(parsed), 400
        parse_meta = parsed.get("meta")
        items = parsed.get("items") or []
        form_items = request.form.get("items")
        if form_items:
            try:
                items = json.loads(form_items)
            except json.JSONDecodeError:
                pass
    else:
        body = request.get_json(silent=True) or {}
        items = body.get("items") or []
        scan_disk = body.get("scan_disk", scan_disk)

    if not items:
        return jsonify({"ok": False, "error": "无待下载条目"}), 400

    if not db.is_ready() and not scan_disk:
        return jsonify({"ok": False, "error": "标准库未就绪，请先运行 scripts/build_index.py 或勾选「扫描磁盘」"}), 503

    def _batch_progress(done: int, total: int) -> None:
        print(f"  [批量下载] {done}/{total}", flush=True)

    buf, summary = build_zip_archive(
        items,
        scan_disk=scan_disk,
        progress=_batch_progress,
        original_data=original_data,
        original_filename=original_filename,
        parse_meta=parse_meta,
    )
    if summary["success"] < 1:
        return jsonify({"ok": False, "error": "未找到任何可打包的 PDF", "summary": summary}), 404

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"标准PDF批量下载_{stamp}.zip",
    )


def main() -> None:
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    url = f"http://127.0.0.1:{PORT}/"
    print()
    print("  ========================================")
    print(f"    PDF 下载  v{APP_VERSION}")
    print(f"    浏览器打开: {url}")
    print(f"    数据库: {db.backend_name()}  PDF根目录: {PDF_ROOT}")
    if not db.is_ready():
        print("    [提示] 标准库未就绪，请运行: python scripts/build_index.py")
    if not PDF_ROOT.is_dir():
        print(f"    [提示] PDF 目录不存在，请检查 paths.py 或 .env 中的 PDF_ROOT")
    print("    请勿关闭本窗口")
    print("  ========================================")
    print()
    if OPEN_BROWSER:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
