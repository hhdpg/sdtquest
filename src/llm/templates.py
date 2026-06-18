"""Prompt 模板管理模块

提供 Prompt 模板的加载和变量替换功能。
"""

import re
from string import Template
from typing import Any


class PromptTemplate:
    """
    Prompt 模板类

    支持使用 ${variable} 格式的变量替换。

    Example:
        >>> template = PromptTemplate("你好，${name}！今天是${day}。")
        >>> result = template.render(name="张三", day="星期一")
        >>> print(result)
        '你好，张三！今天是星期一。'
    """

    def __init__(self, template: str, name: str = ""):
        """
        初始化模板

        Args:
            template: 模板字符串，使用 ${var} 表示变量
            name: 模板名称（可选，用于调试）
        """
        self.template = template
        self.name = name
        self._variables = self._extract_variables()

    def _extract_variables(self) -> list[str]:
        """提取模板中的所有变量名"""
        pattern = r"\$\{(\w+)\}"
        return re.findall(pattern, self.template)

    @property
    def variables(self) -> list[str]:
        """获取模板中的所有变量名"""
        return self._variables

    def render(self, **kwargs: Any) -> str:
        """
        渲染模板，替换变量

        Args:
            **kwargs: 变量名到值的映射

        Returns:
            渲染后的字符串

        Raises:
            KeyError: 缺少必要的变量
        """
        # 检查是否有缺失的变量
        missing = [v for v in self._variables if v not in kwargs]
        if missing:
            raise KeyError(
                f"模板 '{self.name}' 缺少变量: {', '.join(missing)}"
            )

        # 使用 string.Template 进行替换
        tmpl = Template(self.template)
        return tmpl.safe_substitute(**kwargs)

    def __str__(self) -> str:
        return f"PromptTemplate(name='{self.name}', vars={self._variables})"

    def __repr__(self) -> str:
        return self.__str__()


class PromptManager:
    """
    Prompt 管理器

    管理和注册多个 Prompt 模板。

    Example:
        >>> manager = PromptManager()
        >>> manager.register("greeting", "你好，${name}！")
        >>> result = manager.render("greeting", name="张三")
    """

    def __init__(self):
        """初始化 Prompt 管理器"""
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, name: str, template: str) -> None:
        """
        注册一个模板

        Args:
            name: 模板名称
            template: 模板字符串
        """
        self._templates[name] = PromptTemplate(template, name)

    def register_template(self, name: str, template: PromptTemplate) -> None:
        """
        注册一个 PromptTemplate 对象

        Args:
            name: 模板名称
            template: PromptTemplate 对象
        """
        self._templates[name] = template

    def get(self, name: str) -> PromptTemplate:
        """
        获取模板

        Args:
            name: 模板名称

        Returns:
            PromptTemplate 对象

        Raises:
            KeyError: 模板不存在
        """
        if name not in self._templates:
            raise KeyError(f"模板 '{name}' 不存在")
        return self._templates[name]

    def render(self, template_name: str, **kwargs: Any) -> str:
        """
        渲染指定模板

        Args:
            template_name: 模板名称
            **kwargs: 变量值

        Returns:
            渲染后的字符串
        """
        template = self.get(template_name)
        return template.render(**kwargs)

    def has(self, name: str) -> bool:
        """检查模板是否存在"""
        return name in self._templates

    def list_templates(self) -> list[str]:
        """列出所有已注册的模板名称"""
        return list(self._templates.keys())


# 全局 Prompt 管理器实例
prompt_manager = PromptManager()
