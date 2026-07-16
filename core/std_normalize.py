"""标准编号与 PDF 文件名的规范化与互转（如 YD/T ↔ YDT、GB/T ↔ GBT）。"""

from __future__ import annotations

import re
from pathlib import Path

# 匹配标准号主体：前缀 + 编号 + 年份，如 YD/T 1234.1-2020
_STD_CORE = re.compile(
    r"^([A-Z]{1,6}(?:/[A-Z])?)\s*([\d]+(?:\.\d+)*)\s*[-－—]?\s*(\d{2,4})?\s*$",
    re.IGNORECASE,
)
# 紧凑写法：YDT1234-2020、GBT1002-2024
_STD_COMPACT = re.compile(
    r"^([A-Z]{2,5})([TZX])([\d]+(?:\.\d+)*)(?:[-－—](\d{2,4}))?$",
    re.IGNORECASE,
)


def normalize_std_id(std_id: str) -> str:
    """统一检索键：大写、去空格、去斜杠、统一连字符。"""
    s = std_id.strip().upper()
    s = s.replace("／", "/")
    s = re.sub(r"\s+", "", s)
    s = s.replace("/", "")
    s = s.replace("—", "-").replace("－", "-")
    return s


def _dash_variants(s: str) -> set[str]:
    out = {s}
    if "-" in s:
        out.add(s.replace("-", "—"))
        out.add(s.replace("-", "－"))
        out.add(re.sub(r"-+", "", s))
    return out


def std_id_lookup_variants(query: str) -> list[str]:
    """生成用于数据库精确匹配的多种写法。"""
    raw = query.strip()
    if not raw:
        return []
    variants: set[str] = set()
    variants.add(raw)
    upper = raw.upper()
    variants.add(upper)
    collapsed = re.sub(r"\s+", " ", upper).strip()
    variants.add(collapsed)

    no_space = re.sub(r"\s+", "", upper)
    variants.add(no_space)
    variants.update(_dash_variants(no_space))

    no_slash = no_space.replace("/", "")
    variants.add(no_slash)
    variants.update(_dash_variants(no_slash))

    # YDT1234 -> YD/T 1234（补斜杠，便于命中库中带 / 的编号）
    m = _STD_CORE.match(no_slash.replace("-", " "))
    if not m:
        m = _STD_CORE.match(no_space)
    if m:
        prefix, num, year = m.group(1), m.group(2), m.group(3) or ""
        if "/" not in prefix and len(prefix) >= 3 and prefix[-1] in "TZX":
            slash_prefix = prefix[:-1] + "/" + prefix[-1]
            body = f"{slash_prefix} {num}"
            if year:
                body += f"-{year}"
            variants.add(body)
            variants.add(body.replace(" ", ""))
            variants.add(re.sub(r"\s+", "", body.upper()))

    # 去重并保持顺序
    ordered: list[str] = []
    for v in variants:
        v = v.strip()
        if v and v not in ordered:
            ordered.append(v)
    return ordered


def pdf_basename_variants(file_name: str, std_id: str | None = None) -> list[str]:
    """生成可能在磁盘上出现的 PDF 文件名（含 / 与不含 /）。"""
    names: list[str] = []

    def add(name: str) -> None:
        name = name.strip()
        if not name:
            return
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        if name not in names:
            names.append(name)

    for src in (file_name, std_id):
        if not src:
            continue
        base = Path(src.replace("\\", "/")).name
        add(base)
        add(base.replace("/", ""))
        add(re.sub(r"\s+", "", base))
        add(re.sub(r"\s+", " ", base.replace("/", " ")).strip())

        # 将 XXX/T 转为 XXXT（PDF 常见写法）
        compact = re.sub(r"\s+", "", base.upper())
        no_slash = compact.replace("/", "")
        add(no_slash)
        m = _STD_CORE.match(no_slash.replace("-", " "))
        if m and "/" not in m.group(1):
            p = m.group(1)
            if len(p) >= 3 and p[-1] in "TZX":
                add(base.replace(p, p[:-1] + "/" + p[-1], 1))

    if std_id:
        norm = normalize_std_id(std_id)
        # 用标准号核心在磁盘中模糊匹配：*YDT1234*2020*.pdf
        core = re.sub(r"^([A-Z]+)", r"\1", norm)  # already normalized
        if len(core) >= 4:
            add(f"{core}.pdf")

    return names


