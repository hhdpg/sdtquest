"""HTTP 客户端工厂单元测试。

回归保护: 桌面端会向子进程注入 HTTP_PROXY/HTTPS_PROXY，指向本机随机端口
的代理。若业务请求走该代理，桌面端重启（代理端口变化）后旧进程会连不上，
导致钉钉机器人静默失联（本地 /health 仍 200）。因此业务客户端必须
trust_env=False，直连目标服务。
"""

import httpx
import pytest

from src.shared.http import create_direct_client


class TestCreateDirectClient:
    """直连客户端工厂"""

    def test_trust_env_disabled(self):
        """必须禁用环境变量代理"""
        client = create_direct_client(timeout=30.0)

        assert isinstance(client, httpx.AsyncClient)
        assert client.trust_env is False

    def test_timeout_applied(self):
        """超时应按传入值设置"""
        client = create_direct_client(timeout=12.5)

        assert client.timeout.read == 12.5

    @pytest.mark.asyncio
    async def test_ignores_proxy_env(self, monkeypatch):
        """即使设置了代理环境变量，客户端也不应使用它"""
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")

        async with create_direct_client(timeout=5.0) as client:
            # trust_env=False 时 httpx 不会读取 proxy 环境变量
            assert client.trust_env is False
            assert client._trust_env is False
