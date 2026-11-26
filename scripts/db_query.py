"""零依赖 MySQL 查询工具（纯标准库实现）。

为什么不用 pymysql / mysql-connector：
    本项目要部署到测试服务器与正式环境，那两个包不在生产依赖里。
    为了排查问题而在 pyproject.toml 里加依赖，会让生产镜像多带一个
    永远用不到、却可能被误用的数据库驱动。这里用 socket + hashlib
    手写 MySQL 文本协议的最小实现，任何有 Python 3.11 的机器都能跑。

安全性约定：
    · 只允许 SELECT / SHOW / DESC / EXPLAIN，写操作直接拒绝
    · 连接信息单独放 .env.db（已被 .gitignore 忽略），不写进代码
    · 查询结果默认截断输出，避免大表把终端刷爆

为什么单独一个 .env.db 而不是写进 .env：
    主配置 src/config.py 的 Settings 是 extra=forbid 的严格模型，
    .env 里多出任何未声明键都会让应用启动失败。
    数据库排查配置只在运维时用，不该影响应用启动，故单独存放。

用法:
    # 列连接信息（不含密码）
    python3 scripts/db_query.py env

    # 查表结构
    python3 scripts/db_query.py desc us_open_config

    # 查数据（自动补 LIMIT）
    python3 scripts/db_query.py query "select app_id, status from us_open_config limit 20"

    # 指定数据源（默认 default，另有 us0..us5 分片库）
    python3 scripts/db_query.py query "show tables" --ds us0

配置文件 .env.db（从 .env.db.example 复制后填写）:
    SIT_DB_HOST / SIT_DB_PORT / SIT_DB_USER / SIT_DB_PASSWORD / SIT_DB_NAME
    SIT_DB_SHARD_HOST / SIT_DB_SHARD_NAME_PREFIX   # 分片库，如 united_store_00
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import socket
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# 只读语句白名单：任何写操作在发到服务器前就被拦下
READONLY_PREFIXES = ("select", "show", "desc", "describe", "explain", "with")
# 这些词出现在语句里就拒绝——即使用 with 或子查询包装也挡掉
FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "truncate", "alter",
    "create", "replace", "grant", "revoke", "rename", "load",
)

MAX_ROWS_DEFAULT = 50
MAX_CELL_CHARS = 120


# ── 配置读取（不引入 pydantic，避免和主配置耦合） ──────────

def load_env(path: Path | None = None) -> dict[str, str]:
    """
    读取 .env.db 里的键值对。

    只做最小解析：忽略注释与空行，去掉包裹的引号。
    不覆盖已存在的进程环境变量（进程环境优先，便于 CI/临时覆盖）。

    Args:
        path: 配置文件路径，默认项目根目录下的 .env.db

    Returns:
        键值字典
    """
    env_path = path or (PROJECT_ROOT / ".env.db")
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        result[key.strip()] = value
    for key in list(result):
        if key in os.environ:
            result[key] = os.environ[key]
    return result


def resolve_datasource(env: dict[str, str], name: str) -> dict:
    """
    把数据源代号解析成连接参数。

    Args:
        env: load_env() 的结果
        name: default / us0 / us1 ... / us5

    Returns:
        含 host/port/user/password/database 的字典

    Raises:
        SystemExit: 配置缺失时直接退出并给出提示
    """
    if name == "default":
        host = env.get("SIT_DB_HOST", "")
        database = env.get("SIT_DB_NAME", "united_store")
    elif re.fullmatch(r"us[0-5]", name):
        host = env.get("SIT_DB_SHARD_HOST", "")
        database = f"{env.get('SIT_DB_SHARD_NAME_PREFIX', 'united_store')}_{name[2:].zfill(2)}"
    else:
        sys.exit(f"未知数据源: {name}（可用 default/us0..us5）")

    conf = {
        "host": host,
        "port": int(env.get("SIT_DB_PORT", "3306")),
        "user": env.get("SIT_DB_USER", ""),
        "password": env.get("SIT_DB_PASSWORD", ""),
        "database": database,
    }
    missing = [k for k in ("host", "user", "password") if not conf[k]]
    if missing:
        sys.exit(
            f"缺少连接配置: {', '.join(missing)}\n"
            f"请把 .env.db.example 复制为 .env.db 并填写 SIT_DB_HOST / SIT_DB_USER / SIT_DB_PASSWORD"
        )
    return conf


# ── MySQL 文本协议的最小实现 ────────────────────────────

class MySQLClient:
    """
    极简 MySQL 客户端（只支持查询与结果集解析）。

    实现范围刻意收窄：够查表结构和少量数据即可，
    不做预处理语句、不做多结果集、不做 SSL。
    """

    def __init__(self, host: str, user: str, password: str, database: str,
                 port: int = 3306, timeout: int = 10):
        self.timeout = timeout
        self.seq = 0
        self._sock = socket.create_connection((host, port), timeout)
        self._sock.settimeout(timeout)
        _, greeting = self._read_packet()
        seed = self._parse_greeting(greeting)
        self._authenticate(user, password, database, seed)

    # ── 底层收发 ──

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("服务端断开连接")
            buf += chunk
        return buf

    def _read_packet(self) -> tuple[int, bytes]:
        header = self._recv_exact(4)
        length = header[0] | (header[1] << 8) | (header[2] << 16)
        self.seq = (header[3] + 1) & 0xFF
        return header[3], self._recv_exact(length)

    def _send_packet(self, payload: bytes) -> None:
        header = struct.pack("<I", len(payload))[:3] + bytes([self.seq])
        self._sock.sendall(header + payload)
        self.seq = (self.seq + 1) & 0xFF

    # ── 握手与认证 ──

    @staticmethod
    def _parse_greeting(body: bytes) -> bytes:
        """从握手包里取出 20 字节的 auth seed"""
        i = 1
        i = body.index(b"\x00", i) + 1        # 跳过版本号
        i += 4                                 # connection id
        seed1 = body[i:i + 8]
        i += 9                                 # seed1 + 填充
        i += 2 + 1 + 2 + 2                     # 能力低位/字符集/状态/能力高位
        auth_len = body[i]
        i += 1 + 10
        seed2_len = max(13, auth_len - 8)
        seed2 = body[i:i + seed2_len].rstrip(b"\x00")
        return seed1 + seed2

    def _authenticate(self, user: str, password: str, database: str, seed: bytes) -> None:
        raw_pwd = password.encode("utf-8")
        s1 = hashlib.sha1(raw_pwd).digest()
        s2 = hashlib.sha1(s1).digest()
        s3 = hashlib.sha1(seed + s2).digest()
        auth_resp = bytes(a ^ b for a, b in zip(s1, s3)) if raw_pwd else b""

        # LONG_PASSWORD|LONG_FLAG|CONNECT_WITH_DB|PROTOCOL_41
        # |TRANSACTIONS|SECURE_CONNECTION|PLUGIN_AUTH|MULTI_RESULTS
        flags = 1 | 4 | 8 | 512 | 8192 | 32768 | (1 << 19) | (1 << 17)
        payload = struct.pack("<I", flags)
        payload += struct.pack("<I", 16 * 1024 * 1024)
        payload += b"\x21" + b"\x00" * 23
        payload += user.encode() + b"\x00"
        payload += bytes([len(auth_resp)]) + auth_resp
        payload += database.encode() + b"\x00"
        payload += b"mysql_native_password\x00"
        self._send_packet(payload)

        _, resp = self._read_packet()
        if resp and resp[0] == 0xFF:
            raise RuntimeError("认证失败: " + resp[3:].decode("utf-8", "ignore"))
        if resp and resp[0] == 0xFE:
            raise RuntimeError("服务端要求切换认证插件，当前实现不支持")

    # ── 查询 ──

    @staticmethod
    def _read_lenenc_str(buf: bytes, pos: int) -> tuple[str, int]:
        length = buf[pos]
        pos += 1
        return buf[pos:pos + length].decode("utf-8", "ignore"), pos + length

    @classmethod
    def _column_name(cls, body: bytes) -> str:
        """列定义包里第 5 个 lenenc 字符串是列名"""
        pos = 0
        name = ""
        for idx in range(5):
            value, pos = cls._read_lenenc_str(body, pos)
            if idx == 4:
                name = value
        return name

    @classmethod
    def _parse_row(cls, body: bytes, ncols: int) -> list[str | None]:
        pos = 0
        values: list[str | None] = []
        for _ in range(ncols):
            byte = body[pos]
            if byte == 0xFB:
                values.append(None)
                pos += 1
                continue
            if byte < 0xFB:
                length = byte
                pos += 1
            elif byte == 0xFC:
                length = struct.unpack("<H", body[pos + 1:pos + 3])[0]
                pos += 3
            elif byte == 0xFD:
                length = int.from_bytes(body[pos + 1:pos + 4], "little")
                pos += 4
            else:  # 0xFE
                length = struct.unpack("<Q", body[pos + 1:pos + 9])[0]
                pos += 9
            values.append(body[pos:pos + length].decode("utf-8", "ignore"))
            pos += length
        return values

    def query(self, sql: str) -> tuple[list[str], list[list[str | None]]]:
        """
        执行只读 SQL。

        Args:
            sql: 单条只读语句

        Returns:
            (列名列表, 数据行列表)
        """
        self.seq = 0
        self._send_packet(b"\x03" + sql.encode("utf-8"))
        _, first = self._read_packet()
        if first and first[0] == 0xFF:
            raise RuntimeError(first[3:].decode("utf-8", "ignore"))

        if not first or first[0] == 0:
            return [], []          # 非结果集语句（如无结果集响应）

        ncols = first[0]
        columns: list[str] = []
        for _ in range(ncols):
            _, body = self._read_packet()
            columns.append(self._column_name(body))

        _, marker = self._read_packet()      # 字段定义后的 EOF
        rows: list[list[str | None]] = []
        if marker[0] != 0xFE:
            rows.append(self._parse_row(marker, ncols))

        while True:
            _, body = self._read_packet()
            if body[0] == 0xFE and len(body) < 9:
                break
            if body[0] == 0xFF:
                raise RuntimeError(body[3:].decode("utf-8", "ignore"))
            rows.append(self._parse_row(body, ncols))
        return columns, rows

    def close(self) -> None:
        try:
            self.seq = 0
            self._send_packet(b"\x01")       # COM_QUIT
        except OSError:
            pass
        finally:
            self._sock.close()


# ── SQL 安全检查 ────────────────────────────────────────

def assert_readonly(sql: str) -> str:
    """
    校验语句是只读的，并补上默认 LIMIT。

    Args:
        sql: 用户输入的语句

    Returns:
        规范化后可执行的语句

    Raises:
        SystemExit: 语句含写操作或被判定为非只读
    """
    cleaned = sql.strip().rstrip(";").strip()
    lowered = cleaned.lower()

    if not lowered.startswith(READONLY_PREFIXES):
        sys.exit(f"只允许查询语句（{', '.join(READONLY_PREFIXES)}），已拒绝执行")

    for word in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", lowered):
            sys.exit(f"语句包含写操作关键字 `{word}`，已拒绝执行")

    # select 没写 limit 时补一个，防止把大表全拉下来
    if lowered.startswith("select") and not re.search(r"\blimit\b", lowered):
        cleaned += f" LIMIT {MAX_ROWS_DEFAULT}"
    return cleaned


# ── 输出 ───────────────────────────────────────────────

def print_table(columns: list[str], rows: list[list[str | None]]) -> None:
    """按列宽对齐输出，超长单元格截断"""
    if not columns:
        print("（无结果）")
        return

    def clip(value: str | None) -> str:
        text = "NULL" if value is None else str(value).replace("\n", " ")
        return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "…"

    display = [[clip(v) for v in row] for row in rows]
    widths = [len(c) for c in columns]
    for row in display:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    print(header)
    print("-+-".join("-" * w for w in widths))
    for row in display:
        print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    print(f"\n共 {len(rows)} 行")


# ── 命令入口 ────────────────────────────────────────────

def cmd_env(env: dict[str, str], _args) -> None:
    """打印当前解析出的连接信息（密码打码）"""
    for name in ("default", "us0", "us1", "us2", "us3", "us4", "us5"):
        try:
            conf = resolve_datasource(env, name)
        except SystemExit:
            continue
        pwd = conf["password"]
        masked = f"{pwd[:2]}***{pwd[-2:]}" if len(pwd) > 6 else "***"
        print(f"{name:<8} {conf['user']}@{conf['host']}:{conf['port']}"
              f"/{conf['database']}  pwd={masked}")


def cmd_query(env: dict[str, str], args) -> None:
    """执行一条只读查询"""
    sql = assert_readonly(args.sql)
    conf = resolve_datasource(env, args.ds)
    client = MySQLClient(**conf, timeout=args.timeout)
    try:
        columns, rows = client.query(sql)
        if args.limit and len(rows) > args.limit:
            rows = rows[:args.limit]
        print_table(columns, rows)
    finally:
        client.close()


def cmd_desc(env: dict[str, str], args) -> None:
    """查看表结构"""
    if not re.fullmatch(r"[A-Za-z0-9_$]+", args.table):
        sys.exit("表名只允许字母、数字、下划线和 $")
    cmd_query(env, argparse.Namespace(
        sql=f"desc `{args.table}`", ds=args.ds,
        limit=0, timeout=args.timeout,
    ))


def cmd_tables(env: dict[str, str], args) -> None:
    """列出表名，可用 --like 过滤"""
    sql = "show tables"
    if args.like:
        if not re.fullmatch(r"[A-Za-z0-9_%]+", args.like):
            sys.exit("过滤词只允许字母、数字、下划线和 %")
        sql += f" like '{args.like}'"
    cmd_query(env, argparse.Namespace(
        sql=sql, ds=args.ds, limit=0, timeout=args.timeout,
    ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="零依赖 MySQL 只读查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ds", default="default",
                        help="数据源：default 或 us0..us5（默认 default）")
    common.add_argument("--timeout", type=int, default=10, help="连接/读取超时秒数")

    p_env = sub.add_parser("env", help="查看连接配置（密码打码）")
    p_env.set_defaults(func=cmd_env)

    p_query = sub.add_parser("query", parents=[common], help="执行只读 SQL")
    p_query.add_argument("sql", help="SELECT / SHOW / DESC / EXPLAIN 语句")
    p_query.add_argument("--limit", type=int, default=0, help="客户端截断行数，0 不截断")
    p_query.set_defaults(func=cmd_query)

    p_desc = sub.add_parser("desc", parents=[common], help="查看表结构")
    p_desc.add_argument("table", help="表名")
    p_desc.set_defaults(func=cmd_desc)

    p_tables = sub.add_parser("tables", parents=[common], help="列出表名")
    p_tables.add_argument("--like", default="", help="表名过滤，支持 %% 通配")
    p_tables.set_defaults(func=cmd_tables)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    env = load_env()
    if not env:
        sys.exit(
            "未找到 .env.db：\n"
            "  1. cp .env.db.example .env.db\n"
            "  2. 按目标环境填写 SIT_DB_HOST / SIT_DB_USER / SIT_DB_PASSWORD"
        )
    args.func(env, args)


if __name__ == "__main__":
    main()
