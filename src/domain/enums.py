"""领域枚举定义模块"""

from enum import Enum


class QuestionCategory(str, Enum):
    """
    问题分类枚举

    用于对用户问题进行分类，不同分类使用不同的处理策略：
    - 标准操作类：高阈值检索，低 temperature
    - 灵活推理类：中等阈值检索，高 temperature
    """
    OPERATION_GUIDE = "operation_guide"        # 操作指南 (~50%)
    PROCESS_INQUIRY = "process_inquiry"        # 流程咨询 (~25%)
    ANOMALY_TROUBLESHOOT = "anomaly_troubleshoot"  # 异常排查 (~15%)
    GENERAL = "general"                        # 其他/闲聊 (~10%)


class KnowledgeType(str, Enum):
    """
    知识类型枚举

    用于区分不同类型的知识条目，支持按类型过滤检索
    """
    PAGE = "page"                # 页面说明
    BUTTON = "button"            # 按钮操作
    FORM = "form"                # 表单说明
    WORKFLOW = "workflow"        # 流程说明
    API = "api"                  # API 接口
    MANUAL = "manual"            # 手动文档


class AnswerStatus(str, Enum):
    """
    回答状态枚举

    用于记录问答结果的状态
    """
    SUCCESS = "success"          # 成功回答
    NO_MATCH = "no_match"        # 未匹配到知识
    ERROR = "error"              # 生成出错
    TIMEOUT = "timeout"          # 超时
