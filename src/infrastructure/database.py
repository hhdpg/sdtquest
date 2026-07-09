"""SQLite 数据库管理模块

提供数据库连接管理、表初始化和索引创建功能。
采用单例模式确保全局只有一个数据库连接。
"""

import sqlite3
from pathlib import Path
from typing import Self

from loguru import logger

from src.config import settings


class DatabaseManager:
    """
    SQLite 数据库管理器

    单例模式，管理数据库连接和表初始化。

    Attributes:
        db_path: 数据库文件路径
        conn: 数据库连接
    """

    _instance: Self | None = None
    _initialized: bool = False

    def __new__(cls, db_path: str | None = None) -> Self:
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str | None = None):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径，默认从配置读取
        """
        if self._initialized:
            return

        self.db_path = db_path or settings.ANALYTICS_DB_PATH
        self.conn: sqlite3.Connection | None = None

        # 确保数据库目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        logger.info("DatabaseManager 初始化 | db_path={}", self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            sqlite3.Connection 对象
        """
        if self.conn is None:
            self.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # 允许多线程访问
            )
            # 设置行工厂，返回字典格式
            self.conn.row_factory = sqlite3.Row

            # ── 并发访问优化 ──
            # WAL 模式: 允许读写并发（多读 + 一写），避免默认 rollback journal
            # 模式下"读阻塞写、写阻塞读"的问题。适合问答记录与定时汇总并发写入场景。
            self.conn.execute("PRAGMA journal_mode=WAL")
            # busy_timeout: 遇到锁时等待指定毫秒数再报错，而非立即抛出
            # "database is locked"。5 秒对大多数并发场景足够。
            self.conn.execute("PRAGMA busy_timeout=5000")

            logger.debug("数据库连接已创建 | db_path={}", self.db_path)

        return self.conn

    def initialize_tables(self) -> None:
        """
        初始化数据库表

        创建问答记录表、每日汇总表和必要的索引。
        """
        conn = self.get_connection()

        # 问答记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS question_records (
                id              TEXT PRIMARY KEY,
                question        TEXT NOT NULL,
                answer          TEXT,
                category        TEXT,
                sender_id       TEXT NOT NULL,
                conversation_id TEXT,
                confidence      REAL DEFAULT 0.0,
                status          TEXT NOT NULL,
                sources         TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 每日汇总表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            DATE NOT NULL,
                category        TEXT NOT NULL,
                question_count  INTEGER DEFAULT 0,
                top_questions   TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, category)
            )
        """)

        # 创建索引
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_created_at
            ON question_records(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_category
            ON question_records(category)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_status
            ON question_records(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_sender
            ON question_records(sender_id)
        """)

        conn.commit()
        logger.info("数据库表初始化完成")

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        执行 SQL 查询

        Args:
            query: SQL 查询语句
            params: 查询参数

        Returns:
            Cursor 对象
        """
        conn = self.get_connection()
        return conn.execute(query, params)

    def commit(self) -> None:
        """提交事务"""
        if self.conn:
            self.conn.commit()

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        if cls._instance and cls._instance.conn:
            cls._instance.conn.close()
        cls._instance = None
        cls._initialized = False


# 获取全局数据库管理器实例
def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    return DatabaseManager()
