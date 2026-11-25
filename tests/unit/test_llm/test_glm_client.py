"""GLM 客户端单元测试模块。

测试 GLMClient 的生成、向量化与错误处理（mock HTTP 调用）。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.domain.exceptions import LLMServiceError
from src.domain.ports import GenerateOptions
from src.llm.glm_client import GLMClient


def make_client(**kwargs) -> GLMClient:
    """创建测试用客户端（固定参数，避免受 .env 影响）"""
    defaults = dict(
        api_key="test-key",
        base_url="https://api.test/v4",
        model="glm-test",
        embedding_model="embedding-test",
        embedding_dimensions=512,
        timeout=30,
        max_concurrent=2,
    )
    defaults.update(kwargs)
    return GLMClient(**defaults)


class TestGLMClientInit:
    """初始化测试"""

    def test_init_custom(self):
        """自定义参数应正确保存"""
        client = make_client()
        assert client.base_url == "https://api.test/v4"
        assert client.model == "glm-test"
        assert client.embedding_dimensions == 512
        assert client.timeout == 30

    def test_base_url_trailing_slash_stripped(self):
        """base_url 末尾斜杠应被去掉，避免拼出 //"""
        client = make_client(base_url="https://api.test/v4/")
        assert client.base_url == "https://api.test/v4"

    def test_headers_without_key_raises(self):
        """未配置 API Key 时构造请求头应直接报错"""
        client = make_client(api_key="")
        with pytest.raises(LLMServiceError, match="GLM_API_KEY"):
            client._headers()

    def test_headers_with_key(self):
        """正常配置时应带 Bearer 头"""
        headers = make_client()._headers()
        assert headers["Authorization"] == "Bearer test-key"


