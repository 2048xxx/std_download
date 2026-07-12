"""测试连接项目原本 MySQL 库 mydate。"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pymysql

from settings import MYSQL_DATABASE, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER

CORE_TABLES = (
    "std_base",
    "std_filepath",
    "std_term",
    "std_terms",
    "term_dict",
    "unit_dict",
    "area_dict",
    "std_unit_relation",
)


def main() -> int:
    print("=" * 50)
    print("  MySQL 连接测试")
    print("=" * 50)
    print(f"  主机: {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"  用户: {MYSQL_USER}")
    print(f"  数据库: {MYSQL_DATABASE}")
    print(f"  密码: {'已配置' if MYSQL_PASSWORD else '未配置（.env 中设置 MYSQL_PASSWORD）'}")
    print()

    if not MYSQL_PASSWORD:
        print("[失败] 未配置 MYSQL_PASSWORD")
        print("  请在项目根目录创建 .env，例如：")
        print("    MYSQL_PASSWORD=你的root密码")
        print("  可参考 config.example.env")
        return 1

    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            connect_timeout=8,
        )
    except pymysql.err.OperationalError as exc:
        code, msg = exc.args
        print(f"[失败] 无法连接: ({code}) {msg}")
        if code == 1045:
            print("  → 用户名或密码错误")
        elif code == 1049:
            print(f"  → 数据库 {MYSQL_DATABASE} 不存在，请确认库名")
        elif code == 2003:
            print("  → MySQL 服务未启动或端口不对")
        return 1

    try:
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        print(f"[成功] 已连接 MySQL {version}")

        cur.execute("SHOW TABLES")
        tables = {r[0] for r in cur.fetchall()}
        print(f"  表数量: {len(tables)}")

        for name in CORE_TABLES:
            if name in tables:
                cur.execute(f"SELECT COUNT(*) FROM `{name}`")
                print(f"  {name}: {cur.fetchone()[0]:,} 行")

        if "std_base" in tables:
            cur.execute("SELECT std_id, std_chinesename FROM std_base LIMIT 3")
            print("  样例标准:")
            for row in cur.fetchall():
                print(f"    - {row[0]}  {row[1] or ''}")

        print()
        print("连接正常。重启 启动ZKBZ.bat 后系统将优先使用 MySQL。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
