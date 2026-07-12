"""应用运行参数（端口、数据库、缓存等，不含磁盘路径）。"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
OPEN_BROWSER = os.getenv("OPEN_BROWSER", "true").lower() in ("1", "true", "yes")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "mydate")
DB_BACKEND = os.getenv("DB_BACKEND", "auto").lower()

CACHE_VERSION = os.getenv("CACHE_VERSION", "2.3.0")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
CACHE_MAX_MEMORY = int(os.getenv("CACHE_MAX_MEMORY", "800"))
CACHE_TTL_SEARCH = int(os.getenv("CACHE_TTL_SEARCH", "1800"))
CACHE_TTL_SUGGEST = int(os.getenv("CACHE_TTL_SUGGEST", "600"))
CACHE_TTL_DETAIL = int(os.getenv("CACHE_TTL_DETAIL", "7200"))
CACHE_TTL_DISK = int(os.getenv("CACHE_TTL_DISK", "86400"))

ES_ENABLED = os.getenv("ES_ENABLED", "auto").lower()
ES_SCHEME = os.getenv("ES_SCHEME", "http")
ES_HOST = os.getenv("ES_HOST", "127.0.0.1")
ES_PORT = int(os.getenv("ES_PORT", "9200"))
ES_INDEX = os.getenv("ES_INDEX", "standards")
ES_USER = os.getenv("ES_USER", "")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")

APP_VERSION = "3.1.0"

# 术语 AI 语义扩展（OpenAI 兼容，如 DeepSeek）
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() in ("1", "true", "yes")
AI_API_BASE = os.getenv("AI_API_BASE", "https://api.deepseek.com/v1").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "deepseek-chat")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
