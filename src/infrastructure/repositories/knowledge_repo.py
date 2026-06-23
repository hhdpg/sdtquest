"""知识仓储 SQLite 实现

负责知识条目的元数据持久化（向量存储由 VectorStore 负责）。
"""

import json
import sqlite3
from datetime import datetime

from loguru import logger

from src.domain.enums import KnowledgeType
from src.domain.models import KnowledgeItem
from src.infrastructure.database import DatabaseManager, get_db_manager


class SQLiteKnowledgeRepository:
    """
    SQLite 知识仓储

    存储知识条目的元数据（标题、内容、标签等），
    向量数据由 VectorStore (ChromaDB) 管理。
    """

    def __init__(self, db_manager: DatabaseManager | None = None):
        """
        初始化知识仓储

        Args:
            db_manager: 数据库管理器，默认使用全局实例
        """
        self.db = db_manager or get_db_manager()
        self._ensure_table()
        logger.debug("SQLiteKnowledgeRepository 初始化")

    def _ensure_table(self) -> None:
        """确保知识条目表存在"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id          TEXT PRIMARY KEY,
                type        TEXT NOT NULL,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL,
                page_name   TEXT,
                page_path   TEXT,
                source_file TEXT,
                tags        TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_type
            ON knowledge_items(type)
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_page
            ON knowledge_items(page_name)
        """)
        self.db.commit()

    def save(self, item: KnowledgeItem) -> None:
        """
        保存知识条目

        Args:
            item: 知识条目
        """
        try:
            tags_json = json.dumps(item.tags, ensure_ascii=False)

            self.db.execute(
                """
                INSERT OR REPLACE INTO knowledge_items
                (id, type, title, content, page_name, page_path, source_file, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.type.value,
                    item.title,
                    item.content,
                    item.page_name,
                    item.page_path,
                    item.source_file,
                    tags_json,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
            self.db.commit()
            logger.debug("知识条目已保存 | id={} | title={}", item.id, item.title)
        except Exception as e:
            logger.error("保存知识条目失败 | id={} | error={}", item.id, str(e))
            raise

    def save_batch(self, items: list[KnowledgeItem]) -> int:
        """
        批量保存知识条目

        Args:
            items: 知识条目列表

        Returns:
            成功保存的数量
        """
        saved_count = 0
        for item in items:
            try:
                self.save(item)
                saved_count += 1
            except Exception as e:
                logger.warning("保存知识条目失败 | id={} | error={}", item.id, str(e))

        logger.info("批量保存完成 | total={} | saved={}", len(items), saved_count)
        return saved_count

    def find_by_id(self, item_id: str) -> KnowledgeItem | None:
        """
        根据 ID 查询知识条目

        Args:
            item_id: 知识条目 ID

        Returns:
            KnowledgeItem 对象，未找到返回 None
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_item(row)
        except Exception as e:
            logger.error("查询知识条目失败 | id={} | error={}", item_id, str(e))
            return None

    def find_by_type(self, item_type: KnowledgeType) -> list[KnowledgeItem]:
        """
        根据类型查询知识条目

        Args:
            item_type: 知识类型

        Returns:
            知识条目列表
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM knowledge_items WHERE type = ? ORDER BY created_at DESC",
                (item_type.value,),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("按类型查询失败 | type={} | error={}", item_type, str(e))
            return []

    def find_by_page(self, page_name: str) -> list[KnowledgeItem]:
        """
        根据页面名称查询知识条目

        Args:
            page_name: 页面名称

        Returns:
            知识条目列表
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM knowledge_items WHERE page_name = ? ORDER BY created_at DESC",
                (page_name,),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("按页面查询失败 | page={} | error={}", page_name, str(e))
            return []

    def find_all(self, limit: int = 1000) -> list[KnowledgeItem]:
        """
        查询所有知识条目

        Args:
            limit: 最大返回数量

        Returns:
            知识条目列表
        """
        try:
            cursor = self.db.execute(
                "SELECT * FROM knowledge_items ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [self._row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error("查询所有知识条目失败 | error={}", str(e))
            return []

    def delete(self, item_id: str) -> bool:
        """
        删除知识条目

        Args:
            item_id: 知识条目 ID

        Returns:
            是否删除成功
        """
        try:
            cursor = self.db.execute(
                "DELETE FROM knowledge_items WHERE id = ?",
                (item_id,),
            )
            self.db.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug("知识条目已删除 | id={}", item_id)
            return deleted
        except Exception as e:
            logger.error("删除知识条目失败 | id={} | error={}", item_id, str(e))
            return False

    def count(self) -> int:
        """
        统计知识条目总数

        Returns:
            总数
        """
        try:
            cursor = self.db.execute(
                "SELECT COUNT(*) FROM knowledge_items"
            )
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error("统计知识条目失败 | error={}", str(e))
            return 0

    def count_by_type(self) -> dict[KnowledgeType, int]:
        """
        按类型统计知识条目

        Returns:
            类型到数量的映射
        """
        try:
            cursor = self.db.execute(
                """
                SELECT type, COUNT(*) as count
                FROM knowledge_items
                GROUP BY type
                """
            )

            result: dict[KnowledgeType, int] = {}
            for row in cursor.fetchall():
                try:
                    item_type = KnowledgeType(row["type"])
                    result[item_type] = row["count"]
                except ValueError:
                    logger.warning("未知的知识类型: {}", row["type"])

            return result
        except Exception as e:
            logger.error("按类型统计失败 | error={}", str(e))
            return {}

    def get_stats(self) -> dict:
        """
        获取知识库统计信息

        Returns:
            统计信息字典
        """
        try:
            total = self.count()
            by_type = self.count_by_type()

            # 获取不同页面数
            cursor = self.db.execute(
                "SELECT COUNT(DISTINCT page_name) FROM knowledge_items WHERE page_name IS NOT NULL"
            )
            page_count = cursor.fetchone()[0]

            return {
                "total": total,
                "by_type": {t.value: c for t, c in by_type.items()},
                "page_count": page_count,
            }
        except Exception as e:
            logger.error("获取知识库统计失败 | error={}", str(e))
            return {"total": 0, "by_type": {}, "page_count": 0}

    def _row_to_item(self, row: sqlite3.Row) -> KnowledgeItem:
        """
        将数据库行转换为 KnowledgeItem

        Args:
            row: 数据库行

        Returns:
            KnowledgeItem 对象
        """
        tags = json.loads(row["tags"]) if row["tags"] else []

        item_type = KnowledgeType.MANUAL
        try:
            item_type = KnowledgeType(row["type"])
        except ValueError:
            pass

        return KnowledgeItem(
            id=row["id"],
            type=item_type,
            title=row["title"],
            content=row["content"],
            page_name=row["page_name"],
            page_path=row["page_path"],
            source_file=row["source_file"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
