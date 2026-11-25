"""智谱 GLM 客户端模块

封装智谱开放平台（OpenAI 兼容）HTTP API，支持：
- 文本生成 (generate)
- 流式生成 (generate_stream)
- 批量向量化 (embed)
- 超时控制和并发限制

与 OllamaClient 实现同一套 LLMClient 协议，可被上层无差别替换。

接口约定（智谱 v4）：
- 对话: POST {base}/chat/completions
- 向量: POST {base}/embeddings
- 鉴权: Authorization: Bearer <API_KEY>
"""

import json
from typing import AsyncIterator

import httpx
from loguru import logger

from src.config import settings
from src.domain.exceptions import LLMServiceError
from src.domain.ports import GenerateOptions
from src.shared.http import create_direct_client


class GLMClient:
    """
    智谱 GLM API 客户端

    实现 LLMClient 协议，封装智谱开放平台的对话与向量化接口。

    Attributes:
        base_url: API 根地址（不含 /chat/completions）
        api_key: 智谱 API Key
        model: 默认对话模型
        embedding_model: 默认向量化模型
        timeout: 请求超时（秒）
        max_concurrent: 最大并发数
    """

    # 智谱单次 embedding 请求最多 64 条文本
    EMBED_BATCH_LIMIT = 64

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
        timeout: int | None = None,
        max_concurrent: int | None = None,
        thinking: bool | None = None,
        fallback_models: list[str] | None = None,
    ):
        """
        初始化 GLM 客户端。

        Args:
            api_key: 智谱 API Key，默认从配置读取
            base_url: API 根地址，默认从配置读取
            model: 对话模型名，默认从配置读取
            embedding_model: 向量模型名，默认从配置读取
            embedding_dimensions: 向量维度，默认从配置读取
            timeout: 请求超时秒数，默认从配置读取
            max_concurrent: 最大并发数，默认从配置读取
            thinking: 是否开启思考模式，默认从配置读取（问答应关闭）
            fallback_models: 主模型 429 时的降级模型列表，默认从配置读取
        """
        import asyncio

        self.api_key = api_key if api_key is not None else settings.GLM_API_KEY
        self.base_url = (base_url or settings.GLM_BASE_URL).rstrip("/")
        self.model = model or settings.GLM_MODEL
        self.embedding_model = embedding_model or settings.GLM_EMBEDDING_MODEL
        self.embedding_dimensions = (
            embedding_dimensions
            if embedding_dimensions is not None
            else settings.GLM_EMBEDDING_DIMENSIONS
        )
        self.timeout = timeout or settings.GLM_TIMEOUT
        self.max_concurrent = max_concurrent or settings.GLM_MAX_CONCURRENT
        self.thinking = settings.GLM_THINKING if thinking is None else thinking

        if fallback_models is None:
            fallback_models = [
                m.strip() for m in (settings.GLM_FALLBACK_MODELS or "").split(",")
                if m.strip()
            ]
        self.fallback_models = fallback_models

        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        logger.info(
            "GLMClient 初始化 | base_url={} | model={} | fallback={} | thinking={} | "
            "embedding={}({}维) | timeout={}s | max_concurrent={} | configured={}",
            self.base_url, self.model, self.fallback_models, self.thinking,
            self.embedding_model, self.embedding_dimensions,
            self.timeout, self.max_concurrent, bool(self.api_key),
        )

    # ── 内部辅助 ──────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        """构造请求头（缺少 API Key 时尽早失败，避免发无效请求）"""
        if not self.api_key:
            raise LLMServiceError(
                "GLM API Key 未配置，请在 .env 设置 GLM_API_KEY"
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_chat_payload(
        self,
        model: str,
        prompt: str,
        opts: GenerateOptions,
        stream: bool,
    ) -> dict:
        """构造对话请求体（含 thinking 开关）"""
        payload: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": opts.temperature,
            "max_tokens": min(opts.max_tokens, settings.LLM_MAX_TOKENS),
            "stream": stream,
            # 免费模型如 glm-4.7-flash 默认带推理，会吃掉输出配额，问答场景关闭
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
        }
        if opts.top_p is not None:
            payload["top_p"] = opts.top_p
        if opts.stop:
            payload["stop"] = opts.stop
        return payload

    async def _chat_once(self, model: str, payload: dict) -> dict:
        """单次非流式对话请求，返回原始 JSON"""
        async with create_direct_client(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def generate(
        self,
        prompt: str,
        options: GenerateOptions | None = None,
        model: str | None = None,
    ) -> str:
        """
        生成文本。

        主模型遇到 429（免费模型访问量过大）时，按 fallback_models 顺序自动降级，
        任一模型成功即返回。全部失败才抛错。降级只针对 429，其他错误立即上抛，
        避免把真实配置错误（如 401）藏在重试里。

        Args:
            prompt: 提示词
            options: 生成选项（temperature / max_tokens / top_p / stop）
            model: 模型名，默认使用初始化时的模型

        Returns:
            生成的文本

        Raises:
            LLMServiceError: 调用失败
        """
        async with self._semaphore:
            opts = options or GenerateOptions()
            primary = model or self.model

            # 显式指定 model 时只用它（调用方意图明确，不做降级）
            if model is not None:
                chain = [model]
            else:
                chain = [primary] + [m for m in self.fallback_models if m != primary]

            last_429: httpx.HTTPStatusError | None = None
            for idx, target_model in enumerate(chain):
                payload = self._build_chat_payload(target_model, prompt, opts, stream=False)
                try:
                    result = await self._chat_once(target_model, payload)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and idx < len(chain) - 1:
                        last_429 = e
                        logger.warning(
                            "GLM 模型限流，尝试降级 | model={} | next={}",
                            target_model, chain[idx + 1],
                        )
                        continue
                    if e.response.status_code == 429:
                        self._raise_429(e, chain)
                    hint = {401: "API Key 无效或已过期"}.get(e.response.status_code, "")
                    logger.error(
                        "GLM HTTP 错误 | status={} | hint={} | body={}",
                        e.response.status_code, hint, e.response.text[:200],
                    )
                    raise LLMServiceError(
                        f"GLM HTTP 错误: {e.response.status_code}"
                        f"{(' - ' + hint) if hint else ''}"
                    ) from e
                except httpx.TimeoutException as e:
                    logger.error("GLM 生成超时 | model={} | timeout={}s", target_model, self.timeout)
                    raise LLMServiceError(f"GLM 生成超时 ({self.timeout}s)") from e
                except httpx.ConnectError as e:
                    logger.error("GLM 连接失败 | url={}", self.base_url)
                    raise LLMServiceError(f"无法连接 GLM 服务: {self.base_url}") from e
                except LLMServiceError:
                    raise
                except Exception as e:
                    logger.error("GLM 生成失败 | error={}", str(e))
                    raise LLMServiceError(f"GLM 生成失败: {e}") from e

                # 解析响应
                choices = result.get("choices") or []
                if not choices:
                    raise LLMServiceError(f"GLM 返回无 choices: {result}")

                message = choices[0].get("message") or {}
                text = message.get("content") or ""

                if not text.strip() and message.get("reasoning_content"):
                    logger.warning(
                        "GLM 回答为空但存在推理内容 | model={} | finish_reason={}",
                        target_model, choices[0].get("finish_reason"),
                    )
                    raise LLMServiceError(
                        "GLM 未产出正式回答（推理过程占用了输出配额），"
                        "请调大 LLM_MAX_TOKENS 或关闭思考模式"
                    )

                if idx > 0:
                    logger.info("GLM 降级成功 | used={} | original={}", target_model, primary)

                logger.debug(
                    "GLM 生成完成 | model={} | tokens={} | text_len={}",
                    target_model,
                    (result.get("usage") or {}).get("completion_tokens", 0),
                    len(text),
                )
                return text

            # 理论上不可达（最后一个 429 已在循环内抛出），兜底
            self._raise_429(last_429, chain)

    def _raise_429(self, exc: httpx.HTTPStatusError | None, chain: list[str]) -> None:
        """构造限流错误（含降级链路说明），供多处复用"""
        logger.error(
            "GLM 全部模型限流 | chain={} | body={}",
            chain, exc.response.text[:150] if exc else "",
        )
        raise LLMServiceError(
            f"GLM 限流：模型 {', '.join(chain)} 当前访问量过大（免费模型高峰期常见）。"
            f"请稍后重试，或在 .env 换用稳定模型 glm-4-flash-250414"
        ) from (exc if exc else None)

    async def generate_stream(
        self,
        prompt: str,
        options: GenerateOptions | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """
        流式生成文本（SSE）。

        Args:
            prompt: 提示词
            options: 生成选项
            model: 模型名

        Yields:
            文本片段

        Raises:
            LLMServiceError: 调用失败
        """
        async with self._semaphore:
            try:
                opts = options or GenerateOptions()
                target_model = model or self.model
                payload = self._build_chat_payload(target_model, prompt, opts, stream=True)

                async with create_direct_client(timeout=self.timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[len("data:"):].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            for choice in chunk.get("choices") or []:
                                delta = choice.get("delta") or {}
                                piece = delta.get("content")
                                if piece:
                                    yield piece

            except httpx.TimeoutException as e:
                logger.error("GLM 流式生成超时")
                raise LLMServiceError("GLM 流式生成超时") from e
            except Exception as e:
                logger.error("GLM 流式生成失败 | error={}", str(e))
                raise LLMServiceError(f"GLM 流式生成失败: {e}") from e

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        批量向量化。

        自动按智谱限制（单次 64 条）分批，返回顺序与输入一致。

        Args:
            texts: 文本列表
            model: 向量模型名，默认使用配置值

        Returns:
            向量列表

        Raises:
            LLMServiceError: 调用失败
        """
        if not texts:
            return []

        async with self._semaphore:
            try:
                target_model = model or self.embedding_model
                all_embeddings: list[list[float]] = []

                for start in range(0, len(texts), self.EMBED_BATCH_LIMIT):
                    batch = texts[start:start + self.EMBED_BATCH_LIMIT]
                    payload = {
                        "model": target_model,
                        "input": batch,
                        "dimensions": self.embedding_dimensions,
                    }

                    async with create_direct_client(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.base_url}/embeddings",
                            headers=self._headers(),
                            json=payload,
                        )
                        response.raise_for_status()
                        result = response.json()

                    data = result.get("data") or []
                    # 按 index 排序，保证与输入顺序一致
                    data.sort(key=lambda d: d.get("index", 0))
                    all_embeddings.extend([d.get("embedding") or [] for d in data])

                if len(all_embeddings) != len(texts):
                    logger.warning(
                        "GLM 向量数量与输入不一致 | input={} | output={}",
                        len(texts), len(all_embeddings),
                    )

                logger.debug(
                    "GLM Embedding 完成 | model={} | texts={} | dims={}",
                    target_model, len(texts),
                    len(all_embeddings[0]) if all_embeddings else 0,
                )
                return all_embeddings

            except httpx.TimeoutException as e:
                logger.error("GLM Embedding 超时")
                raise LLMServiceError("GLM Embedding 超时") from e
            except httpx.HTTPStatusError as e:
                logger.error(
                    "GLM Embedding HTTP 错误 | status={} | body={}",
                    e.response.status_code, e.response.text[:200],
                )
                raise LLMServiceError(
                    f"GLM Embedding HTTP 错误: {e.response.status_code}"
                ) from e
            except LLMServiceError:
                raise
            except Exception as e:
                logger.error("GLM Embedding 失败 | error={}", str(e))
                raise LLMServiceError(f"GLM Embedding 失败: {e}") from e

    async def health_check(self) -> bool:
        """
        检查 GLM 服务是否可用。

        用一个极小的对话请求探测，避免额外依赖。

        Returns:
            True 表示可用
        """
        if not self.api_key:
            return False
        try:
            async with create_direct_client(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """
        列出模型。

        智谱 v4 未提供稳定的模型列表接口，这里返回配置中的已知模型，
        供上层展示与选择使用。

        Returns:
            模型名列表
        """
        return [self.model, self.embedding_model]
