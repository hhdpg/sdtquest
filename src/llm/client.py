"""Ollama API 客户端模块

封装 Ollama HTTP API 的异步调用，支持：
- 文本生成 (generate)
- 流式生成 (generate_stream)
- 批量向量化 (embed)
- 超时控制和并发限制
"""

import asyncio
from typing import AsyncIterator

import httpx
from loguru import logger

from src.config import settings
from src.domain.exceptions import LLMServiceError
from src.domain.ports import GenerateOptions


class OllamaClient:
    """
    Ollama API 客户端

    实现 LLMClient 接口，封装 Ollama HTTP API 调用。

    Attributes:
        base_url: Ollama 服务地址
        model: 默认使用的模型名称
        timeout: 请求超时时间（秒）
        max_concurrent: 最大并发数
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_concurrent: int | None = None,
    ):
        """
        初始化 Ollama 客户端

        Args:
            base_url: Ollama 服务地址，默认从配置读取
            model: 默认模型名称，默认从配置读取
            timeout: 请求超时时间（秒），默认从配置读取
            max_concurrent: 最大并发数，默认从配置读取
        """
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self.max_concurrent = max_concurrent or settings.OLLAMA_MAX_CONCURRENT

        # 并发控制信号量
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        logger.info(
            "OllamaClient 初始化 | base_url={} | model={} | timeout={}s | max_concurrent={}",
            self.base_url, self.model, self.timeout, self.max_concurrent
        )

    async def generate(
        self,
        prompt: str,
        options: GenerateOptions | None = None,
        model: str | None = None,
    ) -> str:
        """
        生成文本

        Args:
            prompt: LLM 提示词
            options: 生成选项（temperature, max_tokens 等）
            model: 模型名称，可选，默认使用初始化时的模型

        Returns:
            生成的文本

        Raises:
            LLMServiceError: LLM 服务调用失败
        """
        async with self._semaphore:
            try:
                opts = options or GenerateOptions()
                target_model = model or self.model

                payload = {
                    "model": target_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": opts.temperature,
                        "num_predict": opts.max_tokens,
                        "top_p": opts.top_p,
                    },
                }

                if opts.stop:
                    payload["options"]["stop"] = opts.stop

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                text = result.get("response", "")
                logger.debug(
                    "LLM 生成完成 | model={} | tokens={} | text_len={}",
                    target_model, result.get("eval_count", 0), len(text)
                )
                return text

            except httpx.TimeoutException as e:
                logger.error("LLM 生成超时 | timeout={}s", self.timeout)
                raise LLMServiceError(f"LLM 生成超时 ({self.timeout}s)") from e
            except httpx.HTTPStatusError as e:
                logger.error(
                    "LLM HTTP 错误 | status={} | error={}",
                    e.response.status_code, str(e)
                )
                raise LLMServiceError(
                    f"LLM HTTP 错误: {e.response.status_code}"
                ) from e
            except httpx.ConnectError as e:
                logger.error("LLM 连接失败 | url={}", self.base_url)
                raise LLMServiceError(
                    f"无法连接到 Ollama 服务: {self.base_url}"
                ) from e
            except Exception as e:
                logger.error("LLM 生成失败 | error={}", str(e))
                raise LLMServiceError(f"LLM 生成失败: {e}") from e

    async def generate_stream(
        self,
        prompt: str,
        options: GenerateOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """
        流式生成文本

        Args:
            prompt: LLM 提示词
            options: 生成选项
            model: 模型名称

        Yields:
            生成的文本片段

        Raises:
            LLMServiceError: LLM 服务调用失败
        """
        async with self._semaphore:
            try:
                opts = options or GenerateOptions()
                target_model = model or self.model

                payload = {
                    "model": target_model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": opts.temperature,
                        "num_predict": opts.max_tokens,
                        "top_p": opts.top_p,
                    },
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/api/generate",
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line:
                                import json
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                                if data.get("done", False):
                                    break

            except httpx.TimeoutException as e:
                logger.error("LLM 流式生成超时")
                raise LLMServiceError("LLM 流式生成超时") from e
            except Exception as e:
                logger.error("LLM 流式生成失败 | error={}", str(e))
                raise LLMServiceError(f"LLM 流式生成失败: {e}") from e

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        批量向量化文本

        Args:
            texts: 待向量化的文本列表
            model: Embedding 模型名称，默认使用配置中的 Embedding 模型

        Returns:
            向量列表

        Raises:
            LLMServiceError: LLM 服务调用失败
        """
        async with self._semaphore:
            try:
                target_model = model or settings.OLLAMA_EMBEDDING_MODEL

                payload = {
                    "model": target_model,
                    "input": texts,
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/api/embed",
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()

                embeddings = result.get("embeddings", [])
                logger.debug(
                    "Embedding 完成 | model={} | texts={} | dims={}",
                    target_model, len(texts),
                    len(embeddings[0]) if embeddings else 0
                )
                return embeddings

            except httpx.TimeoutException as e:
                logger.error("Embedding 超时")
                raise LLMServiceError("Embedding 超时") from e
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Embedding HTTP 错误 | status={}",
                    e.response.status_code
                )
                raise LLMServiceError(
                    f"Embedding HTTP 错误: {e.response.status_code}"
                ) from e
            except Exception as e:
                logger.error("Embedding 失败 | error={}", str(e))
                raise LLMServiceError(f"Embedding 失败: {e}") from e

    async def health_check(self) -> bool:
        """
        检查 Ollama 服务是否可用

        Returns:
            True 表示服务可用，False 表示不可用
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """
        列出可用的模型

        Returns:
            模型名称列表
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                result = response.json()
                return [m["name"] for m in result.get("models", [])]
        except Exception as e:
            logger.error("获取模型列表失败 | error={}", str(e))
            return []