class TestGLMGenerate:
    """文本生成测试"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """正常返回 choices[0].message.content"""
        client = make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "这是回答"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 10},
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            result = await client.generate("你好", GenerateOptions(temperature=0.3))

        assert result == "这是回答"
        # 校验请求落在 chat/completions 且带 model/messages
        call_kwargs = mock_http.post.call_args
        assert call_kwargs.args[0].endswith("/chat/completions")
        assert call_kwargs.kwargs["json"]["model"] == "glm-test"

    @pytest.mark.asyncio
    async def test_generate_empty_choices_raises(self):
        """无 choices 应报错，不能静默返回空串"""
        client = make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError):
                await client.generate("你好")

    @pytest.mark.asyncio
    async def test_generate_timeout_raises(self):
        """超时应转为 LLMServiceError"""
        client = make_client()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError, match="超时"):
                await client.generate("你好")

    @pytest.mark.asyncio
    async def test_generate_401_hint(self):
        """401 应带出可操作的提示"""
        client = make_client()
        request = httpx.Request("POST", "https://api.test/v4/chat/completions")
        response = httpx.Response(401, request=request, text="unauthorized")

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("401", request=request, response=response)
        )
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError, match="API Key"):
                await client.generate("你好")

    @pytest.mark.asyncio
    async def test_generate_429_hint(self):
        """429 应提示免费模型限流，而不是笼统的并发过高"""
        client = make_client()
        request = httpx.Request("POST", "https://api.test/v4/chat/completions")
        response = httpx.Response(429, request=request, text='{"error":{"code":"1305"}}')

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("429", request=request, response=response)
        )
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError, match="限流"):
                await client.generate("你好")


class TestGLMEmbed:
    """向量化测试"""

    @pytest.mark.asyncio
    async def test_embed_success_sorted_by_index(self):
        """应按 index 排序，保证与输入顺序一致"""
        client = make_client()
        mock_response = MagicMock()
        # 故意乱序返回
        mock_response.json.return_value = {
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            result = await client.embed(["文本0", "文本1"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        # 请求应带 dimensions
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["dimensions"] == 512

    @pytest.mark.asyncio
    async def test_embed_empty_returns_empty(self):
        """空输入应直接返回，不发请求"""
        client = make_client()
        assert await client.embed([]) == []

    @pytest.mark.asyncio
    async def test_embed_batching(self):
        """超过 64 条应分批"""
        client = make_client()
        texts = [f"t{i}" for i in range(70)]

        def fake_post(url, headers=None, json=None):
            n = len(json["input"])
            resp = MagicMock()
            resp.json.return_value = {
                "data": [{"index": i, "embedding": [0.0]} for i in range(n)]
            }
            resp.raise_for_status = MagicMock()
            return resp

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=fake_post)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            result = await client.embed(texts)

        assert len(result) == 70
        assert mock_http.post.call_count == 2  # 64 + 6


class TestGLMFallback:
    """429 降级逻辑测试"""

    @staticmethod
    def _ok_response(text: str) -> MagicMock:
        r = MagicMock()
        r.json.return_value = {
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}]
        }
        r.raise_for_status = MagicMock()
        return r

    @staticmethod
    def _429_error() -> httpx.HTTPStatusError:
        req = httpx.Request("POST", "https://api.test/v4/chat/completions")
        resp = httpx.Response(429, request=req, text='{"error":{"code":"1305"}}')
        return httpx.HTTPStatusError("429", request=req, response=resp)

    @pytest.mark.asyncio
    async def test_falls_back_on_429(self):
        """主模型 429 时应自动用备用模型"""
        client = make_client(model="primary", fallback_models=["backup"])
        calls = []

        async def fake_post(url, headers=None, json=None):
            calls.append(json["model"])
            if json["model"] == "primary":
                raise self._429_error()
            return self._ok_response("备用模型答案")

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=fake_post)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            result = await client.generate("问题")

        assert result == "备用模型答案"
        assert calls == ["primary", "backup"]

    @pytest.mark.asyncio
    async def test_all_429_raises(self):
        """全部限流应抛错且提示降级链路"""
        client = make_client(model="p", fallback_models=["b1", "b2"])

        async def always_429(url, headers=None, json=None):
            raise self._429_error()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=always_429)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError, match="限流"):
                await client.generate("问题")

        assert mock_http.post.call_count == 3  # 主 + 2 备用

    @pytest.mark.asyncio
    async def test_explicit_model_no_fallback(self):
        """显式指定 model 时不降级，直接抛 429"""
        client = make_client(model="primary", fallback_models=["backup"])

        async def always_429(url, headers=None, json=None):
            raise self._429_error()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=always_429)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError):
                await client.generate("问题", model="specific")

        assert mock_http.post.call_count == 1

    @pytest.mark.asyncio
    async def test_401_not_retried(self):
        """401 不应触发降级（避免掩盖配置错误）"""
        client = make_client(model="p", fallback_models=["b"])
        req = httpx.Request("POST", "https://api.test/v4/chat/completions")
        resp = httpx.Response(401, request=req, text="unauth")

        async def fail(url, headers=None, json=None):
            raise httpx.HTTPStatusError("401", request=req, response=resp)

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=fail)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("src.llm.glm_client.create_direct_client", return_value=mock_http):
            with pytest.raises(LLMServiceError, match="API Key"):
                await client.generate("问题")

        assert mock_http.post.call_count == 1


class TestGLMThinking:
    """思考模式开关测试"""

    @pytest.mark.asyncio
    async def test_thinking_disabled_by_default(self):
        """默认应下发 thinking.type=disabled 避免推理吃光输出"""
        client = make_client(thinking=False)
        payload = client._build_chat_payload("m", "p", GenerateOptions(), stream=False)
        assert payload["thinking"] == {"type": "disabled"}

    @pytest.mark.asyncio
    async def test_thinking_enabled(self):
        """开启时应下发 enabled"""
        client = make_client(thinking=True)
        payload = client._build_chat_payload("m", "p", GenerateOptions(), stream=False)
        assert payload["thinking"] == {"type": "enabled"}


class TestGLMHealth:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_without_key_false(self):
        """无 Key 直接判定不可用，不发请求"""
        assert await make_client(api_key="").health_check() is False

    @pytest.mark.asyncio
    async def test_list_models(self):
        """返回配置中的模型"""
        models = await make_client().list_models()
        assert "glm-test" in models
        assert "embedding-test" in models
