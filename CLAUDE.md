# Claude Code 项目规范指南

> **项目**: 钉钉智能问答机器人 (dingtalk-qa-bot)  
> **版本**: v1.0  
> **更新日期**: 2026-06-15  
> **适用范围**: 本项目所有 Python 代码

---

## 目录

1. [项目概述](#项目概述)
2. [代码风格规范 (PEP 8)](#代码风格规范-pep-8)
3. [命名规范](#命名规范)
4. [类型提示规范](#类型提示规范)
5. [文档字符串规范](#文档字符串规范)
6. [异步编程规范](#异步编程规范)
7. [错误处理规范](#错误处理规范)
8. [日志规范](#日志规范)
9. [导入规范](#导入规范)
10. [测试规范](#测试规范)
11. [Git 提交规范](#git-提交规范)
12. [代码审查规范](#代码审查规范)
13. [性能优化规范](#性能优化规范)
14. [安全规范](#安全规范)
15. [项目特定规范](#项目特定规范)

---

## 项目概述

### 项目简介

本项目是一个基于本地大模型的 RAG (Retrieval-Augmented Generation) 智能问答机器人,用于钉钉群内自动回答用户问题。

**技术栈**:
- **后端框架**: FastAPI + Uvicorn
- **LLM 运行时**: Ollama (qwen3.5:35b-a3b-instruct-4bit)
- **Embedding 模型**: bge-m3
- **向量数据库**: ChromaDB
- **代码解析**: Tree-sitter + BeautifulSoup4
- **钉钉 SDK**: dingtalk-stream
- **Python 版本**: >= 3.11

**核心功能**:
- 智能问答: 基于 RAG 技术提供准确的操作指南和问题解答
- 知识库自动构建: 自动解析 Vue 2 前端代码,提取操作知识
- 混合检索: 结合 Dense + Sparse 向量检索,提高检索准确率
- 钉钉集成: 通过 Stream 模式实现实时消息收发
- 统计分析: 自动统计问题分类,生成日报

---

## 代码风格规范 (PEP 8)

> **参考**: [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)

### 缩进

```python
# ✅ 正确: 使用 4 个空格缩进
def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total

# ❌ 错误: 使用 Tab 或 2 个空格
def calculate_total(items):
  total = 0  # 只有 2 个空格
  for item in items:
    total += item.price
  return total
```

**说明**: 
- 统一使用 **4 个空格** 进行缩进,不使用 Tab
- 这样可以保证在不同编辑器中显示一致
- 避免 Tab 和空格混用导致的语法错误

### 行宽限制

```python
# ✅ 正确: 单行不超过 120 字符
def process_question(self, question: str, conversation_id: str, category: QuestionCategory, 
                     temperature: float = 0.3) -> Answer:
    pass

# 如果超过 120 字符,使用反斜杠或括号换行
def process_question(self, question: str, conversation_id: str, 
                     category: QuestionCategory, temperature: float = 0.3) -> Answer:
    pass

# ❌ 错误: 单行过长
def process_question(self, question: str, conversation_id: str, category: QuestionCategory, temperature: float = 0.3, max_tokens: int = 2048) -> Answer:
    pass
```

**说明**:
- 本项目行宽限制为 **120 字符** (PEP 8 默认 79,但现代屏幕更宽)
- 超过限制时,在运算符前换行或使用括号隐式换行
- 字符串过长时使用隐式字符串连接

### 空行使用

```python
# ✅ 正确: 类和函数之间使用 2 个空行
class QuestionService:
    """问答服务类"""
    
    def __init__(self):
        self.repo = QuestionRepository()
    
    
    def process(self, question: str) -> Answer:
        """处理问题"""
        pass


# 类内方法之间使用 1 个空行
class QuestionService:
    def __init__(self):
        self.repo = QuestionRepository()
    
    def process(self, question: str) -> Answer:
        pass
    
    def validate(self, question: str) -> bool:
        pass

# ❌ 错误: 没有空行或空行过多
class QuestionService:
    def __init__(self):
        self.repo = QuestionRepository()
    def process(self, question: str) -> Answer:  # 方法间没有空行
        pass
```

**说明**:
- 顶层函数和类定义之间使用 **2 个空行**
- 类内的方法定义之间使用 **1 个空行**
- 函数内的逻辑块可以用空行分隔(可选)
- 不要使用过多的空行(超过 2 个)

### 引号使用

```python
# ✅ 正确: 统一使用双引号
name = "dingtalk-qa-bot"
message = "Hello, World!"
path = "src/config.py"

# 字符串中包含双引号时使用单引号
quote = 'He said "Hello"'

# 多行字符串使用三引号
description = """
这是一个多行字符串
可以包含换行符
"""

# ❌ 错误: 混用引号
name = 'dingtalk-qa-bot'  # 应该用双引号
message = "Hello, World!"
```

**说明**:
- 字符串统一使用 **双引号** `"`
- 字符串内部包含双引号时使用单引号 `'`
- 多行字符串使用三引号 `"""`
- 字典键也使用双引号

### 空格使用

```python
# ✅ 正确: 适当使用空格
x = 1 + 2  # 运算符两侧有空格
my_list = [1, 2, 3]  # 逗号后有空格
def foo(x: int, y: str) -> bool:  # 参数类型注解前有空格
    pass

# ❌ 错误: 空格使用不当
x=1+2  # 运算符两侧没有空格
my_list = [1,2,3]  # 逗号后没有空格
def foo(x:int,y:str)->bool:  # 类型注解格式不对
    pass
```

**说明**:
- 二元运算符两侧各加一个空格: `=`, `+`, `-`, `==`, `!=` 等
- 逗号、冒号、分号后加空格
- 函数参数默认值不使用空格: `def foo(x=1)`
- 类型注解的冒号后加空格: `x: int`
- 避免行尾空格

### 括号使用

```python
# ✅ 正确: 合理使用括号
result = (a + b) * c  # 明确运算优先级
my_list = [
    "item1",
    "item2",
    "item3",
]  # 多行列表使用尾随逗号

# ❌ 错误: 不必要的括号
result = (a) + (b)  # 不必要的括号
```

**说明**:
- 只在需要明确运算优先级时使用括号
- 多行列表、字典、元组使用尾随逗号
- 避免在元组外层使用不必要的括号

---

## 命名规范

### 文件命名

```python
# ✅ 正确: 使用 snake_case
qa_service.py
knowledge_service.py
vector_store.py
router_parser.py

# ❌ 错误: 使用 camelCase 或其他格式
qaService.py
KnowledgeService.py
vectorStore.py
```

**说明**:
- 文件名使用 **snake_case** (小写字母 + 下划线)
- 文件名应该简短但具有描述性
- 测试文件以 `test_` 开头: `test_qa_service.py`

### 类命名

```python
# ✅ 正确: 使用 PascalCase
class QuestionService:
    pass

class RAGPipeline:
    pass

class ChromaVectorStore:
    pass

# ❌ 错误: 使用 snake_case 或其他格式
class question_service:
    pass

class rag_pipeline:
    pass
```

**说明**:
- 类名使用 **PascalCase** (每个单词首字母大写)
- 类名应该是名词,表示一个实体或概念
- 避免使用缩写,除非是广泛接受的缩写(如 API, URL)

### 函数和方法命名

```python
# ✅ 正确: 使用 snake_case,动词开头
def process_question(question: str) -> Answer:
    pass

def get_knowledge_item(item_id: str) -> KnowledgeItem:
    pass

def validate_answer(answer: Answer) -> bool:
    pass

# 私有方法使用下划线前缀
def _internal_method(self):
    pass

# ❌ 错误: 使用 camelCase 或名词
def processQuestion(question: str) -> Answer:
    pass

def question_processor(question: str) -> Answer:
    pass
```

**说明**:
- 函数名使用 **snake_case**
- 函数名应该是动词或动词短语,表示一个动作
- 获取数据用 `get_` 前缀
- 设置数据用 `set_` 前缀
- 验证数据用 `validate_` 前缀
- 私有方法使用 `_` 前缀

### 变量命名

```python
# ✅ 正确: 使用 snake_case,有意义的名称
question_text = "如何创建订单?"
max_retry_count = 3
is_valid = True
knowledge_items = []

# 循环变量可以使用简短名称
for item in items:
    process(item)

# ❌ 错误: 使用无意义的名称
q = "如何创建订单?"  # 不清晰
x = 3  # 不知道是什么
flag = True  # 什么标志?
data = []  # 什么数据?
```

**说明**:
- 变量名使用 **snake_case**
- 变量名应该有意义,能表达其用途
- 避免使用单字母变量(循环变量除外)
- 布尔变量使用 `is_`, `has_`, `can_` 等前缀
- 集合变量使用复数形式

### 常量命名

```python
# ✅ 正确: 使用 UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 120
API_BASE_URL = "https://api.example.com"
QUESTION_CATEGORIES = ["operation", "process", "anomaly"]

# ❌ 错误: 使用小写或其他格式
max_retry_count = 3
defaultTimeout = 120
apiBaseUrl = "https://api.example.com"
```

**说明**:
- 常量使用 **UPPER_SNAKE_CASE** (全大写 + 下划线)
- 常量应该在模块级别定义
- 常量名应该清晰表达其含义

### 枚举命名

```python
# ✅ 正确: 枚举类用 PascalCase,枚举值用 UPPER_SNAKE_CASE
from enum import Enum

class QuestionCategory(str, Enum):
    OPERATION_GUIDE = "operation_guide"
    PROCESS_INQUIRY = "process_inquiry"
    ANOMALY_TROUBLESHOOT = "anomaly_troubleshoot"
    GENERAL = "general"

class AnswerStatus(str, Enum):
    SUCCESS = "success"
    NO_MATCH = "no_match"
    ERROR = "error"
    TIMEOUT = "timeout"
```

**说明**:
- 枚举类名使用 **PascalCase**
- 枚举值使用 **UPPER_SNAKE_CASE**
- 枚举值应该是字符串或整数,便于序列化

---

## 类型提示规范

> **参考**: [mypy 官方文档](https://mypy.readthedocs.io/)、[PEP 484 - Type Hints](https://peps.python.org/pep-0484/)

### 函数签名

```python
# ✅ 正确: 所有公开函数都有类型注解
def process_question(
    question: str,
    conversation_id: str,
    category: QuestionCategory | None = None,
    temperature: float = 0.3
) -> Answer:
    """处理问题并返回答案"""
    pass

# 异步函数也要标注
async def generate_answer(prompt: str, options: GenerateOptions) -> str:
    """生成答案"""
    pass

# ❌ 错误: 缺少类型注解
def process_question(question, conversation_id, category=None):
    pass
```

**说明**:
- **所有公开函数** 必须有完整的类型注解
- 包括参数类型和返回类型
- 异步函数也要标注
- 默认值也要标注类型

### 变量类型注解

```python
# ✅ 正确: 复杂变量显式标注类型
question_list: list[Question] = []
answer_dict: dict[str, Answer] = {}
max_count: int = 10
is_valid: bool = True

# 可选类型使用 | None
category: QuestionCategory | None = None

# 联合类型
result: str | int | None = None

# ❌ 错误: 简单变量不需要标注
x: int = 1  # 太简单,可以推断
name: str = "test"  # 可以推断
```

**说明**:
- 复杂类型(列表、字典、联合类型)显式标注
- 简单类型可以省略,让类型推断器自动推断
- 可选类型使用 `Type | None` (Python 3.10+)
- 避免过度注解

### 类和实例属性

```python
# ✅ 正确: 类属性在 __init__ 中定义并标注
class QuestionService:
    """问答服务"""
    
    def __init__(self, repo: QuestionRepository, llm: LLMClient):
        self.repo: QuestionRepository = repo
        self.llm: LLMClient = llm
        self.cache: dict[str, Answer] = {}
        self._internal_state: str = "initialized"  # 私有属性

# 使用 Pydantic 模型时,字段自动有类型
from pydantic import BaseModel

class Question(BaseModel):
    id: str
    text: str
    category: QuestionCategory | None = None
```

**说明**:
- 实例属性在 `__init__` 中定义并标注类型
- 私有属性使用 `_` 前缀
- Pydantic 模型的字段自动有类型注解
- 类属性(所有实例共享)也要标注

### 类型别名

```python
# ✅ 正确: 复杂类型使用别名
from typing import TypeAlias

QuestionList: TypeAlias = list[Question]
AnswerDict: TypeAlias = dict[str, Answer]
CallbackFunc: TypeAlias = Callable[[str, str], Awaitable[None]]

def process_questions(questions: QuestionList) -> AnswerDict:
    pass

# ❌ 错误: 重复使用复杂类型
def process_questions(questions: list[Question]) -> dict[str, Answer]:
    pass

def process_more(questions: list[Question]) -> dict[str, Answer]:
    pass
```

**说明**:
- 复杂类型使用 `TypeAlias` 创建别名
- 别名使用 **PascalCase**
- 提高代码可读性和一致性
- 便于统一修改

### Protocol 接口

```python
# ✅ 正确: 使用 Protocol 定义接口
from typing import Protocol

class LLMClient(Protocol):
    """LLM 客户端接口"""
    
    async def generate(self, prompt: str, options: GenerateOptions) -> str:
        """生成文本"""
        ...
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """向量化文本"""
        ...

class VectorStore(Protocol):
    """向量存储接口"""
    
    async def add(self, items: list[KnowledgeItem]) -> None:
        """添加文档"""
        ...
    
    async def search(self, query: list[float], top_k: int) -> list[KnowledgeItem]:
        """搜索文档"""
        ...

# 实现类不需要显式继承
class OllamaClient:
    """Ollama 客户端实现"""
    
    async def generate(self, prompt: str, options: GenerateOptions) -> str:
        # 实现...
        pass
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 实现...
        pass
```

**说明**:
- 使用 `Protocol` 定义接口(结构化子类型)
- 实现类不需要显式继承
- 方法签名必须完全匹配
- 方法体使用 `...` 或 `pass`

### 泛型

```python
# ✅ 正确: 使用泛型提高复用性
from typing import TypeVar, Generic

T = TypeVar("T")

class Repository(Generic[T]):
    """通用仓储"""
    
    def save(self, item: T) -> None:
        pass
    
    def find_by_id(self, item_id: str) -> T | None:
        pass

class QuestionRepository(Repository[Question]):
    """问题仓储"""
    pass

class AnswerRepository(Repository[Answer]):
    """答案仓储"""
    pass
```

**说明**:
- 使用 `TypeVar` 和 `Generic` 创建泛型类
- 泛型参数使用单个大写字母或描述性名称
- 提高代码复用性

### 类型检查配置

```python
# pyproject.toml 中的 mypy 配置
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true  # 禁止未标注类型的函数
disallow_incomplete_defs = true  # 禁止部分标注
check_untyped_defs = true  # 检查未标注的函数
disallow_untyped_decorators = true  # 禁止未标注的装饰器
no_implicit_optional = true  # 禁止隐式可选
warn_redundant_casts = true  # 警告冗余类型转换
warn_unused_ignores = true  # 警告未使用的 ignore
warn_no_return = true  # 警告缺少返回
strict_equality = true  # 严格相等检查
```

**说明**:
- 使用严格模式检查类型
- 禁止未标注类型的函数
- 警告冗余的类型转换
- 严格检查相等性

---

## 文档字符串规范

> **参考**: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

### 模块文档字符串

```python
"""
问答服务模块。

本模块实现了问答服务的核心逻辑,包括问题处理、答案生成、日志记录等功能。

主要类:
- QAService: 问答服务主类,编排完整的问答流程
- AnswerGenerator: 答案生成器,调用 LLM 生成答案
- ContextAssembler: 上下文组装器,组装 RAG 检索结果

典型用法:
    >>> from src.services.qa_service import QAService
    >>> service = QAService(repo=repo, llm=llm_client)
    >>> answer = await service.ask("如何创建订单?", "conv_123")
    >>> print(answer.text)
"""

from typing import Protocol
# ... 其他导入
```

**说明**:
- 模块文档字符串放在文件开头
- 使用三引号 `"""`
- 包括模块功能说明、主要类、典型用法
- 第一行是摘要,后面是详细说明

### 类文档字符串

```python
class QAService:
    """
    问答服务类。
    
    负责编排完整的问答流程,包括:
    1. 获取会话上下文
    2. 问题分类
    3. RAG 检索
    4. Prompt 组装
    5. LLM 生成答案
    6. 回答后处理
    7. 记录问答日志
    
    Attributes:
        repo: 问题仓储,用于保存问答记录
        llm: LLM 客户端,用于生成答案
        rag_pipeline: RAG 管道,用于检索知识
        classifier: 问题分类器
        
    Example:
        >>> service = QAService(repo=repo, llm=llm_client)
        >>> answer = await service.ask("如何创建订单?", "conv_123")
        >>> print(answer.text)
        '创建订单的步骤如下...'
    """
    
    def __init__(self, repo: QuestionRepository, llm: LLMClient):
        """
        初始化问答服务。
        
        Args:
            repo: 问题仓储实例
            llm: LLM 客户端实例
        """
        self.repo = repo
        self.llm = llm
```

**说明**:
- 类文档字符串说明类的职责和功能
- 列出主要属性(Attributes)
- 提供使用示例(Example)
- `__init__` 方法也要有文档字符串

### 函数文档字符串

```python
def process_question(
    question: str,
    conversation_id: str,
    category: QuestionCategory | None = None,
    temperature: float = 0.3
) -> Answer:
    """
    处理用户问题并生成答案。
    
    完整的处理流程:
    1. 验证问题文本
    2. 获取会话上下文
    3. 问题分类(如果未提供)
    4. RAG 检索相关知识
    5. 组装 Prompt
    6. 调用 LLM 生成答案
    7. 后处理(格式化、引用标注)
    8. 记录问答日志
    
    Args:
        question: 用户问题文本,不能为空
        conversation_id: 会话 ID,用于维护上下文
        category: 问题分类,如果为 None 则自动分类
        temperature: LLM 生成温度,0.0-1.0,越高越随机
        
    Returns:
        Answer: 生成的答案对象,包含答案文本、引用来源、置信度等
        
    Raises:
        QuestionProcessingError: 问题处理失败(如 LLM 调用超时)
        KnowledgeNotFoundError: 知识库中未找到相关知识
        ValueError: 问题文本为空或格式不正确
        
    Example:
        >>> answer = process_question("如何创建订单?", "conv_123")
        >>> print(answer.text)
        '创建订单的步骤如下...'
        >>> print(answer.confidence)
        0.85
        
    Note:
        - 标准操作类问题使用 temperature=0.3
        - 灵活推理类问题使用 temperature=0.7
        - 处理时间通常 < 30 秒
        
    See Also:
        - RAGPipeline: RAG 检索管道
        - ContextAssembler: 上下文组装器
    """
    pass
```

**说明**:
- 第一行是摘要,简洁说明函数功能
- 详细说明函数的处理流程
- Args: 列出所有参数,包括类型和说明
- Returns: 说明返回值类型和含义
- Raises: 列出可能抛出的异常
- Example: 提供使用示例
- Note: 补充说明
- See Also: 相关函数或类

### 异步函数文档字符串

```python
async def generate_answer(prompt: str, options: GenerateOptions) -> str:
    """
    异步生成答案。
    
    调用 LLM 客户端生成答案,支持超时控制和并发限制。
    
    Args:
        prompt: LLM 提示词,包含问题和上下文
        options: 生成选项,包括 temperature、max_tokens 等
        
    Returns:
        str: 生成的答案文本
        
    Raises:
        LLMServiceError: LLM 服务调用失败
        asyncio.TimeoutError: 生成超时
        
    Example:
        >>> answer = await generate_answer(prompt, options)
        >>> print(answer)
        '这是生成的答案...'
        
    Note:
        - 默认超时时间为 120 秒
        - 最大并发数为 2
        - 使用 asyncio.Semaphore 控制并发
    """
    pass
```

**说明**:
- 异步函数也要有完整的文档字符串
- 说明异步特性和并发控制
- 如果有超时,要在 Note 中说明

### 属性文档字符串

```python
class QuestionService:
    """问答服务"""
    
    @property
    def question_count(self) -> int:
        """
        已处理的问题数量。
        
        Returns:
            int: 问题总数
        """
        return len(self.processed_questions)
```

**说明**:
- 属性也要有文档字符串
- 说明属性的含义和返回值

---

## 异步编程规范

> **参考**: [Python asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)

### 异步函数定义

```python
# ✅ 正确: 使用 async def 定义异步函数
async def process_question(question: str) -> Answer:
    """异步处理问题"""
    answer = await generate_answer(question)
    return answer

# 异步方法
class QAService:
    async def ask(self, question: str, conversation_id: str) -> Answer:
        """异步问答"""
        context = await self.get_context(conversation_id)
        answer = await self.generate(question, context)
        return answer

# ❌ 错误: 在异步函数中使用阻塞调用
async def process_question(question: str) -> Answer:
    time.sleep(1)  # 阻塞调用,会阻塞整个事件循环
    return answer
```

**说明**:
- 使用 `async def` 定义异步函数
- 使用 `await` 调用异步函数
- **禁止在异步函数中使用阻塞调用**(如 `time.sleep()`, `requests.get()`)
- 必须使用异步版本(如 `asyncio.sleep()`, `httpx.AsyncClient`)

### 并发执行

```python
# ✅ 正确: 使用 asyncio.gather 并发执行多个任务
async def process_multiple_questions(questions: list[str]) -> list[Answer]:
    """并发处理多个问题"""
    tasks = [process_question(q) for q in questions]
    answers = await asyncio.gather(*tasks)
    return list(answers)

# 使用 asyncio.TaskGroup (Python 3.11+)
async def process_with_task_group(questions: list[str]) -> list[Answer]:
    """使用 TaskGroup 并发处理"""
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(process_question(q)) for q in questions]
    return [task.result() for task in tasks]

# ❌ 错误: 顺序执行
async def process_sequential(questions: list[str]) -> list[Answer]:
    """顺序处理(慢)"""
    answers = []
    for q in questions:
        answer = await process_question(q)  # 顺序等待
        answers.append(answer)
    return answers
```

**说明**:
- 使用 `asyncio.gather()` 并发执行多个任务
- Python 3.11+ 推荐使用 `asyncio.TaskGroup`
- 避免顺序执行可以并发的任务
- 注意并发数量限制

### 并发限制

```python
# ✅ 正确: 使用 Semaphore 限制并发数
class OllamaClient:
    def __init__(self, max_concurrent: int = 2):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def generate(self, prompt: str) -> str:
        """生成文本,限制并发数"""
        async with self.semaphore:  # 限制并发
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"prompt": prompt}
                )
                return response.json()["response"]

# ❌ 错误: 没有并发限制
async def generate(prompt: str) -> str:
    """无限制并发,可能导致资源耗尽"""
    async with httpx.AsyncClient() as client:
        response = await client.post(...)
        return response.json()["response"]
```

**说明**:
- 使用 `asyncio.Semaphore` 限制并发数
- 避免同时发起过多请求导致资源耗尽
- 特别是调用 LLM 等耗时服务时

### 超时控制

```python
# ✅ 正确: 使用 asyncio.timeout 控制超时
async def generate_with_timeout(prompt: str, timeout: int = 120) -> str:
    """带超时的生成"""
    try:
        async with asyncio.timeout(timeout):
            answer = await generate_answer(prompt)
            return answer
    except asyncio.TimeoutError:
        logger.error(f"生成超时: {timeout}s")
        raise LLMServiceError("生成超时")

# 在 httpx 中设置超时
async def call_api(url: str) -> dict:
    """调用 API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()
```

**说明**:
- 所有异步操作都应该有超时控制
- 使用 `asyncio.timeout()` (Python 3.11+)
- httpx 客户端也要设置超时
- 超时后要有明确的错误处理

### 异步上下文管理器

```python
# ✅ 正确: 使用异步上下文管理器
class DatabaseConnection:
    """数据库连接"""
    
    async def __aenter__(self):
        """进入上下文"""
        self.conn = await create_connection()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        await self.conn.close()

# 使用
async def query_database():
    async with DatabaseConnection() as db:
        result = await db.query("SELECT * FROM questions")
        return result

# ❌ 错误: 手动管理资源
async def query_database():
    conn = await create_connection()
    try:
        result = await conn.query("SELECT * FROM questions")
        return result
    finally:
        await conn.close()  # 容易忘记
```

**说明**:
- 使用 `async with` 管理异步资源
- 实现 `__aenter__` 和 `__aexit__` 方法
- 自动处理资源清理,避免内存泄漏

### 异步迭代器

```python
# ✅ 正确: 使用异步迭代器
class StreamGenerator:
    """流式生成器"""
    
    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """异步流式生成"""
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json={"prompt": prompt}) as response:
                async for chunk in response.aiter_text():
                    yield chunk

# 使用
async def process_stream():
    generator = StreamGenerator()
    async for chunk in generator.generate_stream("Hello"):
        print(chunk, end="", flush=True)
```

**说明**:
- 使用 `AsyncIterator` 实现异步迭代
- 使用 `yield` 产生值
- 使用 `async for` 消费迭代器

---

## 错误处理规范

> **参考**: [Python 异常处理最佳实践](https://realpython.com/python-exceptions/)

### 自定义异常

```python
# ✅ 正确: 定义清晰的异常层级
class AppException(Exception):
    """应用基础异常"""
    
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class QuestionProcessingError(AppException):
    """问题处理失败"""
    code = "QA_PROCESSING_ERROR"

class KnowledgeNotFoundError(AppException):
    """知识未找到"""
    code = "KNOWLEDGE_NOT_FOUND"

class LLMServiceError(AppException):
    """LLM 服务错误"""
    code = "LLM_SERVICE_ERROR"

class VectorStoreError(AppException):
    """向量库错误"""
    code = "VECTOR_STORE_ERROR"

# 使用
def process_question(question: str) -> Answer:
    if not question:
        raise QuestionProcessingError("问题不能为空")
    
    try:
        answer = llm.generate(question)
    except Exception as e:
        raise LLMServiceError(f"LLM 调用失败: {e}") from e
```

**说明**:
- 定义清晰的异常层级
- 每个异常都有明确的 code 和 message
- 使用 `from e` 保留原始异常链
- 异常类名以 `Error` 结尾

### 捕获特定异常

```python
# ✅ 正确: 捕获特定异常
async def process_question(question: str) -> Answer:
    try:
        answer = await generate_answer(question)
        return answer
    except LLMServiceError as e:
        logger.error(f"LLM 服务错误: {e.message}")
        raise
    except VectorStoreError as e:
        logger.error(f"向量库错误: {e.message}")
        raise
    except asyncio.TimeoutError:
        logger.error("生成超时")
        raise LLMServiceError("生成超时")

# ❌ 错误: 捕获过于宽泛的异常
async def process_question(question: str) -> Answer:
    try:
        answer = await generate_answer(question)
        return answer
    except Exception as e:  # 太宽泛
        logger.error(f"错误: {e}")
        return None  # 不应该返回 None
```

**说明**:
- 捕获**特定的异常**,不要捕获 `Exception`
- 除非在最外层,用于兜底
- 不要捕获 `BaseException`
- 不要使用空的 `except:`

### 异常传播

```python
# ✅ 正确: 在合适的层级处理异常
# 底层: 抛出异常
async def call_llm(prompt: str) -> str:
    """调用 LLM"""
    try:
        response = await httpx.post(url, json={"prompt": prompt})
        return response.json()["response"]
    except httpx.HTTPError as e:
        raise LLMServiceError(f"HTTP 错误: {e}") from e

# 中层: 传播异常
async def generate_answer(question: str) -> Answer:
    """生成答案"""
    prompt = build_prompt(question)
    text = await call_llm(prompt)  # 不捕获,向上传播
    return Answer(text=text)

# 顶层: 处理异常
async def handle_message(message: str):
    """处理消息"""
    try:
        answer = await generate_answer(message)
        await send_answer(answer)
    except LLMServiceError as e:
        await send_error("服务繁忙,请稍后再试")
        logger.error(f"LLM 错误: {e}")
    except Exception as e:
        await send_error("处理失败,请联系管理员")
        logger.exception(f"未知错误: {e}")
```

**说明**:
- **底层抛出异常**,不要隐藏错误
- **中层传播异常**,让调用者处理
- **顶层处理异常**,给用户友好的提示
- 不要在中间层吞掉异常

### 不要吞掉异常

```python
# ✅ 正确: 记录异常并重新抛出
def process_data(data: dict) -> Result:
    try:
        result = validate_and_process(data)
        return result
    except ValidationError as e:
        logger.error(f"数据验证失败: {e}")
        raise  # 重新抛出

# ❌ 错误: 吞掉异常
def process_data(data: dict) -> Result | None:
    try:
        result = validate_and_process(data)
        return result
    except ValidationError:
        pass  # 吞掉异常,返回 None
    except Exception:
        pass  # 吞掉所有异常
    return None
```

**说明**:
- **不要吞掉异常**(空的 except 或 pass)
- 如果要忽略异常,必须有明确的注释说明原因
- 记录异常日志后再抛出

### 使用 contextlib.suppress

```python
# ✅ 正确: 使用 contextlib.suppress 忽略特定异常
from contextlib import suppress

def cleanup():
    """清理资源"""
    with suppress(FileNotFoundError):
        os.remove("temp.txt")  # 文件不存在也不报错

# 等同于
def cleanup():
    try:
        os.remove("temp.txt")
    except FileNotFoundError:
        pass  # 但 suppress 更清晰
```

**说明**:
- 使用 `contextlib.suppress` 明确忽略特定异常
- 比空的 except 更清晰
- 只用于确实可以忽略的异常

### 异常信息

```python
# ✅ 正确: 提供有用的异常信息
class QuestionProcessingError(AppException):
    """问题处理失败"""
    
    def __init__(self, message: str, question_id: str | None = None):
        self.question_id = question_id
        super().__init__(message, code="QA_PROCESSING_ERROR")

# 使用
raise QuestionProcessingError("问题文本过长", question_id="q_123")

# ❌ 错误: 异常信息不明确
raise Exception("错误")  # 什么错误?
raise ValueError("失败")  # 为什么失败?
```

**说明**:
- 异常信息要**清晰明确**
- 包含上下文信息(如 ID、参数等)
- 便于调试和定位问题

---

## 日志规范

> **参考**: [loguru 官方文档](https://loguru.readthedocs.io/)

### 日志初始化

```python
# src/main.py
from loguru import logger
import sys

def setup_logging():
    """配置日志"""
    logger.remove()  # 移除默认 handler
    
    # 控制台输出
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    )
    
    # 文件输出
    logger.add(
        "data/logs/bot_{time:YYYY-MM-DD}.log",
        rotation="1 day",  # 每天轮转
        retention="30 days",  # 保留 30 天
        compression="gz",  # 压缩
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{function}:{line} | {message}",
        encoding="utf-8"
    )

# 启动时调用
setup_logging()
```

**说明**:
- 使用 `loguru` 替代标准库 `logging`
- 配置控制台和文件输出
- 设置日志轮转和保留策略
- 使用彩色格式提高可读性

### 日志级别

```python
from loguru import logger

# DEBUG: 开发调试信息
logger.debug(f"检索到的文档: {docs}")
logger.debug(f"Prompt 内容: {prompt[:200]}")

# INFO: 关键业务流程
logger.info("收到问题 | sender={} | text={}", sender_id, question_text[:50])
logger.info("问题分类 | category={} | confidence={:.2f}", category, confidence)
logger.info("检索结果 | top_k={} | max_score={:.3f}", len(docs), max_score)
logger.info("LLM 生成 | tokens={} | latency={:.1f}s", tokens, latency)
logger.info("知识库构建完成 | total={}", total_items)

# WARNING: 非致命异常
logger.warning("检索未命中 | query={}", query)
logger.warning("模型响应慢 | latency={:.1f}s", latency)
logger.warning("缓存未命中 | key={}", cache_key)

# ERROR: 业务异常
logger.error("LLM 调用失败 | error={}", str(e))
logger.error("钉钉 API 超时 | conversation_id={}", conversation_id)
logger.error("知识库构建失败 | file={}", file_path)

# CRITICAL: 系统级故障
logger.critical("Ollama 服务不可用 | url={}", settings.OLLAMA_BASE_URL)
logger.critical("数据库损坏 | path={}", db_path)
logger.critical("内存不足 | usage={:.1f}%", memory_usage)
```

**说明**:
- **DEBUG**: 开发调试,生产环境关闭
- **INFO**: 关键业务流程,生产环境开启
- **WARNING**: 非致命异常,需要关注
- **ERROR**: 业务异常,需要处理
- **CRITICAL**: 系统级故障,需要立即处理

### 日志格式

```python
# ✅ 正确: 使用结构化日志
logger.info("收到问题 | sender={} | text={} | conversation={}", 
            sender_id, question_text[:50], conversation_id)

logger.info("检索结果 | top_k={} | max_score={:.3f} | docs={}", 
            len(docs), max_score, [d.title for d in docs])

# ❌ 错误: 使用字符串拼接
logger.info("收到问题: " + question_text)  # 性能差
logger.info(f"检索结果: {docs}")  # 不安全
```

**说明**:
- 使用 `{}` 占位符,不要使用字符串拼接或 f-string
- 使用 `|` 分隔不同的字段
- 字段名使用 snake_case
- 敏感信息要脱敏(如只记录前 50 字符)

### 异常日志

```python
# ✅ 正确: 记录完整异常信息
try:
    answer = await generate_answer(question)
except LLMServiceError as e:
    logger.error("LLM 服务错误 | error={} | question_id={}", 
                 e.message, question_id)
    logger.opt(exception=True).error("完整堆栈:")  # 记录堆栈
except Exception as e:
    logger.exception("未知错误")  # 自动记录堆栈

# ❌ 错误: 只记录异常消息
try:
    answer = await generate_answer(question)
except Exception as e:
    logger.error(str(e))  # 丢失堆栈信息
```

**说明**:
- 使用 `logger.exception()` 自动记录堆栈
- 或使用 `logger.opt(exception=True).error()`
- 保留完整的异常信息便于调试

### 性能日志

```python
import time
from loguru import logger

# ✅ 正确: 记录性能指标
start_time = time.time()
answer = await generate_answer(question)
latency = time.time() - start_time

if latency > 30:
    logger.warning("LLM 响应慢 | latency={:.1f}s | question={}", 
                   latency, question[:50])
else:
    logger.info("LLM 生成完成 | latency={:.1f}s | tokens={}", 
                latency, token_count)

# 使用 contextmanager 简化
from contextlib import contextmanager

@contextmanager
def log_performance(operation: str, threshold: float = 1.0):
    """性能日志上下文管理器"""
    start = time.time()
    try:
        yield
    finally:
        latency = time.time() - start
        if latency > threshold:
            logger.warning("{} 慢 | latency={:.1f}s", operation, latency)
        else:
            logger.info("{} 完成 | latency={:.1f}s", operation, latency)

# 使用
with log_performance("RAG 检索", threshold=2.0):
    docs = await retriever.retrieve(query)
```

**说明**:
- 记录关键操作的性能指标
- 设置阈值,超过阈值记录 WARNING
- 使用上下文管理器简化代码

---

## 导入规范

### 导入顺序

```python
# ✅ 正确: 按顺序导入

# 1. 标准库
import asyncio
import os
import sys
from pathlib import Path
from typing import Protocol
from datetime import datetime
from contextlib import asynccontextmanager

# 2. 第三方库
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
import httpx
import chromadb

# 3. 项目内模块
from src.config import settings
from src.domain.models import Question, Answer
from src.domain.ports import LLMClient, VectorStore
from src.domain.exceptions import LLMServiceError

# ❌ 错误: 顺序混乱
from src.config import settings
import os
from fastapi import FastAPI
from src.domain.models import Question
import asyncio
```

**说明**:
- 按顺序导入:**标准库** → **第三方库** → **项目内模块**
- 每组之间空一行
- 每组内按字母顺序排序

### 导入方式

```python
# ✅ 正确: 使用 from ... import ...
from src.domain.models import Question, Answer
from src.config import settings

# 导入整个模块(仅在需要时使用)
import json
import os

# ❌ 错误: 使用 *
from src.domain.models import *  # 不清楚导入了什么

# ❌ 错误: 导入过多
from src.domain.models.question import Question
from src.domain.models.answer import Answer
from src.domain.models.knowledge import KnowledgeItem
# 应该合并
from src.domain.models import Question, Answer, KnowledgeItem
```

**说明**:
- 优先使用 `from ... import ...`
- 不要使用 `import *`
- 同一模块的导入要合并
- 只在必要时导入整个模块

### 循环导入处理

```python
# ✅ 正确: 使用类型注解避免循环导入
# file1.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from file2 import ClassB

class ClassA:
    def method(self, b: "ClassB") -> None:
        pass

# file2.py
from file1 import ClassA

class ClassB:
    pass

# ✅ 或者: 延迟导入
class ClassA:
    def method(self) -> None:
        from file2 import ClassB  # 在函数内导入
        b = ClassB()
```

**说明**:
- 使用 `TYPE_CHECKING` 避免运行时循环导入
- 或使用延迟导入(在函数内导入)
- 类型注解使用字符串形式

### __all__ 定义

```python
# src/domain/models/__init__.py
"""领域模型模块"""

from .question import Question
from .answer import Answer
from .knowledge import KnowledgeItem
from .conversation import Conversation, Message

__all__ = [
    "Question",
    "Answer",
    "KnowledgeItem",
    "Conversation",
    "Message",
]

# 使用
from src.domain.models import Question, Answer  # 只能导入 __all__ 中定义的
```

**说明**:
- 使用 `__all__` 明确导出哪些名称
- 便于 IDE 自动补全
- 避免导出内部实现

---

## 测试规范

> **参考**: [pytest 官方文档](https://docs.pytest.org/)

### 测试文件组织

```
tests/
├── conftest.py              # 全局 fixture
├── unit/                    # 单元测试
│   ├── test_parser/
│   │   ├── test_vue_parser.py
│   │   ├── test_router_parser.py
│   │   └── test_component_parser.py
│   ├── test_rag/
│   │   ├── test_retriever.py
│   │   └── test_context.py
│   ├── test_llm/
│   │   └── test_client.py
│   └── test_services/
│       └── test_qa_service.py
├── integration/             # 集成测试
│   ├── test_qa_pipeline.py
│   └── test_knowledge_build.py
└── fixtures/                # 测试数据
    ├── sample_vue_project/
    └── sample_knowledge/
```

**说明**:
- 单元测试和集成测试分开
- 测试文件以 `test_` 开头
- 测试类以 `Test` 开头
- 测试函数以 `test_` 开头

### 单元测试

```python
# tests/unit/test_services/test_qa_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.services.qa_service import QAService
from src.domain.models import Question, Answer
from src.domain.enums import QuestionCategory

class TestQAService:
    """问答服务单元测试"""
    
    @pytest.fixture
    def mock_repo(self):
        """Mock 仓储"""
        repo = Mock()
        repo.save = Mock()
        return repo
    
    @pytest.fixture
    def mock_llm(self):
        """Mock LLM 客户端"""
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value="这是答案")
        return llm
    
    @pytest.fixture
    def qa_service(self, mock_repo, mock_llm):
        """问答服务实例"""
        return QAService(repo=mock_repo, llm=mock_llm)
    
    @pytest.mark.asyncio
    async def test_ask_success(self, qa_service, mock_repo):
        """测试成功问答"""
        # 准备
        question = "如何创建订单?"
        conversation_id = "conv_123"
        
        # 执行
        answer = await qa_service.ask(question, conversation_id)
        
        # 验证
        assert isinstance(answer, Answer)
        assert answer.text == "这是答案"
        assert answer.question_id is not None
        mock_repo.save.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ask_empty_question(self, qa_service):
        """测试空问题"""
        # 执行和验证
        with pytest.raises(ValueError, match="问题不能为空"):
            await qa_service.ask("", "conv_123")
    
    @pytest.mark.asyncio
    async def test_ask_with_category(self, qa_service):
        """测试带分类的问题"""
        # 准备
        question = "订单创建失败怎么办?"
        category = QuestionCategory.ANOMALY_TROUBLESHOOT
        
        # 执行
        answer = await qa_service.ask(question, "conv_123", category=category)
        
        # 验证
        assert answer.category == category
```

**说明**:
- 使用 `pytest` 框架
- 使用 `fixture` 管理测试依赖
- 使用 `Mock` 和 `AsyncMock` 模拟依赖
- 测试函数要有清晰的名称
- 使用 AAA 模式: Arrange(准备) → Act(执行) → Assert(验证)

### 集成测试

```python
# tests/integration/test_qa_pipeline.py
import pytest
from pathlib import Path
from src.rag.pipeline import RAGPipeline
from src.rag.vectorstore import ChromaVectorStore
from src.llm.client import OllamaClient
from src.config import settings

@pytest.fixture
def vectorstore(tmp_path):
    """临时向量库"""
    return ChromaVectorStore(persist_dir=str(tmp_path / "chroma"))

@pytest.fixture
def llm_client():
    """LLM 客户端(需要 Ollama 服务)"""
    return OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL
    )

@pytest.mark.integration
@pytest.mark.asyncio
async def test_rag_pipeline(vectorstore, llm_client):
    """测试 RAG 管道(需要真实 Ollama)"""
    # 准备: 添加测试数据
    test_docs = [
        {"title": "创建订单", "content": "点击新建按钮..."},
        {"title": "删除订单", "content": "选择订单后点击删除..."},
    ]
    await vectorstore.add(test_docs)
    
    # 执行
    pipeline = RAGPipeline(vectorstore=vectorstore, llm=llm_client)
    result = await pipeline.query("如何创建订单?")
    
    # 验证
    assert result.answer is not None
    assert len(result.sources) > 0
    assert "创建" in result.answer
```

**说明**:
- 集成测试使用真实的组件(如 ChromaDB)
- 使用 `tmp_path` 创建临时目录
- 标记为 `@pytest.mark.integration`
- 需要外部服务(如 Ollama)的测试要单独标记

### Mock 策略

```python
# ✅ 正确: Mock 外部依赖
from unittest.mock import Mock, AsyncMock, patch

# Mock LLM 客户端
@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="模拟答案")
    llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return llm

# Mock 钉钉 API
@pytest.fixture
def mock_dingtalk():
    with patch("src.infrastructure.external.dingtalk_client.DingTalkClient") as mock:
        client = AsyncMock()
        client.send_message = AsyncMock(return_value=True)
        mock.return_value = client
        yield mock

# ❌ 错误: Mock 内部逻辑
def test_process():
    service = QAService(...)
    service.validate_question = Mock(return_value=True)  # 不应该 Mock 内部方法
    # 应该测试真实逻辑
```

**说明**:
- Mock **外部依赖**(API、数据库、网络)
- 不要 Mock **内部逻辑**
- 使用 `pytest.fixture` 管理 Mock
- 使用 `patch` 临时替换

### 覆盖率目标

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: 集成测试",
    "slow: 慢速测试",
]

[tool.coverage.run]
source = ["src"]
omit = [
    "src/main.py",  # 启动入口
    "src/config.py",  # 配置
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.",
]

# 覆盖率目标
# domain/ > 90%
# services/ > 80%
# rag/、parser/ > 70%
# infrastructure/ > 50%
```

**说明**:
- 设置覆盖率目标
- 排除启动入口和配置文件
- 排除不可达代码

---

## Git 提交规范

### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**说明**:
- **type**: 提交类型(必填)
- **scope**: 影响范围(可选)
- **subject**: 简短描述(必填)
- **body**: 详细说明(可选)
- **footer**: 关联信息(可选)

### 提交类型

```bash
# feat: 新功能
feat(bot): 添加钉钉消息自动回复功能

# fix: 修复 bug
fix(rag): 修复检索结果为空时的异常处理

# docs: 文档更新
docs(readme): 更新快速启动指南

# style: 代码格式(不影响逻辑)
style(services): 格式化 qa_service.py

# refactor: 重构(既不是新功能也不是 bug 修复)
refactor(parser): 重构 Vue 解析器结构

# perf: 性能优化
perf(llm): 优化 LLM 并发控制

# test: 测试相关
test(services): 添加问答服务单元测试

# chore: 构建或辅助工具变动
chore(deps): 升级 fastapi 到 0.110.0
```

### 提交示例

```bash
# 好的提交消息
feat(rag): 实现混合检索策略

- 结合 Dense + Sparse 检索
- 使用 RRF 融合排序
- 支持根据问题类型切换阈值

Closes #12

# 坏的提交消息
update code  # 太模糊
fix bug  # 什么 bug?
wip  # 不应该提交
```

**说明**:
- 提交消息要**清晰明确**
- 使用祈使句(如 "添加功能" 而不是 "添加了功能")
- 第一行不超过 50 字符
- body 每行不超过 72 字符
- 说明**做了什么**和**为什么**

---

## 代码审查规范

### 审查清单

```markdown
## 代码审查清单

### 1. 功能正确性
- [ ] 代码是否实现了预期的功能?
- [ ] 边界条件是否处理正确?
- [ ] 异常处理是否完善?

### 2. 代码质量
- [ ] 是否遵循 PEP 8 规范?
- [ ] 命名是否清晰有意义?
- [ ] 是否有重复代码可以提取?
- [ ] 是否有魔法数字或硬编码?

### 3. 类型安全
- [ ] 所有公开函数是否有类型注解?
- [ ] 类型注解是否正确?
- [ ] 是否通过了 mypy 检查?

### 4. 文档
- [ ] 是否有完整的文档字符串?
- [ ] 文档字符串是否准确清晰?
- [ ] 复杂逻辑是否有注释?

### 5. 测试
- [ ] 是否有充分的单元测试?
- [ ] 测试覆盖率是否达标?
- [ ] 测试是否易于理解和维护?

### 6. 性能
- [ ] 是否有明显的性能问题?
- [ ] 是否有不必要的循环或重复计算?
- [ ] 异步代码是否正确使用?

### 7. 安全
- [ ] 是否有敏感信息泄露?
- [ ] 输入是否经过验证?
- [ ] 是否有 SQL 注入等安全风险?

### 8. 可维护性
- [ ] 代码是否易于理解?
- [ ] 是否遵循项目架构?
- [ ] 是否引入了不必要的复杂性?
```

### 审查原则

```markdown
## 审查原则

1. **尊重他人**: 评论代码,不评论人
   - ✅ "这里可以优化" 
   - ❌ "你怎么写成这样"

2. **提供建议**: 不只是指出问题,还要给出解决方案
   - ✅ "建议使用 dict.get() 避免 KeyError"
   - ❌ "这里有 bug"

3. **说明原因**: 解释为什么这样不好
   - ✅ "这里会阻塞事件循环,建议使用异步版本"
   - ❌ "不要这样写"

4. **区分严重程度**:
   - 🔴 **必须修改**: bug、安全漏洞、严重问题
   - 🟡 **建议修改**: 性能优化、代码改进
   - 🟢 **可选修改**: 风格、小优化

5. **表扬好的代码**: 看到好的实现也要表扬
   - ✅ "这个实现很优雅 👍"
```

---

## 性能优化规范

### 避免常见性能问题

```python
# ✅ 正确: 使用生成器处理大数据
def process_large_file(file_path: str) -> Iterator[Line]:
    """逐行处理大文件"""
    with open(file_path) as f:
        for line in f:
            yield parse_line(line)

# ❌ 错误: 一次性加载到内存
def process_large_file(file_path: str) -> list[Line]:
    """内存可能溢出"""
    with open(file_path) as f:
        lines = f.readlines()  # 全部加载
    return [parse_line(line) for line in lines]

# ✅ 正确: 使用缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_computation(x: int) -> int:
    """耗时计算"""
    # ...
    return result

# ❌ 错误: 重复计算
def process(items: list[int]) -> list[int]:
    return [expensive_computation(x) for x in items]  # 可能重复计算
```

**说明**:
- 使用生成器处理大数据
- 使用缓存避免重复计算
- 避免一次性加载大文件到内存

### 异步性能

```python
# ✅ 正确: 并发执行
async def process_multiple(items: list[str]) -> list[Result]:
    """并发处理"""
    tasks = [process_item(item) for item in items]
    return await asyncio.gather(*tasks)

# ✅ 正确: 限制并发
async def process_with_limit(items: list[str], max_concurrent: int = 5) -> list[Result]:
    """限制并发数"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_process(item: str) -> Result:
        async with semaphore:
            return await process_item(item)
    
    tasks = [limited_process(item) for item in items]
    return await asyncio.gather(*tasks)

# ❌ 错误: 顺序执行
async def process_sequential(items: list[str]) -> list[Result]:
    """慢"""
    results = []
    for item in items:
        result = await process_item(item)
        results.append(result)
    return results
```

**说明**:
- 使用 `asyncio.gather()` 并发执行
- 使用 `Semaphore` 限制并发数
- 避免顺序执行可以并发的任务

### 数据库性能

```python
# ✅ 正确: 批量操作
async def add_items(items: list[KnowledgeItem]) -> None:
    """批量添加"""
    await vectorstore.add_batch(items)

# ❌ 错误: 逐个操作
async def add_items(items: list[KnowledgeItem]) -> None:
    """慢"""
    for item in items:
        await vectorstore.add(item)

# ✅ 正确: 使用索引
# 在数据库查询中使用索引
async def find_by_category(category: str) -> list[Question]:
    """使用索引查询"""
    return await db.execute(
        "SELECT * FROM questions WHERE category = ?", 
        (category,)
    )
```

**说明**:
- 使用批量操作代替逐个操作
- 为常用查询字段创建索引
- 避免 N+1 查询问题

---

## 安全规范

### 敏感信息保护

```python
# ✅ 正确: 使用环境变量
class Settings(BaseSettings):
    DINGTALK_APP_KEY: str
    DINGTALK_APP_SECRET: str
    
    model_config = {"env_file": ".env"}

# ❌ 错误: 硬编码密钥
APP_KEY = "sk-1234567890abcdef"  # 不应该提交到 Git
SECRET = "my-secret-key"

# ✅ 正确: 日志脱敏
logger.info("用户登录 | user_id={} | token={}", 
            user_id, token[:10] + "***")  # 只显示前 10 位

# ❌ 错误: 记录完整密钥
logger.info("API 调用 | key={}", api_key)  # 泄露密钥
```

**说明**:
- 敏感信息使用环境变量
- 不要硬编码密钥、密码
- 日志中脱敏敏感信息
- `.env` 文件不要提交到 Git

### 输入验证

```python
# ✅ 正确: 验证输入
from pydantic import BaseModel, validator

class QuestionRequest(BaseModel):
    question: str
    conversation_id: str
    
    @validator("question")
    def validate_question(cls, v):
        if not v or len(v) > 1000:
            raise ValueError("问题长度必须在 1-1000 字符")
        return v.strip()

# ❌ 错误: 不验证输入
@app.post("/api/chat")
async def chat(request: dict):
    question = request.get("question")  # 可能为空或过长
    # 直接使用,不安全
```

**说明**:
- 使用 Pydantic 验证输入
- 检查输入长度、格式
- 去除空白字符
- 不要信任用户输入

### SQL 注入防护

```python
# ✅ 正确: 使用参数化查询
async def find_question(question_id: str) -> Question | None:
    """参数化查询"""
    query = "SELECT * FROM questions WHERE id = ?"
    result = await db.execute(query, (question_id,))
    return result.fetchone()

# ❌ 错误: 字符串拼接
async def find_question(question_id: str) -> Question | None:
    """SQL 注入风险"""
    query = f"SELECT * FROM questions WHERE id = '{question_id}'"
    result = await db.execute(query)
    return result.fetchone()
```

**说明**:
- 始终使用参数化查询
- 不要使用字符串拼接 SQL
- 使用 ORM 或查询构建器

---

## 项目特定规范

### 目录结构

```
src/
├── api/                    # API 路由层
│   ├── routes/             # 路由定义
│   ├── app.py              # FastAPI 应用
│   └── deps.py             # 依赖注入
├── bot/                    # 钉钉机器人模块
│   ├── handler.py          # 消息处理器
│   ├── sender.py           # 消息发送
│   ├── router.py           # Stream 连接管理
│   └── session.py          # 会话管理
├── services/               # 业务服务层
│   ├── qa_service.py       # 问答服务
│   ├── knowledge_service.py # 知识库管理
│   └── analytics_service.py # 分析汇总
├── domain/                 # 领域模型
│   ├── models/             # 数据模型
│   ├── enums.py            # 枚举
│   ├── exceptions.py       # 异常
│   └── ports.py            # 接口定义
├── rag/                    # RAG 模块
│   ├── pipeline.py         # RAG 管道
│   ├── embedding.py        # Embedding
│   ├── retriever.py        # 检索器
│   ├── context.py          # 上下文组装
│   └── vectorstore.py      # 向量库
├── parser/                 # 代码解析模块
│   ├── vue_parser.py       # Vue 解析
│   ├── router_parser.py    # 路由解析
│   ├── component_parser.py # 组件解析
│   └── builder.py          # 知识构建
├── llm/                    # LLM 服务模块
│   ├── client.py           # Ollama 客户端
│   ├── prompts/            # Prompt 模板
│   └── templates.py        # 模板管理
├── analyzer/               # 问题分析模块
│   ├── classifier.py       # 分类器
│   ├── summarizer.py       # 汇总
│   └── reporter.py         # 报告生成
├── infrastructure/         # 基础设施层
│   ├── database.py         # 数据库
│   ├── repositories/       # 仓储实现
│   └── external/           # 外部服务
├── shared/                 # 公共模块
├── main.py                 # 应用入口
└── config.py               # 配置
```

### 依赖注入

```python
# src/api/deps.py
from fastapi import Depends, Request
from src.services.qa_service import QAService
from src.services.knowledge_service import KnowledgeService

def get_qa_service(request: Request) -> QAService:
    """获取问答服务"""
    return request.app.state.qa_service

def get_knowledge_service(request: Request) -> KnowledgeService:
    """获取知识库服务"""
    return request.app.state.knowledge_service

# 使用
@app.post("/api/chat")
async def chat(
    question: str,
    qa_service: QAService = Depends(get_qa_service)
):
    answer = await qa_service.ask(question)
    return {"answer": answer.text}
```

**说明**:
- 使用 FastAPI 的依赖注入系统
- 从 `request.app.state` 获取服务实例
- 便于测试和替换

### 配置管理

```python
# src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "dingtalk-qa-bot"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # 钉钉配置
    DINGTALK_APP_KEY: str
    DINGTALK_APP_SECRET: str
    
    # Ollama 配置
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:35b-a3b-instruct-4bit"
    
    # RAG 配置
    RAG_TOP_K: int = 5
    RAG_THRESHOLD: float = 0.7
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }

settings = Settings()
```

**说明**:
- 使用 Pydantic Settings 管理配置
- 从环境变量和 `.env` 文件加载
- 提供默认值
- 敏感信息不设置默认值

---

## 附录

### 常用工具

```bash
# 代码格式化
uv run ruff format src/ tests/

# 代码检查
uv run ruff check src/
uv run mypy src/

# 运行测试
uv run pytest tests/ -v --cov=src

# 运行开发服务器
uv run uvicorn src.main:app --reload

# 构建知识库
uv run scripts/build_knowledge.py
```

### 参考链接

- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [mypy 官方文档](https://mypy.readthedocs.io/)
- [pytest 官方文档](https://docs.pytest.org/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [loguru 官方文档](https://loguru.readthedocs.io/)
- [Python asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)

---

## 更新记录

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0 | 2026-06-15 | 初始版本,包含完整的代码规范 |

---

**注意**: 本文档是项目的代码规范指南,所有开发者必须遵循这些规范。如有疑问或建议,请提交 Issue 或 PR。
