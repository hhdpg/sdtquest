#!/usr/bin/env python3
"""文档导入脚本。

将 Markdown 或纯文本文件导入到知识库。

用法:
    uv run scripts/import_docs.py --file /path/to/doc.md
    uv run scripts/import_docs.py --dir /path/to/docs
    uv run scripts/import_docs.py --dir /path/to/docs --enrich

依赖:
    - src.services.knowledge_service: 知识库管理服务
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.infrastructure.database import DatabaseManager
from src.infrastructure.repositories.knowledge_repo import SQLiteKnowledgeRepository
from src.llm.client import OllamaClient
from src.rag.embedding import EmbeddingService
from src.rag.vectorstore import ChromaVectorStore
from src.services.knowledge_service import KnowledgeService


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="将 Markdown 或纯文本文件导入到知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --file ./docs/guide.md
  %(prog)s --dir ./docs
  %(prog)s --dir ./docs --enrich
  %(prog)s --dir ./docs --recursive=false
        """,
    )

    # 输入源（二选一）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        type=str,
        help="单个文件路径",
    )
    input_group.add_argument(
        "--dir",
        type=str,
        help="目录路径（导入目录中所有 Markdown/文本文件）",
    )

    parser.add_argument(
        "--enrich",
        action="store_true",
        help="使用 LLM 丰富文档描述（耗时较长）",
    )

    parser.add_argument(
        "--recursive",
        type=bool,
        default=True,
        help="递归扫描子目录（默认: True）",
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="导入前清空现有知识库",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志",
    )

    return parser.parse_args()


def init_services() -> tuple[KnowledgeService, ChromaVectorStore]:
    """初始化服务"""
    # 初始化数据库
    db_manager = DatabaseManager()
    db_manager.initialize_tables()

    # 初始化 Repository
    knowledge_repo = SQLiteKnowledgeRepository(db_manager=db_manager)

    # 初始化向量库
    vectorstore = ChromaVectorStore()

    # 初始化 LLM 客户端
    llm_client = OllamaClient()

    # 初始化 Embedding 服务
    embedding_service = EmbeddingService()

    # 创建知识库服务
    knowledge_service = KnowledgeService(
        vectorstore=vectorstore,
        llm=llm_client,
        knowledge_repo=knowledge_repo,
        embedding=embedding_service,
    )

    return knowledge_service, vectorstore


async def import_file(
    knowledge_service: KnowledgeService,
    file_path: Path,
    enrich: bool = False,
) -> int:
    """
    导入单个文件

    Args:
        knowledge_service: 知识库服务
        file_path: 文件路径
        enrich: 是否丰富描述

    Returns:
        导入的条目数量
    """
    print(f"\n📄 导入文件: {file_path.name}")

    items = await knowledge_service.import_from_file(
        file_path=str(file_path),
        enrich=enrich,
    )

    print(f"   生成条目: {len(items)} 条")
    return len(items)


async def import_directory(
    knowledge_service: KnowledgeService,
    dir_path: Path,
    enrich: bool = False,
    recursive: bool = True,
) -> int:
    """
    导入整个目录

    Args:
        knowledge_service: 知识库服务
        dir_path: 目录路径
        enrich: 是否丰富描述
        recursive: 是否递归

    Returns:
        导入的条目数量
    """
    print(f"\n📁 导入目录: {dir_path}")
    print(f"   递归: {recursive}")

    items = await knowledge_service.import_from_directory(
        dir_path=str(dir_path),
        enrich=enrich,
        recursive=recursive,
    )

    print(f"   生成条目: {len(items)} 条")
    return len(items)


async def import_docs(
    file_path: str | None = None,
    dir_path: str | None = None,
    enrich: bool = False,
    recursive: bool = True,
    clear: bool = False,
) -> int:
    """
    导入文档

    Args:
        file_path: 文件路径
        dir_path: 目录路径
        enrich: 是否丰富描述
        recursive: 是否递归
        clear: 是否清空知识库

    Returns:
        导入的条目数量
    """
    start_time = time.time()

    print("\n" + "=" * 60)
    print("📥 开始导入文档")
    print("=" * 60)

    # 初始化服务
    print("\n📦 初始化服务...")
    knowledge_service, vectorstore = init_services()

    # 清空知识库
    if clear:
        print("\n🗑️  清空现有知识库...")
        await vectorstore.clear()
        print("   ✅ 知识库已清空")

    # 导入文档
    total_items = 0

    if file_path:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ 文件不存在: {path}")
            return 0
        total_items = await import_file(knowledge_service, path, enrich)

    elif dir_path:
        path = Path(dir_path)
        if not path.exists():
            print(f"❌ 目录不存在: {path}")
            return 0
        total_items = await import_directory(
            knowledge_service, path, enrich, recursive
        )

    # 统计耗时
    latency = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"✅ 文档导入完成")
    print(f"   导入条目: {total_items} 条")
    print(f"   耗时: {latency:.1f} 秒")
    print("=" * 60)

    return total_items


def main() -> int:
    """主函数"""
    args = parse_args()

    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    try:
        # 运行异步导入
        count = asyncio.run(import_docs(
            file_path=args.file,
            dir_path=args.dir,
            enrich=args.enrich,
            recursive=args.recursive,
            clear=args.clear,
        ))

        return 0 if count > 0 else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 130

    except Exception as e:
        logger.error("文档导入失败: {}", str(e))
        print(f"\n❌ 文档导入失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
