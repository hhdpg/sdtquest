"""HTTP 客户端工厂。

统一创建对本机/国内服务发起的 HTTP 客户端。

**为什么需要这个模块**

桌面端（丰知 Code 等）会向子进程注入 HTTP_PROXY / HTTPS_PROXY 环境变量，
指向一个本机随机端口的代理。httpx 默认读取这些变量（trust_env=True），
于是发往本地 Ollama、钉钉等国内服务的请求也会绕经该代理。

这会带来实际问题：
- 桌面端重启后代理端口变化，旧进程仍连已关闭的旧端口，导致服务失联
  （表现为钉钉机器人无响应，但本地 HTTP 健康检查仍返回 200）
- 本地服务（127.0.0.1）与国内服务本就不需要代理

因此本项目的业务出站请求统一使用这里创建的客户端（trust_env=False）。

依赖下载（uv / pip）等场景仍需代理，那部分不受本模块影响。
"""

import httpx


def create_direct_client(timeout: float) -> httpx.AsyncClient:
    """
    创建直连 HTTP 客户端（忽略系统代理环境变量）。

    Args:
        timeout: 请求超时时间（秒）

    Returns:
        配置了 trust_env=False 的 AsyncClient

    Example:
        >>> async with create_direct_client(timeout=30.0) as client:
        ...     response = await client.post(url, json=payload)
    """
    return httpx.AsyncClient(timeout=timeout, trust_env=False)