def pdf_path_variants(rel_path: str, file_name: str, std_id: str | None = None) -> list[str]:
    """生成待尝试的相对路径列表。"""
    paths: list[str] = []
    seen: set[str] = set()

    def add(p: str) -> None:
        p = p.replace("\\", "/").lstrip("/")
        if p and p not in seen:
            seen.add(p)
            paths.append(p)

    add(rel_path)
    add(rel_path.replace("/", ""))

    dir_part = str(Path(rel_path.replace("\\", "/")).parent)
    if dir_part and dir_part != ".":
        for bn in pdf_basename_variants(file_name, std_id):
            add(f"{dir_part}/{bn}")
    else:
        for bn in pdf_basename_variants(file_name, std_id):
            add(bn)

    return paths


def _normalize_year(year: str | None) -> str:
    """统一年份：两位转为 20xx（如 05→2005），四位保持不变。"""
    y = (year or "").strip()
    if not y:
        return ""
    if len(y) == 2 and y.isdigit():
        return f"20{y}"
    return y


def parse_std_parts(text: str) -> tuple[str, str, str] | None:
    """解析标准号为 (前缀, 编号, 年份)。前缀无斜杠，如 GBT / GB / JBT。"""
    raw = normalize_std_id(text or "")
    if not raw or len(raw) < 3:
        return None
    compact = raw.replace("—", "-").replace("－", "-")
    m = _STD_COMPACT.match(compact)
    if m:
        prefix = (m.group(1) + m.group(2)).upper()
        return prefix, m.group(3), _normalize_year(m.group(4))
    m2 = re.match(
        r"^([A-Z]{1,6})([\d]+(?:\.\d+)*)(?:-(\d{2,4}))?$",
        compact,
    )
    if m2:
        return m2.group(1).upper(), m2.group(2), _normalize_year(m2.group(3))
    return None


def extract_std_token_from_filename(filename: str) -> str:
    """从文件名提取前导标准号片段（去掉 _F_ 后缀与中文题名）。"""
    stem = Path(filename or "").stem.upper()
    stem = re.split(r"_[FTZX]_", stem, maxsplit=1)[0]
    stem = re.split(r"[\u4e00-\u9fff]", stem, maxsplit=1)[0]
    stem = normalize_std_id(stem)
    stem = stem.rstrip("_- .")
    return stem


def file_std_identity_key(filename: str) -> str | None:
    """同一标准不同文件名的去重键（如 GBT 12005.2-1989 与 GBT12005.2-1989）。"""
    token = extract_std_token_from_filename(filename)
    parts = parse_std_parts(token)
    if not parts:
        return None
    prefix, num, year = parts
    return f"{prefix}{num}-{year}" if year else f"{prefix}{num}"


def filename_contains_std_id(filename: str, std_id: str) -> bool:
    """判断文件名是否对应该标准号（前缀+编号必须一致；有年份则必须同年）。

    避免仅按编号前缀匹配，把 1992/2005 旧版挂到 2026 新版，
    或把 13748.8 误匹配到 13748.81。
    """
    sid = parse_std_parts(std_id)
    if not sid:
        return False
    token = extract_std_token_from_filename(filename)
    fid = parse_std_parts(token)
    if not fid:
        # 无法从文件名解析出标准号时，不做宽松子串匹配
        return False
    if sid[0] != fid[0] or sid[1] != fid[1]:
        return False
    # 标准带年份时，文件必须带相同年份
    if sid[2]:
        return bool(fid[2]) and sid[2] == fid[2]
    # 标准无年份：允许任意年份文件（仅编号一致）
    return True


def std_id_glob_patterns(std_id: str) -> list[str]:
    """生成磁盘搜索用的通配符（如 JBT 11509 与 JBT11509 两种写法）。"""
    norm = normalize_std_id(std_id)
    patterns: list[str] = []
    seen: set[str] = set()

    def add(p: str) -> None:
        if p not in seen:
            seen.add(p)
            patterns.append(p)

    parts = parse_std_parts(std_id)
    compact = norm.replace("—", "-").replace("－", "-")
    m = _STD_COMPACT.match(compact)
    if parts and parts[2]:
        # 带年份：只搜同年份，避免扫出历史版本
        prefix, num, year = parts
        add(f"*{norm}*.pdf")
        add(f"*{prefix}*{num}*{year}*.pdf")
        add(f"*{prefix} {num}*{year}*.pdf")
        add(f"*{num}*{year}*.pdf")
        return patterns

    add(f"*{norm}*.pdf")
    if m:
        p1, p2, num, year = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        add(f"*{p1}{p2}*{num}*.pdf")
        add(f"*{p1}{p2} {num}*.pdf")
        if year:
            add(f"*{p1}{p2}*{num}*{year}*.pdf")
            add(f"*{p1}{p2} {num}*{year}*.pdf")
            add(f"*{num}*{year}*.pdf")
    return patterns
