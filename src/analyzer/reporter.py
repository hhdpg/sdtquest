"""报告生成器模块。

本模块实现 Markdown 格式的日报/周报生成功能，支持:
- 生成问题统计报告
- 高频问题 TOP N
- 未回答问题（知识库盲区）
- 推送到钉钉管理群

典型用法:
    >>> from src.analyzer.reporter import ReportGenerator
    >>> from src.analyzer.summarizer import QuestionSummarizer
    >>> reporter = ReportGenerator(summarizer=summarizer)
    >>> report = await reporter.generate_daily_report()
    >>> print(report)
"""

from datetime import date, datetime
from typing import Any

from loguru import logger

from src.analyzer.summarizer import QuestionSummarizer, SummaryResult
from src.domain.enums import QuestionCategory


# ============================================================================
# 报告生成器
# ============================================================================

class ReportGenerator:
    """
    报告生成器。

    基于汇总数据生成 Markdown 格式的日报/周报。

    Attributes:
        summarizer: 问题汇总器
        dingtalk_client: 钉钉客户端（可选，用于推送报告）

    Example:
        >>> reporter = ReportGenerator(summarizer=summarizer)
        >>> report = await reporter.generate_daily_report()
    """

    # 分类中文名映射
    CATEGORY_NAMES: dict[QuestionCategory, str] = {
        QuestionCategory.OPERATION_GUIDE: "操作指南",
        QuestionCategory.PROCESS_INQUIRY: "流程咨询",
        QuestionCategory.ANOMALY_TROUBLESHOOT: "异常排查",
        QuestionCategory.GENERAL: "其他",
    }

    def __init__(
        self,
        summarizer: QuestionSummarizer,
        dingtalk_client: Any = None,
    ):
        """
        初始化报告生成器。

        Args:
            summarizer: 问题汇总器实例
            dingtalk_client: 钉钉客户端实例（可选）
        """
        self.summarizer = summarizer
        self.dingtalk_client = dingtalk_client
        logger.info("ReportGenerator 初始化")

    async def generate_daily_report(
        self,
        days: int = 1,
        include_details: bool = True,
    ) -> str:
        """
        生成日报。

        Args:
            days: 统计天数（1=日报，7=周报）
            include_details: 是否包含详细信息

        Returns:
            Markdown 格式的报告文本
        """
        logger.info("生成日报 | days={}", days)

        try:
            # 获取汇总数据
            summary = await self.summarizer.get_summary(days=days)

            # 获取高频问题
            top_questions = await self.summarizer.get_top_questions(
                days=days,
                limit=10,
            )

            # 获取未回答问题
            unanswered = await self.summarizer.get_unanswered(
                days=days,
                limit=10,
            )

            # 构建报告
            report = self._build_report(
                summary=summary,
                top_questions=top_questions,
                unanswered=unanswered,
                days=days,
                include_details=include_details,
            )

            logger.info("日报生成完成 | days={} | total={}", days, summary.total)
            return report

        except Exception as e:
            logger.error("日报生成失败 | error={}", str(e))
            return self._build_error_report(str(e))

    async def generate_weekly_report(self) -> str:
        """
        生成周报（最近7天）。

        Returns:
            Markdown 格式的周报文本
        """
        return await self.generate_daily_report(days=7)

    async def push_to_dingtalk(
        self,
        report: str,
        conversation_id: str,
        title: str = "智能问答日报",
    ) -> bool:
        """
        推送报告到钉钉群。

        Args:
            report: 报告内容（Markdown 格式）
            conversation_id: 目标群会话 ID
            title: 消息标题

        Returns:
            True 表示推送成功
        """
        if self.dingtalk_client is None:
            logger.warning("钉钉客户端未配置，无法推送报告")
            return False

        try:
            await self.dingtalk_client.send_markdown(
                open_conversation_id=conversation_id,
                title=title,
                text=report,
            )
            logger.info("报告已推送到钉钉 | conversation={}", conversation_id[:20])
            return True

        except Exception as e:
            logger.error("推送报告到钉钉失败 | error={}", str(e))
            return False

    def _build_report(
        self,
        summary: SummaryResult,
        top_questions: list[dict[str, Any]],
        unanswered: list[dict[str, Any]],
        days: int,
        include_details: bool = True,
    ) -> str:
        """
        构建 Markdown 格式的报告。

        Args:
            summary: 汇总数据
            top_questions: 高频问题列表
            unanswered: 未回答问题列表
            days: 统计天数
            include_details: 是否包含详细信息

        Returns:
            Markdown 格式的报告文本
        """
        today = date.today().strftime("%Y-%m-%d")
        period = "日报" if days == 1 else f"周报（近 {days} 天）"

        lines: list[str] = []

        # ── 标题 ──
        lines.append(f"# 🤖 智能问答{period}")
        lines.append("")
        lines.append(f"**统计周期**: {summary.start_date} ~ {summary.end_date}")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # ── 概览 ──
        lines.append("## 📊 概览")
        lines.append("")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 问题总数 | {summary.total} |")
        lines.append(f"| 活跃用户 | {summary.active_users} |")
        lines.append(f"| 平均置信度 | {summary.avg_confidence:.1%} |")
        lines.append(f"| 成功回答率 | {summary.success_rate:.1%} |")
        lines.append("")

        # ── 分类统计 ──
        lines.append("## 📈 问题分类统计")
        lines.append("")

        if summary.category_stats:
            lines.append("| 分类 | 数量 | 占比 | 置信度 | 成功率 |")
            lines.append("|------|------|------|--------|--------|")

            for stat in summary.category_stats:
                cat_name = self.CATEGORY_NAMES.get(stat.category, "未知")
                lines.append(
                    f"| {cat_name} | {stat.count} | {stat.percentage:.1%} | "
                    f"{stat.avg_confidence:.1%} | {stat.success_rate:.1%} |"
                )
        else:
            lines.append("暂无数据")

        lines.append("")

        # ── 高频问题 ──
        if include_details:
            lines.append("## 🔥 高频问题 TOP 10")
            lines.append("")

            if top_questions:
                for item in top_questions[:10]:
                    question_text = item["question"]
                    # 截断过长的文本
                    if len(question_text) > 50:
                        question_text = question_text[:47] + "..."
                    lines.append(f"{item['rank']}. {question_text}（{item['count']}次）")
            else:
                lines.append("暂无数据")

            lines.append("")

            # ── 未回答问题 ──
            lines.append("## ❓ 未回答问题（知识库盲区）")
            lines.append("")
            lines.append("> 以下问题未能成功回答，建议补充相关知识")
            lines.append("")

            if unanswered:
                for item in unanswered[:10]:
                    q_text = item["text"]
                    if len(q_text) > 50:
                        q_text = q_text[:47] + "..."
                    lines.append(f"- {q_text}")
            else:
                lines.append("✅ 所有问题均已成功回答")

            lines.append("")

        # ── 建议 ──
        if include_details:
            lines.append("## 💡 改进建议")
            lines.append("")

            suggestions = self._generate_suggestions(summary, top_questions, unanswered)
            if suggestions:
                for i, suggestion in enumerate(suggestions, 1):
                    lines.append(f"{i}. {suggestion}")
            else:
                lines.append("系统运行良好，暂无需要改进的地方。")

            lines.append("")

        # ── 页脚 ──
        lines.append("---")
        lines.append(f"*报告由智能问答机器人自动生成*")

        return "\n".join(lines)

    def _generate_suggestions(
        self,
        summary: SummaryResult,
        top_questions: list[dict[str, Any]],
        unanswered: list[dict[str, Any]],
    ) -> list[str]:
        """
        根据统计数据生成改进建议。

        Args:
            summary: 汇总数据
            top_questions: 高频问题
            unanswered: 未回答问题

        Returns:
            建议列表
        """
        suggestions: list[str] = []

        # 成功率低
        if summary.success_rate < 0.8:
            suggestions.append(
                f"当前成功回答率为 {summary.success_rate:.0%}，"
                "建议扩充知识库内容以提高回答准确率"
            )

        # 未回答问题多
        if len(unanswered) > 5:
            suggestions.append(
                f"有 {len(unanswered)} 个问题未成功回答，"
                "建议分析这些问题并补充相关知识"
            )

        # 置信度低
        if summary.avg_confidence < 0.6:
            suggestions.append(
                f"平均置信度为 {summary.avg_confidence:.0%}，"
                "建议优化检索策略或改进 Prompt 模板"
            )

        # 高频问题重复
        if top_questions:
            top1 = top_questions[0]
            if top1["count"] >= 5:
                suggestions.append(
                    f"高频问题「{top1['question'][:20]}...」出现 {top1['count']} 次，"
                    "建议将该问题的解答整理为文档供用户自助查阅"
                )

        return suggestions

    def _build_error_report(self, error_message: str) -> str:
        """
        构建错误报告。

        Args:
            error_message: 错误信息

        Returns:
            错误报告文本
        """
        return f"""# ❌ 报告生成失败

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**错误信息**: {error_message}

请联系管理员检查系统状态。

---
*报告由智能问答机器人自动生成*
"""


# ============================================================================
# 便捷函数
# ============================================================================

async def generate_daily_report(
    summarizer: QuestionSummarizer,
    days: int = 1,
) -> str:
    """
    生成日报的便捷函数。

    Args:
        summarizer: 问题汇总器
        days: 统计天数

    Returns:
        报告文本
    """
    reporter = ReportGenerator(summarizer=summarizer)
    return await reporter.generate_daily_report(days=days)
