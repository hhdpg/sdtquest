"""DingTalkClient 单元测试模块。

重点覆盖历史上曾导致消息无法发出的缺陷:
1. msgParam 曾用 str(dict).replace("'", '"') 拼接，内容含引号/换行时
   会产生非法 JSON 被钉钉拒绝 —— 必须使用 json.dumps。
2. 发送消息时 @ 提问人需要同时写入正文 @userId 与 atUserIds。
3. session_webhook 回复通道。

所有 HTTP 调用均被 mock，不依赖真实钉钉服务。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.domain.exceptions import DingTalkAPIError
from src.infrastructure.external.dingtalk_client import DingTalkClient


def make_response(payload: dict, status_code: int = 200) -> MagicMock:
    """构造 mock httpx 响应"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = json.dumps(payload, ensure_ascii=False)
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status = MagicMock()
    return response


class TestMsgParamSerialization:
    """msgParam 必须是合法 JSON（历史缺陷回归）"""

    @pytest.fixture
    def client(self) -> DingTalkClient:
        return DingTalkClient(app_key="test_key", app_secret="test_secret", robot_code="test_robot")

    @staticmethod
    def _capture_payload(mock_client_cls: MagicMock) -> dict:
        """从 mock 的 httpx 调用中取出请求 body"""
        mock_client = mock_client_cls.return_value
        return mock_client.post.call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_msg_param_is_valid_json_with_apostrophe(self, client: DingTalkClient):
        """内容含英文撇号时 msgParam 仍须是合法 JSON

        回归保护: 旧实现用 str().replace("'", '"')，会把 "it's" 变成
        "it"s" 导致 JSON 非法，钉钉接口直接 400。
        """
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_markdown(
                    open_conversation_id="cid",
                    title="回答",
                    text="It's a test, don't panic",
                )

            body = self._capture_payload(mock_cls)
            parsed = json.loads(body["msgParam"])  # 非法 JSON 会抛异常
            assert parsed["text"] == "It's a test, don't panic"

    @pytest.mark.asyncio
    async def test_msg_param_is_valid_json_with_newline(self, client: DingTalkClient):
        """内容含换行符时 msgParam 仍须是合法 JSON"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_markdown(
                    open_conversation_id="cid",
                    title="标题",
                    text="第一行\n第二行\n第三行",
                )

            body = self._capture_payload(mock_cls)
            parsed = json.loads(body["msgParam"])
            assert parsed["text"].count("\n") == 2

    @pytest.mark.asyncio
    async def test_msg_param_preserves_chinese(self, client: DingTalkClient):
        """中文不能被转义成 \\uXXXX（ensure_ascii=False）"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_text(open_conversation_id="cid", content="创建订单")

            body = self._capture_payload(mock_cls)
            assert "创建订单" in body["msgParam"]


