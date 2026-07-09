"""问题汇总器模块。

本模块实现问题数据的统计汇总功能，包括:
- 按天/周统计各分类数量
- 提取高频问题 TOP N
- 标记未回答问题
- 活跃度统计

典型用法:
    >>> from src.analyzer.summarizer import QuestionSummarizer
    >>> from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository
    >>> summarizer = QuestionSummarizer(question_repo=repo)
    >>> summary = await summarizer.get_summary(days=7)
    >>> top_questions = await summarizer.get_top_questions(days=7, limit=10)
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.domain.enums import AnswerStatus, QuestionCategory


# ============================================================================
# 数据类定义
# ============================================================================

class CategoryStats:
    """
    分类统计数据。

    Attributes:
        category: 问题分类
        count: 问题数量
        percentage: 占比 (0.0-1.0)
        avg_confidence: 平均置信度
        success_rate: 成功回答比例
    """

    def __init__(
        self,
        category: QuestionCategory,
        count: int = 0,
        percentage: float = 0.0,
        avg_confidence: float = 0.0,
        success_rate: float = 0.0,
    ):
        self.category = category
        self.count = count
        self.percentage = percentage
        self.avg_confidence = avg_confidence
        self.success_rate = success_rate

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "category": self.category.value,
            "category_name": self.category_name,
            "count": self.count,
            "percentage": round(self.percentage, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "success_rate": round(self.success_rate, 3),
        }

    @property
    def category_name(self) -> str:
        """获取分类中文名"""
        names = {
            QuestionCategory.OPERATION_GUIDE: "操作指南",
            QuestionCategory.PROCESS_INQUIRY: "流程咨询",
            QuestionCategory.ANOMALY_TROUBLESHOOT: "异常排查",
            QuestionCategory.GENERAL: "其他",
        }
        return names.get(self.category, "未知")


class SummaryResult:
    """
    汇总结果。

    Attributes:
        total: 问题总数
        days: 统计天数
        start_date: 开始日期
        end_date: 结束日期
        category_stats: 各分类统计
        avg_confidence: 整体平均置信度
        success_rate: 整体成功回答比例
        active_users: 活跃用户数
    """

    def __init__(
        self,
        total: int = 0,
        days: int = 7,
        category_stats: list[CategoryStats] | None = None,
        avg_confidence: float = 0.0,
        success_rate: float = 0.0,
        active_users: int = 0,
    ):
        self.total = total
        self.days = days
        self.start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        self.end_date = datetime.now().strftime("%Y-%m-%d")
        self.category_stats = category_stats or []
        self.avg_confidence = avg_confidence
        self.success_rate = success_rate
        self.active_users = active_users

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total": self.total,
            "days": self.days,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "by_category": {
                stat.category.value: stat.to_dict() for stat in self.category_stats
            },
            "avg_confidence": round(self.avg_confidence, 3),
            "success_rate": round(self.success_rate, 3),
            "active_users": self.active_users,
        }


# ============================================================================
# 问题汇总器
# ============================================================================

class QuestionSummarizer:
    """
    问题汇总器。

    负责问答数据的统计分析和汇总，包括:
    - 按分类统计问题数量
    - 计算平均置信度和成功率
    - 提取高频问题
    - 标记未回答问题
    - 统计活跃用户

    Attributes:
        question_repo: 问题仓储

    Example:
        >>> summarizer = QuestionSummarizer(question_repo=repo)
        >>> summary = await summarizer.get_summary(days=7)
        >>> print(f"总问题数: {summary.total}")
    """

    def __init__(self, question_repo: Any):
        """
        初始化问题汇总器。

        Args:
            question_repo: 问题仓储实例
        """
        self.question_repo = question_repo
        logger.info("QuestionSummarizer 初始化")

    async def get_summary(
        self,
        days: int = 7,
    ) -> SummaryResult:
        """
        获取问题统计摘要。

        Args:
            days: 统计最近 N 天

        Returns:
            汇总结果
        """
        logger.info("获取统计摘要 | days={}", days)

        try:
            # 查询所有记录
            records = self.question_repo.find_recent(days=days, limit=10000)

            if not records:
                return SummaryResult(total=0, days=days)

            # 按分类统计
            category_counter: Counter[QuestionCategory] = Counter()
            category_confidence: dict[QuestionCategory, list[float]] = {
                cat: [] for cat in QuestionCategory
            }
            category_success: dict[QuestionCategory, list[bool]] = {
                cat: [] for cat in QuestionCategory
            }
            all_confidence: list[float] = []
            all_success: list[bool] = []
            unique_users: set[str] = set()

            for question, answer in records:
                category = question.category or QuestionCategory.GENERAL
                category_counter[category] += 1

                # 置信度
                category_confidence[category].append(answer.confidence)
                all_confidence.append(answer.confidence)

                # 成功率
                is_success = answer.status == AnswerStatus.SUCCESS
                category_success[category].append(is_success)
                all_success.append(is_success)

                # 活跃用户
                if question.sender_id:
                    unique_users.add(question.sender_id)

            # 构建分类统计
            total = len(records)
            category_stats = []

            for category in QuestionCategory:
                count = category_counter.get(category, 0)
                if count == 0:
                    continue

                conf_list = category_confidence.get(category, [])
                succ_list = category_success.get(category, [])

                avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.0
                succ_rate = sum(succ_list) / len(succ_list) if succ_list else 0.0
                percentage = count / total if total > 0 else 0.0

                category_stats.append(CategoryStats(
                    category=category,
                    count=count,
                    percentage=percentage,
                    avg_confidence=avg_conf,
                    success_rate=succ_rate,
                ))

            # 按数量排序
            category_stats.sort(key=lambda x: x.count, reverse=True)

            # 整体统计
            overall_avg_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0.0
            overall_success_rate = sum(all_success) / len(all_success) if all_success else 0.0

            result = SummaryResult(
                total=total,
                days=days,
                category_stats=category_stats,
                avg_confidence=overall_avg_confidence,
                success_rate=overall_success_rate,
                active_users=len(unique_users),
            )

            logger.info(
                "统计摘要完成 | total={} | categories={} | active_users={}",
                total,
                len(category_stats),
                result.active_users,
            )

            return result

        except Exception as e:
            logger.error("获取统计摘要失败 | error={}", str(e))
            return SummaryResult(total=0, days=days)

    async def get_top_questions(
        self,
        days: int = 7,
        limit: int = 10,
        min_count: int = 2,
    ) -> list[dict[str, Any]]:
        """
        获取高频问题列表。

        Args:
            days: 统计最近 N 天
            limit: 返回数量
            min_count: 最小出现次数（过滤低频问题）

        Returns:
            高频问题列表，按出现次数降序
        """
        logger.info("获取高频问题 | days={} | limit={}", days, limit)

        try:
            # 使用仓储提供的方法
            top_list = self.question_repo.get_top_questions(days=days, limit=limit * 2)

            # 过滤并构建结果
            results = []
            rank = 1

            for question_text, count in top_list:
                if count < min_count:
                    continue

                results.append({
                    "question": question_text,
                    "count": count,
                    "rank": rank,
                })

                rank += 1
                if len(results) >= limit:
                    break

            logger.info("高频问题获取完成 | count={}", len(results))
            return results

        except Exception as e:
            logger.error("获取高频问题失败 | error={}", str(e))
            return []

    async def get_unanswered(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        获取未回答的问题列表。

        未回答的问题包括:
        - 状态为 NO_MATCH（知识库未匹配）
        - 状态为 ERROR（处理出错）

        这些问题可用于发现知识库的盲区。

        Args:
            days: 查询最近 N 天
            limit: 返回数量

        Returns:
            未回答问题列表
        """
        logger.info("获取未回答问题 | days={} | limit={}", days, limit)

        try:
            questions = self.question_repo.find_unanswered(days=days, limit=limit)

            results = [
                {
                    "id": q.id,
                    "text": q.text,
                    "sender_id": q.sender_id,
                    "created_at": q.created_at.isoformat(),
                }
                for q in questions
            ]

            logger.info("未回答问题获取完成 | count={}", len(results))
            return results

        except Exception as e:
            logger.error("获取未回答问题失败 | error={}", str(e))
            return []

    async def get_active_users(
        self,
        days: int = 7,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        获取活跃用户列表。

        Args:
            days: 统计最近 N 天
            limit: 返回数量

        Returns:
            活跃用户列表，按提问次数降序
        """
        logger.info("获取活跃用户 | days={} | limit={}", days, limit)

        try:
            # 查询所有记录
            records = self.question_repo.find_recent(days=days, limit=10000)

            if not records:
                return []

            # 统计每个用户的提问次数
            user_counter: Counter[str] = Counter()

            for question, _ in records:
                if question.sender_id:
                    user_counter[question.sender_id] += 1

            # 构建结果
            results = []
            rank = 1

            for user_id, count in user_counter.most_common(limit):
                results.append({
                    "user_id": user_id,
                    "question_count": count,
                    "rank": rank,
                })
                rank += 1

            logger.info("活跃用户获取完成 | count={}", len(results))
            return results

        except Exception as e:
            logger.error("获取活跃用户失败 | error={}", str(e))
            return []

    async def get_trend(
        self,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """
        获取问题趋势数据（按天统计）。

        Args:
            days: 统计最近 N 天

        Returns:
            每日统计数据列表
        """
        logger.info("获取问题趋势 | days={}", days)

        try:
            # 查询所有记录
            records = self.question_repo.find_recent(days=days, limit=10000)

            if not records:
                return []

            # 按日期统计
            daily_counter: Counter[str] = Counter()

            for question, _ in records:
                date_str = question.created_at.strftime("%Y-%m-%d")
                daily_counter[date_str] += 1

            # 构建结果（按日期排序）
            results = []
            start_date = datetime.now() - timedelta(days=days)

            for i in range(days):
                date = start_date + timedelta(days=i + 1)
                date_str = date.strftime("%Y-%m-%d")
                count = daily_counter.get(date_str, 0)

                results.append({
                    "date": date_str,
                    "count": count,
                })

            logger.info("问题趋势获取完成 | days={}", days)
            return results

        except Exception as e:
            logger.error("获取问题趋势失败 | error={}", str(e))
            return []
