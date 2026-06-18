"""RAG 模块

提供检索增强生成功能，包括：
- Embedding 服务
- 向量存储 (ChromaDB)
- 混合检索器
- 上下文组装
- RAG 主流程
"""

from src.rag.context import ContextAssembler
from src.rag.embedding import EmbeddingService
from src.rag.pipeline import RAGPipeline, RAGPipelineBuilder, RAGResult
from src.rag.retriever import HybridRetriever, SimpleRetriever
from src.rag.vectorstore import ChromaVectorStore

__all__ = [
    "EmbeddingService",
    "ChromaVectorStore",
    "HybridRetriever",
    "SimpleRetriever",
    "ContextAssembler",
    "RAGPipeline",
    "RAGPipelineBuilder",
    "RAGResult",
]
