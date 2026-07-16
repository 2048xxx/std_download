"""PDF 路径解析与标准文件收集。"""
from __future__ import annotations

from pathlib import Path

from paths import PDF_ROOT, PDF_SEARCH_ROOT
from core.db import StandardInfo
from core.pdf_discovery import discover_pdfs_on_disk, pdf_display_path
from core.std_normalize import filename_contains_std_id, file_std_identity_key


def find_pdf_on_disk(
    rel_path: str,
    file_name: str,
    *,
    std_id: str | None = None,
) -> Path | None:
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    if rel:
        candidate = (PDF_ROOT / rel).resolve()
        if candidate.is_file():
            return candidate
    name = (file_name or "").strip()
    if name:
        for root in (PDF_ROOT, PDF_SEARCH_ROOT):
            if not root.is_dir():
                continue
            direct = root / name
            if direct.is_file():
                return direct
            try:
                for hit in root.rglob(name):
                    if hit.is_file():
                        return hit
            except OSError:
                continue
    if std_id:
        hits = discover_pdfs_on_disk(std_id, limit=5)
        if hits:
            return hits[0]
    return None


def _file_display_name(f: dict) -> str:
    name = (f.get("file_name") or "").strip()
    if name:
        return name
    rel = (f.get("file_path") or "").strip()
    return Path(rel.replace("\\", "/")).name if rel else ""


def _file_dedupe_key(f: dict) -> str:
    name = _file_display_name(f)
    identity = file_std_identity_key(name) if name else None
    if identity:
        return f"std:{identity}"
    resolved = (f.get("resolved_path") or "").strip().lower()
    if resolved:
        return f"path:{resolved}"
    rel = (f.get("file_path") or "").strip().lower().replace("\\", "/")
    if rel and name:
        return f"rel:{rel}|{name.lower()}"
    if name:
        return f"name:{name.lower()}"
    fid = f.get("id")
    return f"id:{fid}" if fid is not None else f"disk:{f.get('disk_index', 0)}"


def _file_preference_score(f: dict) -> tuple:
    """去重时保留更优条目：存在 > 体积大 > 有库内 id。"""
    return (
        1 if f.get("exists") else 0,
        int(f.get("file_size") or 0),
        1 if f.get("id") is not None else 0,
    )


def _append_unique_file(files: list[dict], seen: dict[str, int], entry: dict) -> None:
    key = _file_dedupe_key(entry)
    if key not in seen:
        seen[key] = len(files)
        files.append(entry)
        return
    idx = seen[key]
    if _file_preference_score(entry) > _file_preference_score(files[idx]):
        files[idx] = entry


def _db_file_matches_standard(std: StandardInfo, f: dict) -> bool:
    """过滤库内错误挂接：文件名年份/编号必须与标准号一致。"""
    sid = (std.std_id or "").strip()
    if not sid:
        return True
    name = (f.get("file_name") or "").strip()
    rel = (f.get("file_path") or "").strip()
    check = name or Path(rel.replace("\\", "/")).name
    if not check:
        return False
    return filename_contains_std_id(check, sid)


def collect_files_for_standard(std: StandardInfo, *, scan_disk: bool = False) -> list[dict]:
    files: list[dict] = []
    seen: dict[str, int] = {}
    for f in std.files or []:
        if not _db_file_matches_standard(std, f):
            continue
        rel = f.get("file_path") or ""
        name = f.get("file_name") or ""
        # 已通过文件名校验，解析路径时不再用 std_id 宽松兜底，避免指到旧年版本
        found = find_pdf_on_disk(rel, name, std_id=None)
        if found and not filename_contains_std_id(found.name, std.std_id or ""):
            found = None
        entry = {
            **f,
            "exists": found is not None,
            "source": "db",
        }
        if found:
            entry["resolved_path"] = str(found)
        _append_unique_file(files, seen, entry)
    if scan_disk and not any(x.get("exists") for x in files):
        for i, pdf in enumerate(discover_pdfs_on_disk(std.std_id, limit=10)):
            try:
                rel = pdf_display_path(pdf)
            except Exception:
                rel = pdf.name
            _append_unique_file(
                files,
                seen,
                {
                    "id": None,
                    "file_name": pdf.name,
                    "file_path": rel,
                    "exists": True,
                    "source": "disk",
                    "disk_index": i,
                    "resolved_path": str(pdf),
                },
            )
    return files


def pick_pdf_path(std: StandardInfo, files: list[dict]) -> Path | None:
    for f in files:
        if not f.get("exists"):
            continue
        resolved = f.get("resolved_path")
        if resolved and Path(resolved).is_file():
            if filename_contains_std_id(Path(resolved).name, std.std_id or ""):
                return Path(resolved)
            continue
        found = find_pdf_on_disk(
            f.get("file_path") or "",
            f.get("file_name") or "",
            std_id=None,
        )
        if found and filename_contains_std_id(found.name, std.std_id or ""):
            return found
    return None