class TestAtUserSupport:
    """@ 提问人支持"""

    @pytest.fixture
    def client(self) -> DingTalkClient:
        return DingTalkClient(app_key="k", app_secret="s", robot_code="r")

    @pytest.mark.asyncio
    async def test_send_text_with_at_user(self, client: DingTalkClient):
        """文本消息 @ 用户时，正文应含 @userId 且 body 声明 atUserIds"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_text(
                    open_conversation_id="cid",
                    content="这是回答",
                    at_user_ids=["user_456"],
                )

            body = mock_cls.return_value.post.call_args.kwargs["json"]
            parsed = json.loads(body["msgParam"])
            assert "@user_456" in parsed["content"]
            assert parsed["atUserIds"] == ["user_456"]
            assert body["atUserIds"] == ["user_456"]

    @pytest.mark.asyncio
    async def test_send_markdown_with_at_user(self, client: DingTalkClient):
        """Markdown 消息 @ 用户时同样写入正文与 atUserIds"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_markdown(
                    open_conversation_id="cid",
                    title="回答",
                    text="**答案**",
                    at_user_ids=["user_456"],
                )

            body = mock_cls.return_value.post.call_args.kwargs["json"]
            parsed = json.loads(body["msgParam"])
            assert parsed["text"].startswith("@user_456")
            assert parsed["atUserIds"] == ["user_456"]

    @pytest.mark.asyncio
    async def test_send_without_at_user(self, client: DingTalkClient):
        """不 @ 用户时不应出现 atUserIds"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"processQueryKey": "mid"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch.object(client, "get_access_token", AsyncMock(return_value="tok")):
                await client.send_text(open_conversation_id="cid", content="回答")

            body = mock_cls.return_value.post.call_args.kwargs["json"]
            parsed = json.loads(body["msgParam"])
            assert "atUserIds" not in parsed
            assert "atUserIds" not in body


class TestWebhookReply:
    """session_webhook 回复通道"""

    @pytest.fixture
    def client(self) -> DingTalkClient:
        return DingTalkClient(app_key="k", app_secret="s", robot_code="r")

    @pytest.mark.asyncio
    async def test_reply_by_webhook_success(self, client: DingTalkClient):
        """webhook 回复应 POST 到 webhook 地址并返回 messageId"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response(
                    {"errcode": 0, "errmsg": "ok", "result": {"messageId": "wh_mid"}}
                )
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            mid = await client.reply_by_webhook(
                webhook_url="https://oapi.dingtalk.com/robot/sendBySession?session=abc",
                msg_type="markdown",
                msg_content={"title": "回答", "text": "@user_456 内容"},
            )

            assert mid == "wh_mid"
            call = mock_cls.return_value.post.call_args
            assert "sendBySession" in call.args[0]
            assert call.kwargs["json"]["msgtype"] == "markdown"

    @pytest.mark.asyncio
    async def test_reply_by_webhook_requires_url(self, client: DingTalkClient):
        """空 webhook 地址直接报错"""
        with pytest.raises(DingTalkAPIError, match="session_webhook 不能为空"):
            await client.reply_by_webhook(
                webhook_url="", msg_type="text", msg_content={"content": "x"}
            )

    @pytest.mark.asyncio
    async def test_reply_by_webhook_errcode_nonzero(self, client: DingTalkClient):
        """钉钉返回非 0 errcode 应抛出异常"""
        with patch("src.infrastructure.external.dingtalk_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.post = AsyncMock(
                return_value=make_response({"errcode": 400, "errmsg": "invalid session"})
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DingTalkAPIError, match="webhook 发送被拒绝"):
                await client.reply_by_webhook(
                    webhook_url="https://example.com/sendBySession",
                    msg_type="text",
                    msg_content={"content": "x"},
                )


class TestUpdateMessageUnsupported:
    """update_message 应显式失败，让上层回退到重发"""

    @pytest.mark.asyncio
    async def test_update_message_raises(self):
        """更新消息不可用时必须抛异常而非静默返回

        回归保护: 旧实现只打 warning 就返回 None，导致 handler 认为
        "思考中"消息已更新为答案，用户永远看不到回答。
        """
        client = DingTalkClient(app_key="k", app_secret="s", robot_code="r")
        with pytest.raises(DingTalkAPIError, match="不可用"):
            await client.update_message("mid", "新内容")


class TestRobotCode:
    """robotCode 配置优先级"""

    def test_robot_code_falls_back_to_app_key(self):
        """未配置 bot code 时回退为 app_key"""
        client = DingTalkClient(app_key="app_k", app_secret="s", robot_code=None)
        # 显式传 None 时，settings 中的 DINGTALK_BOT_CODE 会生效；这里验证非空
        assert client.robot_code

    def test_explicit_robot_code(self):
        """显式传入的 robot_code 优先"""
        client = DingTalkClient(app_key="app_k", app_secret="s", robot_code="robot_x")
        assert client.robot_code == "robot_x"
