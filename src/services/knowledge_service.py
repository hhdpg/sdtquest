"""知识库管理服务模块。

本模块实现知识库的管理和维护功能，包括从代码构建知识库、手动导入文档、
知识库统计等操作。

主要类:
- KnowledgeService: 知识库管理服务

典型用法:
    >>> from src.services.knowledge_service import KnowledgeService
    >>> service = KnowledgeService(vectorstore=vs, llm=llm, knowledge_repo=repo)
    >>> await service.build_from_code(knowledge_items)
    >>> stats = await service.get_stats()
"""

from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from loguru import logger

from src.domain.enums import KnowledgeType
from src.domain.exceptions import AppException, LLMServiceError
from src.domain.models import KnowledgeItem
from src.domain.ports import LLMClient, GenerateOptions, VectorStore
from src.llm.prompts.enrichment import build_enrichment_prompt
from src.rag.embedding import EmbeddingService


# ============================================================================
# KnowledgeService
# ============================================================================

class KnowledgeService:
    """
    知识库管理服务类。

    负责知识库的构建、导入和维护，包括:
    - 从代码解析结果构建知识库（Parser → LLM 丰富 → 向量化入库）
    - 手动导入文档（支持 Markdown、纯文本）
    - 知识库统计信息
    - 知识条目的增删查

    Attributes:
        vectorstore: 向量存储（ChromaDB）
        llm: LLM 客户端，用于丰富知识描述（可选）
        embedding: Embedding 服务
        knowledge_repo: 知识仓储（SQLite 元数据）

    Example:
        >>> service = KnowledgeService(vectorstore=vs, knowledge_repo=repo)
        >>> await service.build_from_code(items, enrich=True)
        >>> stats = await service.get_stats()
    """

    def __init__(
        self,
        vectorstore: VectorStore,
        llm: LLMClient | None = None,
        knowledge_repo: Any | None = None,
        embedding: EmbeddingService | None = None,
    ):
        """
        初始化知识库管理服务。

        Args:
            vectorstore: 向量存储实例
            llm: LLM 客户端（用于丰富知识描述，可选）
            knowledge_repo: 知识仓储实例（SQLite 元数据，可选）
            embedding: Embedding 服务实例（可选，默认创建新实例）
        """
        self.vectorstore = vectorstore
        self.llm = llm
        self.knowledge_repo = knowledge_repo
        self.embedding = embedding or EmbeddingService()
        logger.info(
            "KnowledgeService 初始化 | vectorstore={} | llm={} | repo={}",
            type(vectorstore).__name__,
            type(llm).__name__ if llm else None,
            type(knowledge_repo).__name__ if knowledge_repo else None,
        )

    async def build_from_code(
        self,
        knowledge_items: list[KnowledgeItem],
        enrich: bool = True,
    ) -> dict[str, Any]:
        """
        从代码解析结果构建知识库。

        完整流程:
        1. （可选）调用 LLM 丰富知识描述
        2. 向量化知识条目
        3. 写入向量库（ChromaDB）
        4. 保存元数据到 SQLite

        Args:
            knowledge_items: 从代码解析得到的知识条目列表
            enrich: 是否使用 LLM 丰富描述（默认 True）

        Returns:
            构建结果统计字典，包含:
            - total: 总条目数
            - enriched: 丰富的条目数
            - vectorized: 向量化的条目数
            - stored: 入库的条目数

        Raises:
            KnowledgeBuildError: 构建失败
        """
        if not knowledge_items:
            logger.warning("知识构建: 传入的条目列表为空")
            return {"total": 0, "enriched": 0, "vectorized": 0, "stored": 0}

        logger.info(
            "开始构建知识库 | total={} | enrich={}",
            len(knowledge_items),
            enrich,
        )

        start_time = time.time()
        stats = {
            "total": len(knowledge_items),
            "enriched": 0,
            "vectorized": 0,
            "stored": 0,
        }

        try:
            # ── 1. LLM 丰富描述 ──
            if enrich and self.llm is not None:
                knowledge_items = await self._enrich_items(knowledge_items)
                stats["enriched"] = len(knowledge_items)

            # ── 2. 向量化 ──
            knowledge_items = await self._vectorize_items(knowledge_items)
            stats["vectorized"] = len(knowledge_items)

            # ── 3. 写入向量库 ──
            await self.vectorstore.add(knowledge_items)

            # ── 4. 保存元数据到 SQLite ──
            if self.knowledge_repo is not None:
                self.knowledge_repo.save_batch(knowledge_items)

            stats["stored"] = len(knowledge_items)

            latency = time.time() - start_time
            logger.info(
                "知识库构建完成 | total={} | enriched={} | vectorized={} | stored={} | latency={:.1f}s",
                stats["total"],
                stats["enriched"],
                stats["vectorized"],
                stats["stored"],
                latency,
            )

            return stats

        except Exception as e:
            logger.error("知识库构建失败 | error={}", str(e))
            raise KnowledgeBuildError(f"知识库构建失败: {e}") from e

    async def _enrich_items(
        self,
        items: list[KnowledgeItem],
    ) -> list[KnowledgeItem]:
        """
        使用 LLM 丰富知识条目的描述。

        对每条知识条目调用 LLM，将技术性描述转换为通俗易懂的操作指南。

        Args:
            items: 待丰富的知识条目列表

        Returns:
            丰富后的知识条目列表
        """
        if self.llm is None:
            return items

        enriched_items = []
        for item in items:
            try:
                enriched_content = await self._enrich_single(item)
                enriched_item = item.model_copy(update={"content": enriched_content})
                enriched_items.append(enriched_item)
                logger.debug(
                    "知识丰富完成 | title={} | content_len={}",
                    item.title,
                    len(enriched_content),
                )
            except Exception as e:
                logger.warning(
                    "知识丰富失败，使用原始内容 | title={} | error={}",
                    item.title,
                    str(e),
                )
                enriched_items.append(item)

        return enriched_items

    async def _enrich_single(self, item: KnowledgeItem) -> str:
        """
        丰富单条知识的内容描述。

        Args:
            item: 知识条目

        Returns:
            丰富后的内容文本
        """
        prompt = build_enrichment_prompt(
            code_snippet=item.content[:5000],
            page_name=item.page_name or "",
            page_path=item.page_path or "",
        )

        options = GenerateOptions(
            temperature=0.5,
            max_tokens=1024,
        )

        enriched = await self.llm.generate(prompt, options)
        return enriched.strip()

    async def _vectorize_items(
        self,
        items: list[KnowledgeItem],
    ) -> list[KnowledgeItem]:
        """
        向量化知识条目，将 embedding 填充到每个条目中。

        Args:
            items: 知识条目列表

        Returns:
            填充了 embedding 的知识条目列表
        """
        documents = [item.to_document_string() for item in items]

        try:
            embeddings = await self.embedding.embed_documents(documents)

            # 将 embedding 回填到每个 KnowledgeItem
            vectorized_items = []
            for item, embedding in zip(items, embeddings):
                vectorized_item = item.model_copy(update={"embedding": embedding})
                vectorized_items.append(vectorized_item)

            logger.info("知识向量化完成 | count={}", len(vectorized_items))
            return vectorized_items

        except Exception as e:
            logger.error("知识向量化失败 | error={}", str(e))
            raise LLMServiceError(f"知识向量化失败: {e}") from e

    async def import_document(
        self,
        content: str,
        title: str,
        doc_type: KnowledgeType = KnowledgeType.MANUAL,
        page_name: str | None = None,
        tags: list[str] | None = None,
        enrich: bool = False,
        file_path: str | None = None,
    ) -> KnowledgeItem:
        """
        导入单个文档到知识库。

        流程:
        1. 创建 KnowledgeItem
        2. （可选）LLM 丰富描述
        3. 向量化
        4. 写入向量库和元数据库

        Args:
            content: 文档内容
            title: 文档标题
            doc_type: 文档类型
            page_name: 所属页面名称
            tags: 标签列表
            enrich: 是否使用 LLM 丰富描述
            file_path: 源文件路径（可选，用于记录来源）

        Returns:
            创建并入库的 KnowledgeItem

        Raises:
            KnowledgeBuildError: 导入失败
        """
        item = KnowledgeItem(
            id=str(uuid4()),
            type=doc_type,
            title=title,
            content=content,
            page_name=page_name,
            source_file=file_path,
            tags=tags or [],
        )

        try:
            # LLM 丰富
            if enrich and self.llm is not None:
                enriched_items = await self._enrich_items([item])
                item = enriched_items[0]

            # 向量化
            vectorized_items = await self._vectorize_items([item])
            item = vectorized_items[0]

            # 写入向量库
            await self.vectorstore.add([item])

            # 保存元数据
            if self.knowledge_repo is not None:
                self.knowledge_repo.save(item)

            logger.info(
                "文档导入完成 | title={} | type={} | page={}",
                title,
                doc_type.value,
                page_name,
            )

            return item

        except Exception as e:
            logger.error("文档导入失败 | title={} | error={}", title, str(e))
            raise KnowledgeBuildError(f"文档导入失败: {e}") from e

    async def import_from_file(
        self,
        file_path: str | Path,
        enrich: bool = False,
    ) -> list[KnowledgeItem]:
        """
        从文件导入文档。

        支持 Markdown (.md) 和纯文本 (.txt) 文件。
        大文件会自动按段落分块。

        Args:
            file_path: 文件路径
            enrich: 是否使用 LLM 丰富描述

        Returns:
            创建的知识条目列表

        Raises:
            KnowledgeBuildError: 导入失败
        """
        path = Path(file_path)
        if not path.exists():
            raise KnowledgeBuildError(f"文件不存在: {file_path}")

        # 仅支持特定文件类型
        if path.suffix not in (".md", ".txt", ".markdown"):
            raise KnowledgeBuildError(f"不支持的文件格式: {path.suffix}")

        try:
            content = path.read_text(encoding="utf-8")
            title = path.stem.replace("_", " ").replace("-", " ").title()

            # 大文件分块处理
            chunks = self._split_content(content, max_chunk_size=3000)
            items = []

            for i, chunk in enumerate(chunks):
                chunk_title = f"{title}" if len(chunks) == 1 else f"{title} (第{i + 1}部分)"
                item = await self.import_document(
                    content=chunk,
                    title=chunk_title,
                    doc_type=KnowledgeType.MANUAL,
                    enrich=enrich,
                    file_path=str(path),
                )
                items.append(item)

            logger.info(
                "文件导入完成 | file={} | chunks={}",
                path.name,
                len(items),
            )
            return items

        except UnicodeDecodeError as e:
            raise KnowledgeBuildError(f"文件编码错误: {file_path}") from e
        except Exception as e:
            logger.error("文件导入失败 | file={} | error={}", file_path, str(e))
            raise KnowledgeBuildError(f"文件导入失败: {e}") from e

    async def import_from_directory(
        self,
        dir_path: str | Path,
        enrich: bool = False,
        recursive: bool = True,
    ) -> list[KnowledgeItem]:
        """
        从目录批量导入文档。

        扫描目录中的所有 Markdown 和纯文本文件并逐个导入。

        Args:
            dir_path: 目录路径
            enrich: 是否使用 LLM 丰富描述
            recursive: 是否递归扫描子目录

        Returns:
            所有创建的知识条目列表
        """
        path = Path(dir_path)
        if not path.is_dir():
            raise KnowledgeBuildError(f"目录不存在: {dir_path}")

        all_items = []
        patterns = ["*.md", "*.txt", "*.markdown"]

        for pattern in patterns:
            if recursive:
                files = path.rglob(pattern)
            else:
                files = path.glob(pattern)

            for file_path in files:
                try:
                    items = await self.import_from_file(file_path, enrich=enrich)
                    all_items.extend(items)
                except Exception as e:
                    logger.warning(
                        "导入文件失败，跳过 | file={} | error={}",
                        file_path,
                        str(e),
                    )

        logger.info(
            "目录导入完成 | dir={} | total_items={}",
            path.name,
            len(all_items),
        )
        return all_items

    async def get_stats(self) -> dict[str, Any]:
        """
        获取知识库统计信息。

        综合向量库和元数据库的统计数据。

        Returns:
            统计信息字典，包含:
            - total: 向量库文档总数
            - by_type: 按类型统计（如有元数据库）
            - page_count: 页面数量（如有元数据库）
            - vector_count: 向量库文档总数
        """
        try:
            stats: dict[str, Any] = {"total": 0}

            # 向量库统计
            vector_count = await self.vectorstore.count()
            stats["vector_count"] = vector_count
            stats["total"] = vector_count

            # SQLite 元数据统计
            if self.knowledge_repo is not None:
                repo_stats = self.knowledge_repo.get_stats()
                stats["db_total"] = repo_stats.get("total", 0)
                stats["by_type"] = repo_stats.get("by_type", {})
                stats["page_count"] = repo_stats.get("page_count", 0)
            else:
                stats["by_type"] = {}
                stats["page_count"] = 0

            logger.info("获取知识库统计 | total={}", stats["total"])
            return stats

        except Exception as e:
            logger.error("获取知识库统计失败 | error={}", str(e))
            return {"total": 0, "by_type": {}, "page_count": 0}

    async def get_knowledge_items(
        self,
        item_type: KnowledgeType | None = None,
        page_name: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeItem]:
        """
        查询知识条目列表。

        从 SQLite 元数据库中查询，支持按类型和页面过滤。

        Args:
            item_type: 知识类型过滤
            page_name: 页面名称过滤
            limit: 最大返回数量

        Returns:
            知识条目列表
        """
        if self.knowledge_repo is None:
            return []

        try:
            if item_type is not None:
                return self.knowledge_repo.find_by_type(item_type)
            elif page_name is not None:
                return self.knowledge_repo.find_by_page(page_name)
            else:
                return self.knowledge_repo.find_all(limit=limit)
        except Exception as e:
            logger.error("查询知识条目失败 | error={}", str(e))
            return []

    async def delete_knowledge(
        self,
        item_id: str,
    ) -> bool:
        """
        删除知识条目。

        同时从向量库和元数据库中删除。

        Args:
            item_id: 知识条目 ID

        Returns:
            是否删除成功
        """
        try:
            # 从向量库删除
            await self.vectorstore.delete([item_id])

            # 从元数据库删除
            if self.knowledge_repo is not None:
                self.knowledge_repo.delete(item_id)

            logger.info("知识条目已删除 | id={}", item_id)
            return True

        except Exception as e:
            logger.error("删除知识条目失败 | id={} | error={}", item_id, str(e))
            return False

    async def get_pages(self) -> list[str]:
        """
        获取知识库中的所有页面名称。

        Returns:
            页面名称列表（去重）
        """
        if self.knowledge_repo is None:
            return []

        try:
            all_items = self.knowledge_repo.find_all(limit=10000)
            pages = set()
            for item in all_items:
                if item.page_name:
                    pages.add(item.page_name)
            return sorted(pages)
        except Exception as e:
            logger.error("获取页面列表失败 | error={}", str(e))
            return []

    def _split_content(
        self,
        content: str,
        max_chunk_size: int = 3000,
    ) -> list[str]:
        """
        将长文档内容分割为多个块。

        按段落分割，每块不超过 max_chunk_size 字符。

        Args:
            content: 原始文档内容
            max_chunk_size: 每块最大字符数

        Returns:
            分块后的内容列表
        """
        if len(content) <= max_chunk_size:
            return [content]

        chunks = []
        paragraphs = content.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= max_chunk_size:
                current_chunk = (
                    current_chunk + "\n\n" + paragraph
                    if current_chunk
                    else paragraph
                )
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # 如果单个段落超过 max_chunk_size，按句号分割
                if len(paragraph) > max_chunk_size:
                    sentences = paragraph.replace("。", "。\n").split("\n")
                    sub_chunk = ""
                    for sentence in sentences:
                        if len(sub_chunk) + len(sentence) + 1 <= max_chunk_size:
                            sub_chunk = sub_chunk + sentence if sub_chunk else sentence
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = sentence
                    current_chunk = sub_chunk
                else:
                    current_chunk = paragraph

        if current_chunk.strip():
            chunks.append(current_chunk)

        return chunks


# ============================================================================
# 服务层异常
# ============================================================================

class KnowledgeBuildError(AppException):
    """知识库构建异常"""
    code = "KNOWLEDGE_BUILD_ERROR"
