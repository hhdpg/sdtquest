"""问题仓储 SQLite 实现

实现 QuestionRepository 接口，负责问答记录的持久化。
"""

import json
from datetime import datetime, timedelta

from loguru import logger

from src.domain.enums import AnswerStatus, QuestionCategory
from src.domain.models import Answer, Question
from src.infrastructure.database import DatabaseManager, get_db_manager


class SQLiteQuestionRepository:
    """
    SQLite 问题仓储

    实现问答记录的 CRUD 操作。
    """

    def __init__(self, db_manager: DatabaseManager | None = None):
        """
        初始化问题仓储

        Args:
            db_manager: 数据库管理器，默认使用全局实例
        """
        self.db = db_manager or get_db_manager()
        logger.debug("SQLiteQuestionRepository 初始化")

    def save(self, question: Question, answer: Answer) -> None:
        """
        保存问答记录

        Args:
            question: 问题对象
            answer: 回答对象
        """
        try:
            sources_json = json.dumps(answer.sources, ensure_ascii=False)

            self.db.execute(
                """
                INSERT OR REPLACE INTO question_records
                (id, question, answer, category, sender_id, conversation_id,
                 confidence, status, sources, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer.id,
                    question.text,
                    answer.text,
                    answer.category.value,
                    question.sender_id,
                    question.conversation_id,
                    answer.confidence,
                    answer.status.value,
                    sources_json,
                    answer.created_at.isoformat(),
                ),
            )
            self.db.commit()
            logger.debug("问答记录已保存 | answer_id={}", answer.id)
        except Exception as e:
            logger.error("保存问答记录失败 | error={}", str(e))
            raise

    def find_by_id(self, answer_id: str) -> tuple[Question, Answer] | None:
        """
        根据回答 ID 查询记录

        Args:
            answer_id: 回答 ID

        Returns:
            (Question, Answer) 元组，未找到返回 None
        """
        try:
            cursor = self.db.execute(
                """
                SELECT * FROM question_records WHERE id = ?
                """,
                (answer_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            return self._row_to_question_answer(row)
        except Exception as e:
            logger.error("查询问答记录失败 | answer_id={} | error={}", answer_id, str(e))
            return None

    def find_recent(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> list[tuple[Question, Answer]]:
        """
        查询最近的问答记录

        Args:
            days: 查询最近 N 天
            limit: 最大返回数量

        Returns:
            (Question, Answer) 元组列表
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)

            cursor = self.db.execute(
                """
                SELECT * FROM question_records
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (cutoff.isoformat(), limit),
            )

            results = []
            for row in cursor.fetchall():
                qa = self._row_to_question_answer(row)
                if qa:
                    results.append(qa)

            logger.debug("查询最近问答记录 | days={} | count={}", days, len(results))
            return results
        except Exception as e:
            logger.error("查询最近问答记录失败 | error={}", str(e))
            return []

    def count_by_category(self, days: int = 7) -> dict[QuestionCategory, int]:
        """
        按分类统计问题数量

        Args:
            days: 统计最近 N 天

        Returns:
            分类到数量的映射
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)

            cursor = self.db.execute(
                """
                SELECT category, COUNT(*) as count
                FROM question_records
                WHERE created_at >= ?
                GROUP BY category
                """,
                (cutoff.isoformat(),),
            )

            result: dict[QuestionCategory, int] = {}
            for row in cursor.fetchall():
                cat_value = row["category"]
                try:
                    category = QuestionCategory(cat_value)
                    result[category] = row["count"]
                except ValueError:
                    logger.warning("未知的问题分类: {}", cat_value)

            logger.debug("分类统计完成 | days={} | result={}", days, result)
            return result
        except Exception as e:
            logger.error("分类统计失败 | error={}", str(e))
            return {}

    def find_unanswered(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> list[Question]:
        """
        查询未回答的问题

        Args:
            days: 查询最近 N 天
            limit: 最大返回数量

        Returns:
            未回答的问题列表
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)

            cursor = self.db.execute(
                """
                SELECT * FROM question_records
                WHERE created_at >= ? AND status IN (?, ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    cutoff.isoformat(),
                    AnswerStatus.NO_MATCH.value,
                    AnswerStatus.ERROR.value,
                ),
                limit,
            )

            results = []
            for row in cursor.fetchall():
                q = Question(
                    id=row["id"],
                    text=row["question"],
                    sender_id=row["sender_id"],
                    conversation_id=row["conversation_id"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                results.append(q)

            logger.debug("查询未回答问题 | days={} | count={}", days, len(results))
            return results
        except Exception as e:
            logger.error("查询未回答问题失败 | error={}", str(e))
            return []

    def get_top_questions(
        self,
        days: int = 7,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """
        获取高频问题

        Args:
            days: 统计最近 N 天
            limit: 返回数量

        Returns:
            (问题文本, 出现次数) 列表
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)

            cursor = self.db.execute(
                """
                SELECT question, COUNT(*) as count
                FROM question_records
                WHERE created_at >= ?
                GROUP BY question
                ORDER BY count DESC
                LIMIT ?
                """,
                (cutoff.isoformat(), limit),
            )

            results = [(row["question"], row["count"]) for row in cursor.fetchall()]
            logger.debug("获取高频问题 | days={} | count={}", days, len(results))
            return results
        except Exception as e:
            logger.error("获取高频问题失败 | error={}", str(e))
            return []

    def count_all(self, days: int | None = None) -> int:
        """
        统计问题总数

        Args:
            days: 统计最近 N 天，None 表示全部

        Returns:
            问题总数
        """
        try:
            if days:
                cutoff = datetime.now() - timedelta(days=days)
                cursor = self.db.execute(
                    "SELECT COUNT(*) FROM question_records WHERE created_at >= ?",
                    (cutoff.isoformat(),),
                )
            else:
                cursor = self.db.execute(
                    "SELECT COUNT(*) FROM question_records"
                )

            return cursor.fetchone()[0]
        except Exception as e:
            logger.error("统计问题总数失败 | error={}", str(e))
            return 0

    def _row_to_question_answer(
        self,
        row: sqlite3.Row,
    ) -> tuple[Question, Answer] | None:
        """
        将数据库行转换为 Question 和 Answer 对象

        Args:
            row: 数据库行

        Returns:
            (Question, Answer) 元组
        """
        try:
            sources = json.loads(row["sources"]) if row["sources"] else []

            # 解析分类
            category = QuestionCategory.GENERAL
            if row["category"]:
                try:
                    category = QuestionCategory(row["category"])
                except ValueError:
                    pass

            # 解析状态
            status = AnswerStatus.SUCCESS
            if row["status"]:
                try:
                    status = AnswerStatus(row["status"])
                except ValueError:
                    pass

            q = Question(
                id=row["id"],
                text=row["question"],
                sender_id=row["sender_id"],
                conversation_id=row["conversation_id"] or "",
                category=category,
                created_at=datetime.fromisoformat(row["created_at"]),
            )

            a = Answer(
                id=row["id"],
                question_id=row["id"],
                text=row["answer"] or "",
                sources=sources,
                confidence=row["confidence"] or 0.0,
                category=category,
                status=status,
                created_at=datetime.fromisoformat(row["created_at"]),
            )

            return q, a
        except Exception as e:
            logger.error("转换数据行失败 | error={}", str(e))
            return None
