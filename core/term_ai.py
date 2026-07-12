"""术语检索的 AI 语义扩展（OpenAI 兼容接口，可选）。"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from config import AI_API_BASE, AI_API_KEY, AI_ENABLED, AI_MODEL, AI_TIMEOUT

_LOCAL_SYNONYMS: dict[str, list[str]] = {
    "铅笔": ["石墨笔", "木质铅笔", "自动铅笔", "书写笔"],
    "牙膏": ["洁齿剂", "口腔清洁", "刷牙"],
    "阀门": ["阀", "截止阀", "球阀", "闸阀"],
    "煤矿": ["矿井", "煤炭", "采煤", "矿山"],
    "健康": ["卫生", "医疗", "保健", "公共卫生"],
    "数据元": ["数据元素", "元数据", "数据单元"],
    "个人信息": ["隐私信息", "个人数据", "用户数据"],
    "网络安全": ["信息安全", "网络防护", "等级保护"],
}


def ai_ready() -> bool:
    return AI_ENABLED and bool(AI_API_KEY)


def _local_expand(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"query": "", "keywords": [], "semantic_note": "", "source": "none"}

    keywords = [q]
    seen = {q}
    for key, syns in _LOCAL_SYNONYMS.items():
        if key in q or q in key:
            for s in syns:
                if s not in seen:
                    seen.add(s)
                    keywords.append(s)
        for s in syns:
            if s in q or q in s:
                if key not in seen:
                    seen.add(key)
                    keywords.append(key)

    return {
        "query": q,
        "keywords": keywords[:12],
        "semantic_note": "已使用本地同义词扩展（配置 AI_API_KEY 可启用语义扩展）",
        "source": "local",
    }


def _parse_ai_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _call_chat(prompt: str) -> str:
    url = f"{AI_API_BASE}/chat/completions"
    payload = {
        "model": AI_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是国家标准术语检索助手。根据用户输入的术语，输出 JSON："
                    '{"keywords":["相关检索词"],"semantic_note":"简短说明"}。'
                    "keywords 须包含原词及同义词、近义词、英文缩写（如有），最多 12 个。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def expand_term_semantics(query: str, *, use_ai: bool = True) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"query": "", "keywords": [], "semantic_note": "", "source": "none"}

    if not use_ai or not ai_ready():
        return _local_expand(q)

    try:
        raw = _call_chat(f"术语：{q}")
        parsed = _parse_ai_json(raw) or {}
        keywords = [str(k).strip() for k in (parsed.get("keywords") or []) if str(k).strip()]
        if q not in keywords:
            keywords.insert(0, q)
        deduped: list[str] = []
        seen: set[str] = set()
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)
        return {
            "query": q,
            "keywords": deduped[:12],
            "semantic_note": str(parsed.get("semantic_note") or "").strip(),
            "source": "ai",
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, json.JSONDecodeError):
        out = _local_expand(q)
        out["semantic_note"] = (out.get("semantic_note") or "") + "（AI 不可用，已回退本地扩展）"
        return out
