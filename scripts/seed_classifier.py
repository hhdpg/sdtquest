#!/usr/bin/env python3
"""分类器种子数据脚本。

预置问题分类样本数据，写入 SQLite 供分类器使用。

用法:
    uv run scripts/seed_classifier.py
    uv run scripts/seed_classifier.py --clear
    uv run scripts/seed_classifier.py --show

依赖:
    - src.infrastructure.database: 数据库管理
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.domain.enums import AnswerStatus, QuestionCategory
from src.infrastructure.database import DatabaseManager


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="预置问题分类样本数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s              # 导入种子数据
  %(prog)s --clear      # 清空后导入
  %(prog)s --show       # 显示当前数据
  %(prog)s --stats      # 显示统计信息
        """,
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清空现有数据",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="显示当前数据样本",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="显示数据统计",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志",
    )

    return parser.parse_args()


# ============================================================================
# 种子数据定义
# ============================================================================

# 操作指南类样本
OPERATION_GUIDE_SAMPLES = [
    "如何创建订单?",
    "怎么删除用户?",
    "在哪里导出报表?",
    "如何查询订单状态?",
    "怎么修改密码?",
    "如何添加新员工?",
    "在哪里设置权限?",
    "怎么上传文件?",
    "如何导出数据?",
    "怎么打印页面?",
    "在哪里配置系统参数?",
    "如何批量操作?",
    "怎么筛选数据?",
    "如何查看日志?",
    "在哪里修改个人资料?",
    "怎么提交申请?",
    "如何审核订单?",
    "在哪里查看统计?",
    "怎么发送通知?",
    "如何备份数据?",
    "怎么恢复数据?",
    "在哪里设置提醒?",
    "如何分配任务?",
    "怎么查看进度?",
    "在哪里创建项目?",
    "如何归档文件?",
    "怎么搜索内容?",
    "在哪里设置主题?",
    "如何添加标签?",
    "怎么复制链接?",
]

# 流程咨询类样本
PROCESS_INQUIRY_SAMPLES = [
    "审批流程是怎样的?",
    "订单处理的完整流程是什么?",
    "采购申请需要经过哪些步骤?",
    "员工入职流程是什么?",
    "退货流程怎么走?",
    "项目立项的审批流程?",
    "报销流程需要多久?",
    "合同签署的流程步骤?",
    "客户投诉处理流程?",
    "绩效考核的流程是怎样的?",
    "请假审批流程是什么?",
    "出差申请怎么走流程?",
    "付款流程需要哪些审批?",
    "供应商准入流程?",
    "产品开发流程是怎样的?",
    "质量检验流程步骤?",
    "库存盘点流程怎么走?",
    "发货流程需要哪些步骤?",
    "售后服务流程是什么?",
    "投诉处理流程怎么走?",
    "退款流程需要多久?",
    "合同变更的审批流程?",
    "项目验收流程是怎样的?",
    "人员调动流程怎么走?",
    "薪酬调整流程是什么?",
    "培训申请流程步骤?",
    "设备报修流程怎么走?",
    "采购比价流程是什么?",
    "招标流程需要哪些步骤?",
    "结算流程怎么走?",
]

# 异常排查类样本
ANOMALY_TROUBLESHOOT_SAMPLES = [
    "提交订单报错了",
    "页面加载失败",
    "为什么登录不了?",
    "系统出问题了",
    "数据无法保存",
    "按钮点击没反应",
    "为什么显示空白?",
    "导出功能报错了",
    "页面打不开",
    "为什么搜索不到结果?",
    "提交后一直转圈",
    "为什么权限不足?",
    "系统提示错误",
    "文件上传失败",
    "为什么数据不对?",
    "页面闪退",
    "为什么无法打印?",
    "系统很卡",
    "为什么收不到通知?",
    "数据同步失败",
    "为什么格式不对?",
    "图片无法显示",
    "为什么超时了?",
    "报表生成失败",
    "为什么密码错误?",
    "系统崩溃了",
    "为什么数据丢失?",
    "接口调用报错",
    "为什么权限被拒绝?",
    "页面样式乱了",
]

