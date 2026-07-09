#!/usr/bin/env python3
"""知识库构建脚本。

从 Vue 2 前端项目代码构建知识库。

用法:
    uv run scripts/build_knowledge.py --project-root /path/to/vue-project
    uv run scripts/build_knowledge.py --project-root /path/to/vue-project --enrich
    uv run scripts/build_knowledge.py --project-root /path/to/vue-project --incremental

依赖:
    - src.parser: Vue 2 代码解析模块
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

from src.config import settings
from src.infrastructure.database import DatabaseManager
from src.infrastructure.repositories.knowledge_repo import SQLiteKnowledgeRepository
from src.llm.client import OllamaClient
from src.parser import KnowledgeBuilder, VueProjectParser
from src.rag.embedding import EmbeddingService
from src.rag.vectorstore import ChromaVectorStore
from src.services.knowledge_service import KnowledgeService


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="从 Vue 2 前端项目代码构建知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --project-root ./frontend
  %(prog)s --project-root ./frontend --enrich
  %(prog)s --project-root ./frontend --incremental
  %(prog)s --project-root ./frontend --enrich --no-embedding
        """,
    )

    parser.add_argument(
        "--project-root",
        type=str,
        required=True,
        help="前端项目根目录路径",
    )

    parser.add_argument(
        "--enrich",
        action="store_true",
        help="使用 LLM 丰富知识描述（耗时较长）",
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="增量构建（只处理新增或修改的文件）",
    )

    parser.add_argument(
        "--no-embedding",
        action="store_true",
        help="跳过向量化（仅解析和构建知识条目）",
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="构建前清空现有知识库",
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

    # 初始化 LLM 客户端（用于丰富描述）
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


async def build_knowledge(
    project_root: Path,
    enrich: bool = False,
    incremental: bool = False,
    no_embedding: bool = False,
    clear: bool = False,
) -> int:
    """
    构建知识库

    Args:
        project_root: 前端项目路径
        enrich: 是否使用 LLM 丰富描述
        incremental: 是否增量构建
        no_embedding: 是否跳过向量化
        clear: 是否清空现有知识库

    Returns:
        构建的知识条目数量
    """
    start_time = time.time()

    print("\n" + "=" * 60)
    print("🔨 开始构建知识库")
    print("=" * 60)

    # 初始化服务
    print("\n📦 初始化服务...")
    knowledge_service, vectorstore = init_services()

    # 清空知识库
    if clear:
        print("\n🗑️  清空现有知识库...")
        await vectorstore.clear()
        print("   ✅ 知识库已清空")

    # 解析代码
    print(f"\n📖 解析项目: {project_root}")
    parser = VueProjectParser(project_root=str(project_root))
    parse_result = parser.parse()

    print(f"   页面数: {len(parse_result.pages)}")
    print(f"   路由数: {len(parse_result.routes)}")

    # 构建知识条目
    print("\n🔧 构建知识条目...")
    builder = KnowledgeBuilder()
    knowledge_items = builder.build(parse_result)

    print(f"   生成知识条目: {len(knowledge_items)} 条")

    if not knowledge_items:
        print("\n⚠️  未生成任何知识条目，请检查项目结构")
        return 0

    # 增量构建：过滤已存在的条目
    if incremental:
        print("\n🔄 增量构建模式")
        # TODO: 实现增量构建逻辑
        print("   （增量构建逻辑待实现，当前按全量构建处理）")

    # 构建知识库
    print("\n💾 写入知识库...")

    if no_embedding:
        # 跳过向量化，只保存元数据
        print("   跳过向量化（--no-embedding）")
        # 这里可以保存到 SQLite 但不向量化
    else:
        # 完整构建
        stats = await knowledge_service.build_from_code(
            knowledge_items=knowledge_items,
            enrich=enrich,
        )

        print(f"   总条目数: {stats['total']}")
        print(f"   丰富条目数: {stats['enriched']}")
        print(f"   向量化条目数: {stats['vectorized']}")
        print(f"   入库条目数: {stats['stored']}")

    # 统计耗时
    latency = time.time() - start_time

    print("\n" + "=" * 60)
    print(f"✅ 知识库构建完成")
    print(f"   知识条目: {len(knowledge_items)} 条")
    print(f"   耗时: {latency:.1f} 秒")
    print("=" * 60)

    return len(knowledge_items)


def main() -> int:
    """主函数"""
    args = parse_args()

    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # 验证项目路径
    project_root = Path(args.project_root)
    if not project_root.exists():
        print(f"❌ 项目路径不存在: {project_root}")
        return 1

    if not project_root.is_dir():
        print(f"❌ 路径不是目录: {project_root}")
        return 1

    try:
        # 运行异步构建
        count = asyncio.run(build_knowledge(
            project_root=project_root,
            enrich=args.enrich,
            incremental=args.incremental,
            no_embedding=args.no_embedding,
            clear=args.clear,
        ))

        return 0 if count > 0 else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 130

    except Exception as e:
        logger.error("知识库构建失败: {}", str(e))
        print(f"\n❌ 知识库构建失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
