"""LLM 服务模块

提供与大语言模型交互的客户端和 Prompt 模板管理。

主要组件:
- OllamaClient: Ollama API 客户端
- PromptTemplate: Prompt 模板类
- PromptManager: Prompt 管理器
"""

from src.llm.client import OllamaClient
from src.llm.templates import PromptManager, PromptTemplate, prompt_manager

__all__ = [
    "OllamaClient",
    "PromptTemplate",
    "PromptManager",
    "prompt_manager",
]
