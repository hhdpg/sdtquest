"""会话模型"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    消息模型

    表示会话中的一条消息（用户或机器人）

    Attributes:
        id: 消息唯一标识 (UUID)
        role: 消息角色 ("user" 或 "assistant")
        content: 消息内容
        timestamp: 消息时间戳
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)

    def is_user(self) -> bool:
        """判断是否为用户消息"""
        return self.role == "user"

    def is_assistant(self) -> bool:
        """判断是否为机器人消息"""
        return self.role == "assistant"

    def to_chat_format(self) -> dict:
        """转换为 LLM 聊天格式"""
        return {
            "role": self.role,
            "content": self.content,
        }


class Conversation(BaseModel):
    """
    会话模型

    维护一个完整的对话上下文

    Attributes:
        id: 会话唯一标识 (UUID)
        messages: 消息历史列表
        last_active: 最后活跃时间
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = Field(default_factory=list)
    last_active: datetime = Field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """添加消息到会话历史"""
        self.messages.append(message)
        self.last_active = datetime.now()

    def get_recent_messages(self, max_count: int = 5) -> list[Message]:
        """获取最近 N 条消息"""
        return self.messages[-max_count:]

    def get_chat_history(self, max_count: int = 5) -> list[dict]:
        """获取聊天历史，用于 LLM 上下文"""
        recent = self.get_recent_messages(max_count)
        return [msg.to_chat_format() for msg in recent]

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """判断会话是否过期"""
        now = datetime.now()
        diff = (now - self.last_active).total_seconds()
        return diff > ttl_seconds

    def clear(self) -> None:
        """清空会话历史"""
        self.messages = []
        self.last_active = datetime.now()

    def message_count(self) -> int:
        """获取消息总数"""
        return len(self.messages)
