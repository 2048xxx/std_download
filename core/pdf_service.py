"""PDF 路径解析与标准文件收集。"""
from __future__ import annotations

from pathlib import Path

from paths import PDF_ROOT, PDF_SEARCH_ROOT
from core.db import StandardInfo
from core.pdf_discovery import discover_pdfs_on_disk, pdf_display_path


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


def _file_dedupe_key(f: dict) -> str:
    resolved = (f.get("resolved_path") or "").strip().lower()
    if resolved:
        return f"path:{resolved}"
    rel = (f.get("file_path") or "").strip().lower().replace("\\", "/")
    name = (f.get("file_name") or "").strip().lower()
    if rel and name:
        return f"rel:{rel}|{name}"
    if name:
        return f"name:{name}"
    fid = f.get("id")
    return f"id:{fid}" if fid is not None else f"disk:{f.get('disk_index', 0)}"


def _append_unique_file(files: list[dict], seen: set[str], entry: dict) -> None:
    key = _file_dedupe_key(entry)
    if key in seen:
        return
    seen.add(key)
    files.append(entry)


def collect_files_for_standard(std: StandardInfo, *, scan_disk: bool = False) -> list[dict]:
    files: list[dict] = []
    seen: set[str] = set()
    for f in std.files or []:
        rel = f.get("file_path") or ""
        name = f.get("file_name") or ""
        found = find_pdf_on_disk(rel, name, std_id=std.std_id)
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
            return Path(resolved)
        found = find_pdf_on_disk(
            f.get("file_path") or "",
            f.get("file_name") or "",
            std_id=std.std_id,
        )
        if found:
            return found
    return None
