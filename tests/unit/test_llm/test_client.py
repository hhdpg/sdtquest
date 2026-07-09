"""Ollama 客户端单元测试模块。

测试 OllamaClient 的生成、嵌入、流式生成等功能（mock HTTP 调用）。
"""

import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.exceptions import LLMServiceError
from src.domain.ports import GenerateOptions
from src.llm.client import OllamaClient


class TestOllamaClientInit:
    """初始化测试"""

    def test_init_defaults(self):
        """测试默认初始化"""
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "qwen3.5:35b-a3b-instruct-4bit"
        assert client.timeout == 120
        assert client.max_concurrent == 2

    def test_init_custom(self):
        """测试自定义参数"""
        client = OllamaClient(
            base_url="http://custom:11434",
            model="custom-model",
            timeout=60,
            max_concurrent=4,
        )
        assert client.base_url == "http://custom:11434"
        assert client.model == "custom-model"
        assert client.timeout == 60
        assert client.max_concurrent == 4


class TestOllamaClientGenerate:
    """文本生成测试"""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """测试成功生成"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "生成的文本", "eval_count": 10}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.generate("提示词")

            assert result == "生成的文本"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_options(self):
        """测试带选项的生成"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "文本"}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            options = GenerateOptions(temperature=0.5, max_tokens=100, top_p=0.9)
            await client.generate("提示", options=options)

            # 验证 payload 包含选项
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["options"]["temperature"] == 0.5
            assert payload["options"]["num_predict"] == 100

    @pytest.mark.asyncio
    async def test_generate_timeout_raises(self):
        """测试超时抛出异常"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("超时"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            with pytest.raises(LLMServiceError, match="超时"):
                await client.generate("提示")

    @pytest.mark.asyncio
    async def test_generate_connection_error_raises(self):
        """测试连接错误抛出异常"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("连接失败"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            with pytest.raises(LLMServiceError, match="无法连接"):
                await client.generate("提示")


class TestOllamaClientEmbed:
    """文本向量化测试"""

    @pytest.mark.asyncio
    async def test_embed_success(self):
        """测试成功向量化"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.embed(["测试文本"])

            assert len(result) == 1
            assert result[0] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self):
        """测试批量向量化"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "embeddings": [[0.1, 0.2], [0.3, 0.4]]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.embed(["文本1", "文本2"])

            assert len(result) == 2


class TestOllamaClientHealth:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """测试健康检查成功"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """测试健康检查失败"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("失败"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.health_check()
            assert result is False


class TestOllamaClientListModels:
    """列出模型测试"""

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        """测试成功列出模型"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [{"name": "model1"}, {"name": "model2"}]
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.list_models()
            assert "model1" in result
            assert "model2" in result

    @pytest.mark.asyncio
    async def test_list_models_error_returns_empty(self):
        """测试错误时返回空列表"""
        with patch("src.llm.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("失败"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            client = OllamaClient()
            result = await client.list_models()
            assert result == []
