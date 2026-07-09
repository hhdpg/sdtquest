"""分析汇总服务模块。

本模块实现问答数据的统计分析、高频问题提取、日报生成等功能。

主要类:
- AnalyticsService: 分析汇总服务

典型用法:
    >>> from src.services.analytics_service import AnalyticsService
    >>> from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository
    >>> service = AnalyticsService(question_repo=repo)
    >>> summary = await service.get_summary(days=7)
    >>> top = await service.get_top_questions(days=7, limit=10)
    >>> report = await service.generate_daily_report()
"""

from datetime import date, datetime
from typing import Any

from loguru import logger

from src.domain.enums import QuestionCategory


# ============================================================================
# AnalyticsService
# ============================================================================

class AnalyticsService:
    """
    分析汇总服务类。

    负责问答数据的统计分析和报告生成，包括:
    - 问题分类统计（按天/周统计各分类数量）
    - 高频问题提取（TOP N）
    - 日报生成（Markdown 格式）
    - 可选推送到钉钉管理群

    Attributes:
        question_repo: 问题仓储，用于查询问答数据

    Example:
        >>> service = AnalyticsService(question_repo=repo)
        >>> summary = await service.get_summary(days=7)
        >>> print(summary["total"])
        50
        >>> report = await service.generate_daily_report()
        >>> print(report)
        '# 智能问答日报 - 2026-06-18\\n...'
    """

    def __init__(self, question_repo: Any):
        """
        初始化分析汇总服务。

        Args:
            question_repo: 问题仓储实例
        """
        self.question_repo = question_repo
        logger.info("AnalyticsService 初始化")

    async def get_summary(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        获取问题分类统计摘要。

        Args:
            days: 统计最近 N 天（默认 7 天）

        Returns:
            统计摘要字典，包含:
            - total: 问题总数
            - days: 统计天数
            - by_category: 各分类问题数量 {category_value: count}
            - avg_confidence: 平均置信度
            - success_rate: 成功回答比例
        """
        try:
            # 按分类统计
            category_counts = self.question_repo.count_by_category(days=days)

            # 查询全部记录以计算置信度和成功率
            records = self.question_repo.find_recent(days=days, limit=10000)

            # 计算平均置信度
            total_confidence = sum(a.confidence for _, a in records)
            avg_confidence = total_confidence / len(records) if records else 0.0

            # 计算成功回答比例
            success_count = sum(
                1 for _, a in records if a.is_successful()
            )
            success_rate = success_count / len(records) if records else 0.0

            summary = {
                "total": len(records),
                "days": days,
                "by_category": {
                    cat.value: count for cat, count in category_counts.items()
                },
                "avg_confidence": round(avg_confidence, 3),
                "success_rate": round(success_rate, 3),
            }

            logger.info(
                "获取统计摘要 | days={} | total={} | categories={}",
                days,
                summary["total"],
                summary["by_category"],
            )
            return summary

        except Exception as e:
            logger.error("获取统计摘要失败 | error={}", str(e))
            return {
                "total": 0,
                "days": days,
                "by_category": {},
                "avg_confidence": 0.0,
                "success_rate": 0.0,
            }

    async def get_top_questions(
        self,
        days: int = 7,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        获取高频问题列表。

        Args:
            days: 统计最近 N 天
            limit: 返回数量

        Returns:
            高频问题列表，每项包含:
            - question: 问题文本
            - count: 出现次数
            - rank: 排名（从 1 开始）
        """
        try:
            top_questions = self.question_repo.get_top_questions(
                days=days, limit=limit
            )

            result = [
                {"question": q, "count": c, "rank": i + 1}
                for i, (q, c) in enumerate(top_questions)
            ]

            logger.info(
                "获取高频问题 | days={} | count={}",
                days,
                len(result),
            )
            return result

        except Exception as e:
            logger.error("获取高频问题失败 | error={}", str(e))
            return []

    async def get_unanswered(
        self,
        days: int = 7,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        获取未回答的问题列表。

        这些是知识库未覆盖或处理出错的问题，
        可用于发现知识库的盲区。

        Args:
            days: 查询最近 N 天
            limit: 返回数量

        Returns:
            未回答的问题列表
        """
        try:
            questions = self.question_repo.find_unanswered(days=days, limit=limit)

            result = [
                {
                    "id": q.id,
                    "text": q.text,
                    "sender_id": q.sender_id,
                    "created_at": q.created_at.isoformat(),
                }
                for q in questions
            ]

            logger.info(
                "获取未回答问题 | days={} | count={}",
                days,
                len(result),
            )
            return result

        except Exception as e:
            logger.error("获取未回答问题失败 | error={}", str(e))
            return []

    async def generate_daily_report(
        self,
        days: int = 1,
        push_to_dingtalk: bool = False,
    ) -> str:
        """
        生成日报。

        生成 Markdown 格式的日报，包含:
        - 问题总数和分类统计
        - 高频问题 TOP 5
        - 未回答问题（知识库盲区）
        - 平均置信度和成功率

        Args:
            days: 统计天数（默认 1 天即日报，7 天即周报）
            push_to_dingtalk: 是否推送到钉钉（暂未实现，预留接口）

        Returns:
            Markdown 格式的日报文本
        """
        try:
            # 获取统计数据
            summary = await self.get_summary(days=days)
            top_questions = await self.get_top_questions(days=days, limit=5)
            unanswered = await self.get_unanswered(days=days, limit=5)

            # 构建报告
            report = self._build_report(summary, top_questions, unanswered, days)

            logger.info(
                "日报生成完成 | days={} | total={}",
                days,
                summary["total"],
            )

            # 可选：推送到钉钉（需要 DingTalkClient，目前仅生成文本）
            if push_to_dingtalk:
                logger.info("日报推送功能待集成（需要 DingTalkClient）")

            return report

        except Exception as e:
            logger.error("生成日报失败 | error={}", str(e))
            return f"# 日报生成失败\n\n错误信息: {e}"

    async def save_daily_summary(
        self,
        days: int = 1,
    ) -> None:
        """
        保存每日汇总数据到数据库。

        将分类统计结果写入 daily_summary 表，
        供后续查询和报告生成使用。

        Args:
            days: 统计天数
        """
        try:
            summary = await self.get_summary(days=days)
            top_questions = await self.get_top_questions(days=days, limit=10)

            today = date.today().isoformat()

            import json

            top_json = json.dumps(
                top_questions, ensure_ascii=False, default=str
            )

            # 通过 Repository 方法写入，避免直接访问 db 连接（分层违规）
            for category_value, count in summary["by_category"].items():
                self.question_repo.save_daily_summary(
                    date_str=today,
                    category=category_value,
                    question_count=count,
                    top_questions_json=top_json,
                )

            logger.info("每日汇总已保存 | date={} | categories={}", today, len(summary["by_category"]))

        except Exception as e:
            logger.error("保存每日汇总失败 | error={}", str(e))
            raise

    def _build_report(
        self,
        summary: dict[str, Any],
        top_questions: list[dict[str, Any]],
        unanswered: list[dict[str, Any]],
        days: int,
    ) -> str:
        """
        构建 Markdown 格式的日报。

        Args:
            summary: 统计摘要
            top_questions: 高频问题列表
            unanswered: 未回答问题列表
            days: 统计天数

        Returns:
            Markdown 格式的日报文本
        """
        today = date.today().strftime("%Y-%m-%d")
        period = "日报" if days == 1 else f"周报（近 {days} 天）"

        lines = [
            f"# 智能问答{period} — {today}",
            "",
            f"**统计周期**: 近 {days} 天",
            f"**问题总数**: {summary['total']}",
            "",
            "## 问题分类统计",
            "",
        ]

        # 分类统计表格
        category_labels = {
            QuestionCategory.OPERATION_GUIDE.value: "操作指南",
            QuestionCategory.PROCESS_INQUIRY.value: "流程咨询",
            QuestionCategory.ANOMALY_TROUBLESHOOT.value: "异常排查",
            QuestionCategory.GENERAL.value: "其他",
        }

        by_category = summary.get("by_category", {})
        if by_category:
            lines.append("| 分类 | 数量 | 占比 |")
            lines.append("|------|------|------|")
            total = summary["total"]
            for cat_value, count in by_category.items():
                cat_label = category_labels.get(cat_value, cat_value)
                ratio = (
                    f"{count / total * 100:.1f}%" if total > 0 else "0%"
                )
                lines.append(f"| {cat_label} | {count} | {ratio} |")
        else:
            lines.append("暂无数据")

        lines.extend([
            "",
            f"**平均置信度**: {summary.get('avg_confidence', 0):.2%}",
            f"**成功回答率**: {summary.get('success_rate', 0):.2%}",
            "",
            "## 高频问题 TOP 5",
            "",
        ])

        # 高频问题列表
        if top_questions:
            for item in top_questions:
                question_text = item["question"]
                # 截断过长的文本
                if len(question_text) > 60:
                    question_text = question_text[:57] + "..."
                lines.append(f"{item['rank']}. {question_text}（{item['count']}次）")
        else:
            lines.append("暂无数据")

        lines.extend([
            "",
            "## 未回答问题（知识库盲区）",
            "",
        ])

        # 未回答问题列表
        if unanswered:
            for item in unanswered[:5]:
                q_text = item["text"]
                if len(q_text) > 60:
                    q_text = q_text[:57] + "..."
                lines.append(f"- {q_text}")
        else:
            lines.append("无")

        lines.extend([
            "",
            "---",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])

        return "\n".join(lines)

    def _format_category_name(self, category_value: str) -> str:
        """
        格式化分类名称为中文。

        Args:
            category_value: 分类枚举值

        Returns:
            中文分类名称
        """
        name_map = {
            QuestionCategory.OPERATION_GUIDE.value: "操作指南",
            QuestionCategory.PROCESS_INQUIRY.value: "流程咨询",
            QuestionCategory.ANOMALY_TROUBLESHOOT.value: "异常排查",
            QuestionCategory.GENERAL.value: "其他",
        }
        return name_map.get(category_value, category_value)


# ============================================================================
# 服务层异常
# ============================================================================

class DailyReportError(Exception):
    """日报生成异常"""
    pass