# 闲聊/其他类样本
GENERAL_SAMPLES = [
    "你好",
    "谢谢",
    "再见",
    "好的",
    "明白了",
    "收到",
    "辛苦了",
    "没问题",
    "可以的",
    "嗯",
    "哦",
    "哈哈",
    "请问有人在吗?",
    "早上好",
    "下午好",
    "晚安",
    "拜拜",
    "感谢帮助",
    "太棒了",
    "知道了",
    "好吧",
    "行",
    "OK",
    "Hi",
    "Hello",
    "Thanks",
    "Bye",
    "好的谢谢",
    "明白了谢谢",
    "收到感谢",
]


def get_seed_data() -> list[tuple[str, QuestionCategory]]:
    """获取所有种子数据"""
    data = []

    for text in OPERATION_GUIDE_SAMPLES:
        data.append((text, QuestionCategory.OPERATION_GUIDE))

    for text in PROCESS_INQUIRY_SAMPLES:
        data.append((text, QuestionCategory.PROCESS_INQUIRY))

    for text in ANOMALY_TROUBLESHOOT_SAMPLES:
        data.append((text, QuestionCategory.ANOMALY_TROUBLESHOOT))

    for text in GENERAL_SAMPLES:
        data.append((text, QuestionCategory.GENERAL))

    return data


def clear_data(db_manager: DatabaseManager) -> None:
    """清空种子数据"""
    db_manager.execute("DELETE FROM question_records WHERE sender_id = 'seed_classifier'")
    db_manager.commit()
    print("✅ 已清空种子数据")


def show_data(db_manager: DatabaseManager) -> None:
    """显示当前数据"""
    cursor = db_manager.execute(
        """
        SELECT question, category, created_at
        FROM question_records
        WHERE sender_id = 'seed_classifier'
        ORDER BY category, created_at
        """
    )

    rows = cursor.fetchall()

    if not rows:
        print("\n暂无种子数据")
        return

    print("\n" + "=" * 60)
    print("📋 种子数据样本")
    print("=" * 60)

    current_category = None
    for row in rows:
        category = row["category"]
        if category != current_category:
            current_category = category
            print(f"\n【{category}】")
        print(f"  • {row['question']}")


def show_stats(db_manager: DatabaseManager) -> None:
    """显示数据统计"""
    cursor = db_manager.execute(
        """
        SELECT category, COUNT(*) as count
        FROM question_records
        WHERE sender_id = 'seed_classifier'
        GROUP BY category
        ORDER BY count DESC
        """
    )

    rows = cursor.fetchall()

    if not rows:
        print("\n暂无种子数据")
        return

    print("\n" + "=" * 60)
    print("📊 种子数据统计")
    print("=" * 60)

    total = 0
    for row in rows:
        category = row["category"]
        count = row["count"]
        total += count
        print(f"  {category}: {count} 条")

    print(f"\n  总计: {total} 条")


def seed_data(db_manager: DatabaseManager) -> int:
    """导入种子数据"""
    seed_items = get_seed_data()

    print(f"\n📥 导入种子数据: {len(seed_items)} 条")

    now = datetime.now().isoformat()

    for text, category in seed_items:
        # 生成唯一 ID
        import hashlib
        item_id = hashlib.md5(f"seed:{text}".encode()).hexdigest()[:16]

        try:
            db_manager.execute(
                """
                INSERT OR REPLACE INTO question_records
                (id, question, answer, category, sender_id, conversation_id,
                 confidence, status, sources, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    text,
                    "",  # 空回答
                    category.value,
                    "seed_classifier",  # 标记为种子数据
                    "seed",
                    1.0,  # 高置信度
                    AnswerStatus.SUCCESS.value,
                    "[]",
                    now,
                ),
            )
        except Exception as e:
            logger.warning("导入失败: {} | error={}", text[:30], str(e))

    db_manager.commit()

    return len(seed_items)


def main() -> int:
    """主函数"""
    args = parse_args()

    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    try:
        # 初始化数据库
        db_manager = DatabaseManager()
        db_manager.initialize_tables()

        # 显示数据
        if args.show:
            show_data(db_manager)
            return 0

        # 显示统计
        if args.stats:
            show_stats(db_manager)
            return 0

        # 清空数据
        if args.clear:
            clear_data(db_manager)

        # 导入种子数据
        count = seed_data(db_manager)

        print("\n" + "=" * 60)
        print(f"✅ 种子数据导入完成: {count} 条")
        print("=" * 60)

        # 显示统计
        show_stats(db_manager)

        return 0

    except Exception as e:
        logger.error("种子数据导入失败: {}", str(e))
        print(f"\n❌ 种子数据导入失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
