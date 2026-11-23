"""ChromaDB 向量存储封装模块

实现 VectorStore 接口，提供向量存储和检索功能。
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from src.config import settings
from src.domain.exceptions import VectorStoreError
from src.domain.models import KnowledgeItem


class ChromaVectorStore:
    """
    ChromaDB 向量存储

    实现 VectorStore 接口，封装 ChromaDB 操作。

    Attributes:
        persist_dir: 持久化目录
        collection_name: 集合名称
        client: ChromaDB 客户端
        collection: 当前集合
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ):
        """
        初始化 ChromaDB 向量存储

        Args:
            persist_dir: 持久化目录，默认从配置读取
            collection_name: 集合名称，默认从配置读取
        """
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION

        # 确保目录存在
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        # 创建客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # 使用余弦相似度
        )

        logger.info(
            "ChromaVectorStore 初始化 | persist_dir={} | collection={}",
            self.persist_dir, self.collection_name
        )

    async def add(self, items: list[KnowledgeItem]) -> None:
        """
        添加知识文档到向量库

        Args:
            items: 知识条目列表

        Raises:
            VectorStoreError: 添加失败
        """
        if not items:
            return

        try:
            ids = [item.id for item in items]
            documents = [item.to_document_string() for item in items]
            metadatas = [item.get_metadata() for item in items]

            # 集合由外部 embedding（bge-m3, 1024 维）创建，
            # 若缺少 embedding 而交给 ChromaDB 默认函数（384 维）会触发维度冲突，
            # 因此这里要求调用方先向量化，避免静默写入错误维度的数据。
            embeddings = [item.embedding for item in items]
            if any(e is None for e in embeddings):
                raise VectorStoreError(
                    "知识条目缺少 embedding，请先调用向量化（embed_documents）后再写入"
                )

            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            logger.info(
                "添加文档到向量库 | count={} | total={}",
                len(items), self.collection.count()
            )
        except VectorStoreError:
            raise
        except Exception as e:
            logger.error("添加文档失败 | error={}", str(e))
            raise VectorStoreError(f"添加文档失败: {e}") from e

    async def add_with_embeddings(
        self,
        items: list[KnowledgeItem],
        embeddings: list[list[float]],
    ) -> None:
        """
        使用预计算的 embedding 添加文档

        Args:
            items: 知识条目列表
            embeddings: 对应的向量列表

        Raises:
            VectorStoreError: 添加失败
        """
        if not items or not embeddings:
            return

        if len(items) != len(embeddings):
            raise VectorStoreError("文档数量与向量数量不匹配")

        try:
            ids = [item.id for item in items]
            documents = [item.to_document_string() for item in items]
            metadatas = [item.get_metadata() for item in items]

            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            logger.info(
                "添加文档到向量库（带 embedding） | count={} | total={}",
                len(items), self.collection.count()
            )
        except Exception as e:
            logger.error("添加文档失败 | error={}", str(e))
            raise VectorStoreError(f"添加文档失败: {e}") from e

    async def search(
        self,
        query: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[KnowledgeItem]:
        """
        按向量检索相似文档

        Args:
            query: 查询向量
            top_k: 返回结果数量
            threshold: 相似度阈值（余弦相似度，0-1）
            filters: 元数据过滤条件

        Returns:
            按相似度排序的知识条目列表

        Raises:
            VectorStoreError: 检索失败
        """
        if not query:
            return []

        scored = await self.search_scored(
            query=query,
            top_k=top_k,
            threshold=threshold,
            filters=filters,
        )
        return [item for item, _ in scored]

    async def search_scored(
        self,
        query: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[KnowledgeItem, float]]:
        """
        按向量检索相似文档，并返回相似度分数。

        与 search() 的区别在于保留每条结果的余弦相似度（0-1），
        供上层做阈值判断与融合排序。

        Args:
            query: 查询向量
            top_k: 返回结果数量
            threshold: 相似度阈值（余弦相似度，0-1）
            filters: 元数据过滤条件

        Returns:
            (知识条目, 相似度分数) 列表，按相似度降序

        Raises:
            VectorStoreError: 检索失败
        """
        if not query:
            return []

        try:
            where_filter = self._build_where_filter(filters) if filters else None

            results = self.collection.query(
                query_embeddings=[query],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            scored: list[tuple[KnowledgeItem, float]] = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    # ChromaDB 返回余弦距离，相似度 = 1 - 距离
                    distance = results["distances"][0][i] if results["distances"] else 0.0
                    similarity = 1.0 - distance

                    if similarity < threshold:
                        continue

                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    document = results["documents"][0][i] if results["documents"] else ""

                    item = self._metadata_to_item(doc_id, metadata, document)
                    scored.append((item, similarity))

            logger.debug(
                "向量检索完成 | top_k={} | threshold={} | found={}",
                top_k, threshold, len(scored)
            )
            return scored

        except Exception as e:
            logger.error("向量检索失败 | error={}", str(e))
            raise VectorStoreError(f"向量检索失败: {e}") from e

    async def search_by_keywords(
        self,
        keywords: list[str],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[KnowledgeItem]:
        """
        按关键词做字面量检索（稀疏检索）。

        使用 ChromaDB 的 where_document $contains 在文档正文中匹配关键词，
        不依赖 embedding，因此不会与 bge-m3 的向量维度产生冲突。

        Args:
            keywords: 关键词列表，多个关键词以 OR 关系匹配
            top_k: 返回结果数量
            filters: 元数据过滤条件

        Returns:
            命中的知识条目列表

        Raises:
            VectorStoreError: 检索失败
        """
        clean_keywords = [k.strip() for k in keywords if k and k.strip()]
        if not clean_keywords:
            return []

        try:
            document_filter: dict[str, Any]
            if len(clean_keywords) == 1:
                document_filter = {"$contains": clean_keywords[0]}
            else:
                document_filter = {
                    "$or": [{"$contains": k} for k in clean_keywords]
                }

            where_meta = self._build_where_filter(filters) if filters else None

            # 注意: 文档内字面匹配属于 where_document，元数据过滤属于 where，
            # 二者是并列参数，不能混在同一个 where 条件里。
            results = self.collection.get(
                where=where_meta,
                where_document=document_filter,
                limit=top_k,
                include=["documents", "metadatas"],
            )

            items: list[KnowledgeItem] = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][i] if results["metadatas"] else {}
                    document = results["documents"][i] if results["documents"] else ""
                    items.append(self._metadata_to_item(doc_id, metadata, document))

            logger.debug(
                "关键词检索完成 | keywords={} | found={}",
                clean_keywords, len(items)
            )
            return items

        except Exception as e:
            logger.error("关键词检索失败 | error={}", str(e))
            raise VectorStoreError(f"关键词检索失败: {e}") from e

    async def delete(self, ids: list[str]) -> None:
        """
        删除指定文档

        Args:
            ids: 文档 ID 列表

        Raises:
            VectorStoreError: 删除失败
        """
        if not ids:
            return

        try:
            self.collection.delete(ids=ids)
            logger.info("删除文档 | count={}", len(ids))
        except Exception as e:
            logger.error("删除文档失败 | error={}", str(e))
            raise VectorStoreError(f"删除文档失败: {e}") from e

    async def clear(self) -> None:
        """
        清空向量库

        Raises:
            VectorStoreError: 清空失败
        """
        try:
            # 删除并重新创建集合
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("向量库已清空")
        except Exception as e:
            logger.error("清空向量库失败 | error={}", str(e))
            raise VectorStoreError(f"清空向量库失败: {e}") from e

    async def count(self) -> int:
        """
        获取文档总数

        Returns:
            文档数量
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error("获取文档数量失败 | error={}", str(e))
            return 0

    def _build_where_filter(
        self,
        filters: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """
        构建 ChromaDB 的 where 过滤条件

        Args:
            filters: 过滤条件字典

        Returns:
            ChromaDB where 条件
        """
        if not filters:
            return None

        # 简单转换：{"type": "button"} -> {"type": {"$eq": "button"}}
        where_clauses = []
        for key, value in filters.items():
            if isinstance(value, list):
                # 多值过滤：{"tags": ["tag1", "tag2"]}
                where_clauses.append({key: {"$in": value}})
            else:
                where_clauses.append({key: {"$eq": value}})

        if len(where_clauses) == 1:
            return where_clauses[0]
        elif len(where_clauses) > 1:
            return {"$and": where_clauses}

        return None

    def _metadata_to_item(
        self,
        doc_id: str,
        metadata: dict,
        document: str,
    ) -> KnowledgeItem:
        """
        将元数据转换为 KnowledgeItem

        Args:
            doc_id: 文档 ID
            metadata: 元数据字典
            document: 文档内容

        Returns:
            KnowledgeItem 对象
        """
        from src.domain.enums import KnowledgeType

        item_type = KnowledgeType.MANUAL
        try:
            if metadata.get("type"):
                item_type = KnowledgeType(metadata["type"])
        except ValueError:
            pass

        tags_str = metadata.get("tags", "")
        tags = tags_str.split(",") if tags_str else []

        return KnowledgeItem(
            id=doc_id,
            type=item_type,
            title=metadata.get("title", ""),
            content=document,
            page_name=metadata.get("page_name") or None,
            page_path=metadata.get("page_path") or None,
            source_file=metadata.get("source_file") or None,
            tags=tags,
        )
