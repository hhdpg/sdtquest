# 钉钉智能问答机器人 — 代码架构设计文档

> **版本**: v1.0  
> **日期**: 2026-06-15  
> **状态**: 初稿  
> **关联文档**: 《钉钉智能问答机器人系统 — 概要设计文档》

---

## 目录

- [1. 文档说明](#1-文档说明)
- [2. 架构风格](#2-架构风格)
- [3. 技术选型](#3-技术选型)
- [4. 项目结构](#4-项目结构)
- [5. 分层架构](#5-分层架构)
- [6. 模块设计](#6-模块设计)
- [7. 核心设计模式](#7-核心设计模式)
- [8. 接口设计](#8-接口设计)
- [9. 数据模型](#9-数据模型)
- [10. 配置管理](#10-配置管理)
- [11. 错误处理](#11-错误处理)
- [12. 日志规范](#12-日志规范)
- [13. 测试策略](#13-测试策略)
- [14. 编码规范](#14-编码规范)
- [15. 依赖管理](#15-依赖管理)
- [16. 附录](#16-附录)

---

## 1. 文档说明

### 1.1 目的

本文档定义钉钉智能问答机器人的代码架构设计规范，包括目录结构、分层策略、设计模式、编码规范等内容，作为后续开发的指导依据。

### 1.2 适用范围

本文档适用于本项目全部后端代码的设计与开发，前端代码解析部分仅涉及解析器的设计，不涉及前端代码本身的改造。

### 1.3 术语定义

| 术语 | 说明 |
|------|------|
| Bot Service | 钉钉机器人服务，负责消息收发 |
| RAG | Retrieval-Augmented Generation，检索增强生成 |
| Knowledge Base | 知识库，由代码解析和手动文档构建 |
| Embedding | 将文本转换为向量表示的过程 |
| ChromaDB | 本地向量数据库 |
| AST | Abstract Syntax Tree，抽象语法树 |

---

## 2. 架构风格

### 2.1 整体风格：分层架构 (Layered Architecture)

采用经典的 **分层架构** 风格，按职责将代码划分为若干层次，每层仅依赖其下层，禁止反向依赖和跨层调用。

```
┌─────────────────────────────────────────────────────┐
│                  Presentation Layer                  │
│            (API 路由、钉钉消息入口)                    │
│                  ↓ 依赖                              │
├─────────────────────────────────────────────────────┤
│                  Application Layer                   │
│            (业务用例编排、流程控制)                     │
│                  ↓ 依赖                              │
├─────────────────────────────────────────────────────┤
│                   Domain Layer                       │
│         (核心业务逻辑、领域模型、规则)                  │
│                  ↓ 依赖                              │
├─────────────────────────────────────────────────────┤
│               Infrastructure Layer                  │
│      (数据库、向量库、Ollama、钉钉API、文件IO)         │
└─────────────────────────────────────────────────────┘
```

**分层规则**：

| 规则 | 说明 |
|------|------|
| 上层可调用下层 | API 层 → Application 层 → Domain 层 → Infrastructure 层 |
| 下层不可调用上层 | Infrastructure 层不可直接调用 API 层 |
| 同层可互相调用 | 同一层内的不同模块可以互相引用 |
| Domain 层无外部依赖 | 核心业务逻辑不依赖任何框架和外部库的具体实现 |

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| **单一职责** | 每个类/模块只负责一件事 |
| **依赖倒置** | 高层模块依赖抽象接口，不依赖具体实现 |
| **接口隔离** | 对外暴露最小化的接口，内部实现可自由替换 |
| **开闭原则** | 对扩展开放（新增检索策略、新增解析器），对修改关闭 |
| **约定优于配置** | 统一的目录命名、文件命名、类命名规范 |

### 2.3 模块化策略

按 **业务功能** 划分模块，每个模块内部自包含完整的分层结构：

```
modules/
├── bot/          # 钉钉机器人模块
├── rag/          # RAG 检索模块
├── parser/       # 代码解析模块
├── llm/          # LLM 服务模块
├── analyzer/     # 问题分析模块
└── knowledge/    # 知识库管理模块
```

---

## 3. 技术选型

### 3.1 后端框架

| 组件 | 选型 | 版本 | 用途 |
|------|------|------|------|
| 语言 | Python | >=3.11 | 开发语言 |
| Web 框架 | FastAPI | >=0.110 | HTTP 服务、API 路由 |
| ASGI 服务器 | Uvicorn | >=0.27 | 运行 FastAPI |
| 异步任务 | asyncio + asyncio.Queue | 内置 | 消息队列、并发控制 |
| 定时任务 | APScheduler | >=3.10 | 定时汇总任务 |

### 3.2 AI & RAG

| 组件 | 选型 | 用途 |
|------|------|------|
| LLM 运行时 | Ollama | 本地模型服务 |
| 生成模型 | qwen3.5:35b-a3b-instruct-4bit | 文本生成 |
| Embedding 模型 | bge-m3 | 文本向量化 |
| RAG 框架 | LlamaIndex | 检索管道编排 |
| 向量数据库 | ChromaDB | 向量存储与检索 |

### 3.3 代码解析

| 组件 | 选型 | 用途 |
|------|------|------|
| AST 解析 | tree-sitter + tree-sitter-vue | Vue SFC 解析 |
| HTML 模板 | beautifulsoup4 | 辅助解析 template 部分 |
| JS/TS 解析 | tree-sitter-javascript / tree-sitter-typescript | script 部分解析 |

### 3.4 数据存储

| 组件 | 选型 | 用途 |
|------|------|------|
| 关系数据库 | SQLite (sqlite3 内置) | 问答日志、统计分析 |
| 向量数据库 | ChromaDB | 知识库向量索引 |
| 缓存 | 内存字典 (LRU Cache) | 相似问题缓存 |

### 3.5 工具库

| 组件 | 选型 | 用途 |
|------|------|------|
| 数据校验 | Pydantic v2 | 数据模型定义和校验 |
| 日志 | loguru | 结构化日志 |
| 配置管理 | pydantic-settings | 环境变量管理 |
| HTTP 客户端 | httpx | 异步 HTTP 请求 (Ollama API) |
| 钉钉 SDK | dingtalk-stream | 钉钉 Stream 模式 |
| 依赖管理 | uv | 包管理 |

---

## 4. 项目结构

### 4.1 目录结构

```
dingtalk-qa-bot/
│
├── pyproject.toml                      # 项目配置、依赖声明
├── .env                                # 环境变量 (不提交到 Git)
├── .env.example                        # 环境变量示例
├── Makefile                            # 常用命令快捷方式
├── README.md                           # 项目说明
│
├── src/                                # ===== 源代码根目录 =====
│   │
│   ├── main.py                         # 应用入口，启动服务
│   ├── config.py                       # 全局配置定义 (Pydantic Settings)
│   │
│   ├── api/                            # ── Presentation 层 ──
│   │   ├── __init__.py
│   │   ├── app.py                      # FastAPI 应用实例
│   │   ├── deps.py                     # 公共依赖注入
│   │   └── routes/                     # API 路由
│   │       ├── __init__.py
│   │       ├── health.py               # 健康检查 /health
│   │       ├── chat.py                 # 对话接口 (调试用)
│   │       ├── knowledge.py            # 知识库管理接口
│   │       └── analytics.py            # 统计分析接口
│   │
│   ├── bot/                            # ── 钉钉机器人模块 ──
│   │   ├── __init__.py
│   │   ├── handler.py                  # Stream 消息处理器
│   │   ├── sender.py                   # 消息发送
│   │   ├── router.py                   # 机器人启动/连接管理
│   │   └── session.py                  # 会话上下文管理
│   │
│   ├── services/                       # ── Application 层 ──
│   │   ├── __init__.py
│   │   ├── qa_service.py              # 问答服务 (核心编排)
│   │   ├── knowledge_service.py        # 知识库管理服务
│   │   └── analytics_service.py        # 分析汇总服务
│   │
│   ├── domain/                         # ── Domain 层 ──
│   │   ├── __init__.py
│   │   ├── models/                     # 领域模型
│   │   │   ├── __init__.py
│   │   │   ├── question.py             # 问题模型
│   │   │   ├── answer.py              # 回答模型
│   │   │   ├── knowledge.py           # 知识条目模型
│   │   │   └── conversation.py        # 会话模型
│   │   ├── enums.py                    # 枚举定义
│   │   ├── exceptions.py              # 领域异常
│   │   └── ports.py                    # 端口接口定义 (依赖倒置)
│   │
│   ├── rag/                            # ── RAG 模块 ──
│   │   ├── __init__.py
│   │   ├── pipeline.py                # RAG 主流程编排
│   │   ├── embedding.py               # bge-m3 Embedding 封装
│   │   ├── retriever.py               # 混合检索器
│   │   ├── reranker.py                # 重排序 (可选扩展)
│   │   ├── context.py                 # Prompt 上下文组装
│   │   └── vectorstore.py             # ChromaDB 封装
│   │
│   ├── parser/                         # ── 代码解析模块 ──
│   │   ├── __init__.py
│   │   ├── vue_parser.py              # Vue 2 SFC 解析器
│   │   ├── router_parser.py           # Vue Router 路由解析
│   │   ├── store_parser.py            # Vuex Store 解析
│   │   ├── component_parser.py        # Element UI 组件提取
│   │   ├── api_parser.py              # Axios API 调用解析
│   │   └── builder.py                 # 知识库文档构建器
│   │
│   ├── llm/                            # ── LLM 服务模块 ──
│   │   ├── __init__.py
│   │   ├── client.py                   # Ollama 客户端
│   │   ├── prompts/                    # Prompt 模板
│   │   │   ├── __init__.py
│   │   │   ├── qa.py                   # 问答 Prompt
│   │   │   ├── enrichment.py          # 知识丰富 Prompt
│   │   │   └── classify.py            # 问题分类 Prompt
│   │   └── templates.py               # 模板管理器
│   │
│   ├── analyzer/                       # ── 问题分析模块 ──
│   │   ├── __init__.py
│   │   ├── classifier.py              # 问题分类器
│   │   ├── summarizer.py              # 问题汇总
│   │   └── reporter.py                # 报告生成
│   │
│   ├── infrastructure/                 # ── Infrastructure 层 ──
│   │   ├── __init__.py
│   │   ├── database.py                # SQLite 连接管理
│   │   ├── repositories/              # 数据仓储实现
│   │   │   ├── __init__.py
│   │   │   ├── question_repo.py       # 问答记录仓储
│   │   │   └── knowledge_repo.py      # 知识条目仓储
│   │   └── external/                  # 外部服务适配器
│   │       ├── __init__.py
│   │       ├── dingtalk_client.py     # 钉钉 API 客户端
│   │       └── ollama_adapter.py      # Ollama 适配器
│   │
│   └── shared/                         # ── 公共模块 ──
│       ├── __init__.py
│       ├── utils.py                   # 通用工具函数
│       ├── cache.py                   # LRU 缓存
│       └── constants.py               # 全局常量
│
├── scripts/                            # ===== 独立脚本 =====
│   ├── build_knowledge.py             # 知识库构建 (全量)
│   ├── parse_code.py                  # 代码解析
│   ├── import_docs.py                 # 导入手动文档
│   └── seed_classifier.py             # 分类器种子数据
│
├── data/                               # ===== 数据目录 =====
│   ├── knowledge/                      # 知识库原始文件
│   ├── chroma_db/                      # ChromaDB 持久化
│   ├── analytics.db                    # SQLite 分析数据库
│   └── cache/                          # 临时缓存
│
├── tests/                              # ===== 测试 =====
│   ├── conftest.py                    # pytest 全局 fixture
│   ├── unit/                          # 单元测试
│   │   ├── test_parser/
│   │   ├── test_rag/
│   │   ├── test_llm/
│   │   └── test_services/
│   ├── integration/                   # 集成测试
│   │   ├── test_qa_pipeline.py
│   │   └── test_bot_flow.py
│   └── fixtures/                      # 测试数据
│       ├── sample_vue_project/        # 模拟 Vue 项目
│       └── sample_knowledge/          # 模拟知识库
│
└── docs/                               # ===== 文档 =====
    ├── design-dingtalk-qa-bot.md       # 概要设计文档
    └── code-architecture.md            # 本文档
```

### 4.2 目录职责说明

| 目录 | 职责 | 可依赖 |
|------|------|--------|
| `src/api/` | HTTP 路由、请求参数校验、响应序列化 | services, domain |
| `src/bot/` | 钉钉 Stream 消息收发 | services, domain |
| `src/services/` | 业务用例编排，串联多个模块 | domain, rag, llm, analyzer, infrastructure |
| `src/domain/` | 核心模型、枚举、异常、端口接口 | (不依赖任何其他层) |
| `src/rag/` | 检索管道：Embedding、向量检索、上下文组装 | domain, llm (仅接口) |
| `src/parser/` | Vue 2 代码解析、知识文档生成 | domain |
| `src/llm/` | Ollama 客户端封装、Prompt 管理 | domain, config |
| `src/analyzer/` | 问题分类、统计汇总、报告生成 | domain, infrastructure |
| `src/infrastructure/` | 数据库、外部服务的实际实现 | domain |
| `src/shared/` | 跨模块共享的工具和常量 | (不依赖业务模块) |

---

## 5. 分层架构

### 5.1 各层详细职责

```
┌─────────────────────────────────────────────────────────────────┐
│  Presentation Layer (src/api, src/bot)                          │
│  ─────────────────────────────────────────────────────────────  │
│  · 接收 HTTP 请求 / 钉钉 Stream 消息                             │
│  · 参数校验 (Pydantic)                                          │
│  · 调用 Application 层服务                                       │
│  · 格式化响应 (JSON / 钉钉 Markdown)                             │
│  · 不包含业务逻辑                                                │
├─────────────────────────────────────────────────────────────────┤
│  Application Layer (src/services)                               │
│  ─────────────────────────────────────────────────────────────  │
│  · 编排一个完整的业务用例                                         │
│  · 例: QAService.process_question() 编排                        │
│    分类 → 检索 → 组装Prompt → LLM生成 → 记录日志                  │
│  · 事务控制 (数据库写入)                                          │
│  · 不包含核心规则，只做流程串联                                     │
├─────────────────────────────────────────────────────────────────┤
│  Domain Layer (src/domain)                                      │
│  ─────────────────────────────────────────────────────────────  │
│  · 领域模型: Question, Answer, KnowledgeItem, Conversation      │
│  · 枚举: QuestionCategory, KnowledgeType                        │
│  · 业务规则: 问题分类规则, 检索阈值判断                            │
│  · 端口接口: LLMClient, VectorStore, MessageSender              │
│  · 纯 Python，不依赖任何框架                                     │
├─────────────────────────────────────────────────────────────────┤
│  Infrastructure Layer (src/infrastructure, src/rag, src/llm)    │
│  ─────────────────────────────────────────────────────────────  │
│  · 数据库: SQLite 连接、Repository 实现                           │
│  · 向量库: ChromaDB 操作封装                                     │
│  · 外部服务: Ollama API 调用, 钉钉 API 调用                       │
│  · 文件 IO: 代码文件读取, 知识库文件读写                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 依赖关系图

```
api/ ──────→ services/ ──────→ domain/
  │               │                ↑
  │               ↓                │
  ├──→ bot/ ───→ rag/ ────────→ domain/
  │               │                ↑
  │               ↓                │
  │            llm/ ───────────→ domain/
  │               │                ↑
  │               ↓                │
  └──→ services/ ──→ infrastructure/ ──→ domain/
                         │
                         ↓
                     shared/
```

**关键约束**:
- `domain/` 不 import 任何其他模块，仅定义接口 (Protocol)
- `infrastructure/` 实现 `domain/` 中定义的接口
- `services/` 通过接口依赖，运行时注入具体实现

---

## 6. 模块设计

### 6.1 钉钉机器人模块 (src/bot)

**职责**: 钉钉 Stream 消息的接收和发送

```
src/bot/
├── handler.py       # 消息处理器，接收@消息，调用 qa_service
├── sender.py        # 消息发送，支持文本/Markdown/卡片
├── router.py        # Stream 连接管理，自动重连
└── session.py       # 会话上下文，维护多轮对话
```

**类设计**:

```python
class BotHandler:
    """钉钉消息处理器"""
    def __init__(self, qa_service: QAService, session: SessionManager):
        ...
    async def on_message(self, message: DingTalkMessage) -> None:
        """收到消息的入口"""
        ...

class MessageSender:
    """消息发送器"""
    async def send_text(self, conversation_id: str, text: str) -> None: ...
    async def send_markdown(self, conversation_id: str, title: str, text: str) -> None: ...
    async def update_message(self, message_id: str, new_content: str) -> None: ...

class SessionManager:
    """会话管理，LRU 淘汰过期会话"""
    def get_history(self, conversation_id: str) -> list[Message]: ...
    def add_message(self, conversation_id: str, message: Message) -> None: ...
    def clear(self, conversation_id: str) -> None: ...
```

### 6.2 RAG 模块 (src/rag)

**职责**: 检索管道，从知识库中检索相关内容并组装 Prompt

```
src/rag/
├── pipeline.py       # RAG 主流程: 检索 → 排序 → 组装
├── embedding.py      # bge-m3 向量化封装
├── retriever.py      # 混合检索 (Dense + Sparse + RRF)
├── reranker.py       # 重排序 (扩展点)
├── context.py        # Prompt 上下文组装器
└── vectorstore.py    # ChromaDB 操作封装
```

**类设计**:

```python
class RAGPipeline:
    """RAG 主流程编排"""
    def __init__(self, retriever: HybridRetriever, context: ContextAssembler):
        ...
    async def query(self, question: Question, category: QuestionCategory) -> RAGResult:
        """
        执行检索流程:
        1. 根据问题类型选择检索策略
        2. 混合检索 (Dense + Sparse)
        3. RRF 融合排序
        4. 组装上下文
        """
        ...

class HybridRetriever:
    """混合检索器"""
    def __init__(self, vectorstore: ChromaVectorStore, embedding: EmbeddingService):
        ...
    async def retrieve(self, query: str, top_k: int, threshold: float) -> list[KnowledgeItem]:
        """
        执行混合检索:
        - bge-m3 Dense 向量检索
        - bge-m3 Sparse 关键词检索
        - RRF 融合排序
        """
        ...

class ChromaVectorStore:
    """ChromaDB 封装，实现 domain 中定义的 VectorStore 接口"""
    ...

class ContextAssembler:
    """将检索结果组装为 LLM Prompt"""
    def assemble(self, question: str, docs: list[KnowledgeItem], 
                 history: list[Message], category: QuestionCategory) -> str:
        ...
```

### 6.3 代码解析模块 (src/parser)

**职责**: 解析 Vue 2 前端代码，提取操作知识

```
src/parser/
├── vue_parser.py        # Vue 2 SFC 整体解析入口
├── router_parser.py     # Vue Router 3 路由配置解析
├── store_parser.py      # Vuex Store 状态/操作解析
├── component_parser.py  # Element UI 组件提取 (Button/Form/Table等)
├── api_parser.py        # Axios API 调用关系解析
└── builder.py           # 知识文档构建器
```

**Vue 2 项目解析策略**:

```
前端代码结构 (典型 Vue 2 + Vue CLI 4 项目):

src/
├── router/
│   └── index.js              ← router_parser.py 解析: 路由表、页面路径
├── store/
│   ├── index.js              ← store_parser.py 解析: modules、actions
│   └── modules/
├── views/ 或 src/pages/
│   ├── order/
│   │   ├── index.vue         ← vue_parser.py 解析: template + script
│   │   └── components/
│   └── user/
│       └── index.vue
├── components/               ← component_parser.py 解析: 通用组件
├── api/ 或 src/services/
│   └── order.js              ← api_parser.py 解析: API 接口定义
└── utils/
```

**类设计**:

```python
class VueProjectParser:
    """Vue 2 项目解析入口"""
    def __init__(self, project_root: Path, config: ParserConfig):
        ...
    def parse(self) -> ParseResult:
        """
        完整解析流程:
        1. 扫描项目结构，识别目录布局
        2. 解析路由配置 → 页面列表
        3. 遍历每个页面 .vue 文件 → 提取组件、按钮、表单
        4. 解析 Vuex Store → 提取数据操作
        5. 解析 API 文件 → 提取接口调用
        6. 汇总所有解析结果
        """
        ...

class VueSFCParser:
    """单个 Vue 2 单文件组件解析"""
    def parse(self, file_path: Path) -> SFCResult:
        """
        解析 .vue 文件的三个部分:
        - <template>: Element UI 组件 (el-button, el-form, el-table...)
        - <script>: methods, computed, data
        - <style>: 通常忽略
        """
        ...

class ElementUIExtractor:
    """Element UI 组件提取器"""
    def extract_buttons(self, template_ast) -> list[ButtonInfo]:
        """提取 el-button，获取文本、点击事件、权限指令"""
        ...
    def extract_forms(self, template_ast) -> list[FormInfo]:
        """提取 el-form 及其字段 (el-input, el-select 等)"""
        ...
    def extract_tables(self, template_ast) -> list[TableInfo]:
        """提取 el-table 及其列定义"""
        ...
    def extract_dialogs(self, template_ast) -> list[DialogInfo]:
        """提取 el-dialog 弹窗内容"""
        ...

class KnowledgeBuilder:
    """将解析结果构建为知识文档"""
    def build(self, parse_result: ParseResult) -> list[KnowledgeItem]:
        """
        按页面组织知识:
        - 每个页面生成一个综合文档
        - 包含: 页面说明、菜单路径、按钮操作、表单字段、关联API
        """
        ...
```

### 6.4 LLM 服务模块 (src/llm)

**职责**: 封装 Ollama API 调用和 Prompt 管理

```
src/llm/
├── client.py            # Ollama HTTP 客户端
├── templates.py         # Prompt 模板加载和管理
└── prompts/
    ├── qa.py            # 问答场景 Prompt
    ├── enrichment.py    # 知识丰富场景 Prompt
    └── classify.py      # 问题分类场景 Prompt
```

**类设计**:

```python
class OllamaClient:
    """Ollama API 客户端，实现 domain 中定义的 LLMClient 接口"""
    def __init__(self, base_url: str, model: str):
        ...
    async def generate(self, prompt: str, options: GenerateOptions) -> str:
        """文本生成"""
        ...
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化 (bge-m3)"""
        ...
    async def generate_stream(self, prompt: str, options: GenerateOptions) -> AsyncIterator[str]:
        """流式生成"""
        ...
```

### 6.5 问题分析模块 (src/analyzer)

**职责**: 问题分类、统计汇总、报告生成

```
src/analyzer/
├── classifier.py    # 问题分类 (规则 + 可选 ML)
├── summarizer.py    # 问题汇总统计
└── reporter.py      # 汇总报告生成
```

### 6.6 基础设施层 (src/infrastructure)

**职责**: 数据库、外部服务的具体实现

```
src/infrastructure/
├── database.py                  # SQLite 连接池、初始化
├── repositories/
│   ├── question_repo.py         # 问答记录 CRUD
│   └── knowledge_repo.py        # 知识条目 CRUD
└── external/
    ├── dingtalk_client.py       # 钉钉开放平台 API
    └── ollama_adapter.py        # Ollama 适配器 (如果需要额外封装)
```

**Repository 模式**: 数据访问统一通过 Repository 接口，业务层不直接写 SQL。

```python
# domain/ports.py 中定义接口
class QuestionRepository(Protocol):
    def save(self, record: QuestionRecord) -> None: ...
    def find_recent(self, days: int, limit: int) -> list[QuestionRecord]: ...
    def count_by_category(self, days: int) -> dict[str, int]: ...

# infrastructure/repositories/question_repo.py 中实现
class SQLiteQuestionRepository:
    """SQLite 实现"""
    def save(self, record: QuestionRecord) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO ...", (...))
```

---

## 7. 核心设计模式

### 7.1 依赖注入 (Dependency Injection)

通过 Python Protocol (结构化子类型) 实现接口与实现解耦：

```python
# src/domain/ports.py — 定义接口
from typing import Protocol

class LLMClient(Protocol):
    async def generate(self, prompt: str, options: GenerateOptions) -> str: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

class VectorStore(Protocol):
    async def add(self, items: list[KnowledgeItem]) -> None: ...
    async def search(self, query: list[float], top_k: int) -> list[KnowledgeItem]: ...

class QuestionRepository(Protocol):
    def save(self, record: QuestionRecord) -> None: ...
    def find_recent(self, days: int) -> list[QuestionRecord]: ...

class MessageSender(Protocol):
    async def send_markdown(self, conversation_id: str, title: str, text: str) -> None: ...
```

```python
# src/main.py — 组装依赖 (Composition Root)
from src.llm.client import OllamaClient
from src.rag.vectorstore import ChromaVectorStore
from src.infrastructure.repositories.question_repo import SQLiteQuestionRepository
from src.services.qa_service import QAService

def create_app() -> FastAPI:
    # 1. 创建基础设施实例
    llm_client = OllamaClient(base_url=settings.OLLAMA_URL, model=settings.MODEL)
    vectorstore = ChromaVectorStore(persist_dir=settings.CHROMA_DB_DIR)
    question_repo = SQLiteQuestionRepository(db_path=settings.ANALYTICS_DB)

    # 2. 组装服务
    qa_service = QAService(
        llm=llm_client,
        vectorstore=vectorstore,
        question_repo=question_repo,
    )

    # 3. 注入到路由
    app = create_fastapi_app()
    app.state.qa_service = qa_service
    return app
```

### 7.2 策略模式 (Strategy Pattern)

用于 RAG 检索策略和代码解析策略的可插拔扩展：

```python
# 检索策略
class RetrievalStrategy(Protocol):
    async def retrieve(self, query: str, top_k: int) -> list[KnowledgeItem]: ...

class DenseRetrieval:
    """bge-m3 稠密向量检索"""
    ...

class SparseRetrieval:
    """bge-m3 稀疏关键词检索"""
    ...

class HybridRetriever:
    """组合多个策略，RRF 融合"""
    def __init__(self, strategies: list[RetrievalStrategy]):
        self.strategies = strategies
    ...
```

### 7.3 管道模式 (Pipeline Pattern)

RAG 流程采用管道模式，每个步骤可独立测试和替换：

```python
class RAGPipeline:
    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps

    async def run(self, input: Question) -> RAGResult:
        result = input
        for step in self.steps:
            result = await step.execute(result)
        return result

# 组装管道
pipeline = RAGPipeline(steps=[
    ClassifyStep(),         # 问题分类
    RetrieveStep(),         # 混合检索
    AssembleContextStep(),  # 上下文组装
    GenerateStep(),         # LLM 生成
    FormatStep(),           # 格式化输出
])
```

### 7.4 仓储模式 (Repository Pattern)

数据访问通过 Repository 抽象，隔离数据库实现细节：

```python
# 业务层通过接口使用
class QAService:
    def __init__(self, question_repo: QuestionRepository, ...):
        self.question_repo = question_repo

    async def process(self, question: Question) -> Answer:
        ...
        # 保存问答记录
        self.question_repo.save(QuestionRecord(...))
```

### 7.5 工厂模式 (Factory Pattern)

知识构建中的解析器工厂，根据文件类型选择解析策略：

```python
class ParserFactory:
    @staticmethod
    def create_parser(file_type: str) -> FileParser:
        parsers = {
            ".vue": VueSFCParser(),
            ".js": JavaScriptParser(),
            ".ts": TypeScriptParser(),
            ".json": JSONConfigParser(),
        }
        return parsers.get(file_type, NullParser())
```

---

## 8. 接口设计

### 8.1 API 路由设计

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/health` | 健康检查 | - | `{ "status": "ok" }` |
| POST | `/api/chat` | 对话接口 (调试用) | `{ "question": "...", "conversation_id": "..." }` | `{ "answer": "...", "sources": [...] }` |
| POST | `/api/knowledge/build` | 触发知识库构建 | `{ "project_root": "/path/to/frontend" }` | `{ "status": "building", "task_id": "..." }` |
| GET | `/api/knowledge/stats` | 知识库统计 | - | `{ "total_items": 120, "last_build": "..." }` |
| GET | `/api/analytics/summary` | 问题汇总 | `?days=7` | `{ "total": 50, "categories": {...} }` |
| GET | `/api/analytics/top-questions` | 高频问题 | `?days=7&limit=10` | `{ "questions": [...] }` |

### 8.2 核心服务接口

```python
class QAService:
    """问答服务 — 核心业务编排"""

    async def ask(self, question: str, conversation_id: str) -> Answer:
        """
        处理用户提问的完整流程:
        1. 会话上下文获取
        2. 问题分类
        3. RAG 检索
        4. Prompt 组装
        5. LLM 生成
        6. 回答后处理
        7. 日志记录
        """
        ...

class KnowledgeService:
    """知识库管理服务"""

    async def build_from_code(self, project_root: Path) -> BuildResult:
        """从前端代码构建知识库"""
        ...

    async def import_document(self, doc: Document) -> None:
        """导入手动文档"""
        ...

    async def get_stats(self) -> KnowledgeStats:
        """获取知识库统计信息"""
        ...
```

### 8.3 钉钉 Stream 回调接口

```python
class BotHandler:
    """钉钉消息处理器"""

    async def process(self, callback: CallbackMessage) -> tuple[int, str]:
        """
        Stream 回调入口:
        1. 解析消息
        2. 检测 @提及
        3. 异步处理
        4. 返回 ACK
        """
        ...
```

---

## 9. 数据模型

### 9.1 领域模型 (src/domain/models)

```python
# src/domain/models/question.py
class Question(BaseModel):
    """用户提问"""
    id: str                           # UUID
    text: str                         # 问题文本
    sender_id: str                    # 发送人钉钉ID
    conversation_id: str              # 会话ID
    category: QuestionCategory | None # 分类 (分类后填充)
    created_at: datetime

# src/domain/models/answer.py
class Answer(BaseModel):
    """生成的回答"""
    id: str
    question_id: str                  # 关联的问题ID
    text: str                         # 回答文本
    sources: list[str]                # 引用的知识文档ID
    confidence: float                 # 置信度 0-1
    category: QuestionCategory        # 问题分类
    created_at: datetime

# src/domain/models/knowledge.py
class KnowledgeItem(BaseModel):
    """知识条目"""
    id: str
    type: KnowledgeType               # page / button / form / workflow / manual
    title: str                        # 标题
    content: str                      # 内容
    page_name: str | None             # 所属页面
    page_path: str | None             # 页面路径
    source_file: str | None           # 来源文件
    tags: list[str]                   # 标签
    embedding: list[float] | None     # 向量 (入库后由向量库管理)
    created_at: datetime
    updated_at: datetime

# src/domain/models/conversation.py
class Conversation(BaseModel):
    """会话上下文"""
    id: str
    messages: list[Message]           # 消息历史
    last_active: datetime
```

### 9.2 枚举定义 (src/domain/enums.py)

```python
from enum import Enum

class QuestionCategory(str, Enum):
    """问题分类"""
    OPERATION_GUIDE = "operation_guide"        # 操作指南
    PROCESS_INQUIRY = "process_inquiry"        # 流程咨询
    ANOMALY_TROUBLESHOOT = "anomaly_troubleshoot"  # 异常排查
    GENERAL = "general"                        # 其他/闲聊

class KnowledgeType(str, Enum):
    """知识类型"""
    PAGE = "page"                # 页面说明
    BUTTON = "button"            # 按钮操作
    FORM = "form"                # 表单说明
    WORKFLOW = "workflow"        # 流程说明
    API = "api"                  # API 接口
    MANUAL = "manual"            # 手动文档

class AnswerStatus(str, Enum):
    """回答状态"""
    SUCCESS = "success"          # 成功回答
    NO_MATCH = "no_match"        # 未匹配到知识
    ERROR = "error"              # 生成出错
    TIMEOUT = "timeout"          # 超时
```

### 9.3 数据库表设计 (SQLite)

```sql
-- 问答记录表
CREATE TABLE question_records (
    id              TEXT PRIMARY KEY,
    question        TEXT NOT NULL,
    answer          TEXT,
    category        TEXT,
    sender_id       TEXT NOT NULL,
    conversation_id TEXT,
    confidence      REAL DEFAULT 0.0,
    status          TEXT NOT NULL,      -- success / no_match / error / timeout
    sources         TEXT,               -- JSON 数组
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 每日汇总表
CREATE TABLE daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            DATE NOT NULL,
    category        TEXT NOT NULL,
    question_count  INTEGER DEFAULT 0,
    top_questions   TEXT,               -- JSON 数组
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, category)
);

-- 索引
CREATE INDEX idx_questions_created_at ON question_records(created_at);
CREATE INDEX idx_questions_category ON question_records(category);
CREATE INDEX idx_questions_status ON question_records(status);
```

---

## 10. 配置管理

### 10.1 配置类定义 (src/config.py)

使用 Pydantic Settings，从 `.env` 文件和环境变量加载：

```python
# src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = "dingtalk-qa-bot"
    APP_ENV: str = "development"            # development / production
    LOG_LEVEL: str = "INFO"

    # ── 钉钉 ──
    DINGTALK_APP_KEY: str                   # 钉钉应用 AppKey
    DINGTALK_APP_SECRET: str                # 钉钉应用 AppSecret
    DINGTALK_BOT_CODE: str                  # 机器人编码

    # ── Ollama ──
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:35b-a3b-instruct-4bit"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    OLLAMA_TIMEOUT: int = 120               # 秒
    OLLAMA_MAX_CONCURRENT: int = 2          # 最大并发推理

    # ── RAG ──
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "knowledge_base"
    RAG_TOP_K: int = 5
    RAG_THRESHOLD_STANDARD: float = 0.8     # 标准操作类阈值
    RAG_THRESHOLD_FLEXIBLE: float = 0.6     # 灵活推理类阈值

    # ── 生成参数 ──
    LLM_TEMPERATURE_STANDARD: float = 0.3
    LLM_TEMPERATURE_FLEXIBLE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    LLM_CONTEXT_WINDOW: int = 8192

    # ── 数据库 ──
    ANALYTICS_DB_PATH: str = "./data/analytics.db"

    # ── 代码解析 ──
    PARSER_DEFAULT_PROJECT_ROOT: str = ""
    PARSER_SUPPORTED_EXTENSIONS: list[str] = [".vue", ".js", ".ts", ".json"]

    # ── 会话 ──
    SESSION_MAX_HISTORY: int = 10           # 最大保留对话轮数
    SESSION_TTL_SECONDS: int = 300          # 会话超时 (5分钟)

    # ── 限流 ──
    RATE_LIMIT_PER_USER: int = 60           # 同一用户提问间隔 (秒)
    MAX_QUEUE_SIZE: int = 100               # 消息队列最大长度

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

### 10.2 环境变量文件 (.env)

```bash
# 钉钉
DINGTALK_APP_KEY=your_app_key_here
DINGTALK_APP_SECRET=your_app_secret_here
DINGTALK_BOT_code=your_bot_code_here

# Ollama (可选，有默认值)
OLLAMA_BASE_URL=http://localhost:11434

# 日志
LOG_LEVEL=INFO
```

---

## 11. 错误处理

### 11.1 异常层级

```python
# src/domain/exceptions.py

class AppException(Exception):
    """应用基础异常"""
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code

# ── 业务异常 ──
class QuestionProcessingError(AppException):
    """问答处理失败"""
    code = "QA_PROCESSING_ERROR"

class KnowledgeNotFoundError(AppException):
    """知识库中未找到匹配内容"""
    code = "KNOWLEDGE_NOT_FOUND"

# ── 基础设施异常 ──
class LLMServiceError(AppException):
    """LLM 服务调用失败"""
    code = "LLM_SERVICE_ERROR"

class VectorStoreError(AppException):
    """向量库操作失败"""
    code = "VECTOR_STORE_ERROR"

class DingTalkAPIError(AppException):
    """钉钉 API 调用失败"""
    code = "DINGTALK_API_ERROR"

class ParserError(AppException):
    """代码解析失败"""
    code = "PARSER_ERROR"
```

### 11.2 错误处理策略

| 层级 | 策略 | 说明 |
|------|------|------|
| API 层 | 全局异常拦截器 | 捕获所有异常，返回统一错误格式 |
| Bot 层 | try-except 包裹 | 捕获异常后回复用户 "暂时无法回答，请稍后再试" |
| Service 层 | 抛出业务异常 | 不处理基础设施异常，向上抛出 |
| Infrastructure 层 | 捕获并转换为 AppException | 屏蔽第三方 SDK 的异常类型 |

```python
# API 层全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message}
    )

# Bot 层容错
class BotHandler:
    async def on_message(self, message):
        try:
            answer = await self.qa_service.ask(message.text, message.conversation_id)
            await self.sender.send_markdown(message.conversation_id, "回答", answer.text)
        except LLMServiceError:
            await self.sender.send_text(message.conversation_id, "⚠️ 服务繁忙，请稍后再试")
        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            await self.sender.send_text(message.conversation_id, "⚠️ 处理异常，请联系管理员")
```

---

## 12. 日志规范

### 12.1 日志框架

使用 **loguru**，配置统一在 `src/main.py` 启动时初始化：

```python
from loguru import logger
import sys

# 日志配置
logger.remove()  # 移除默认 handler
logger.add(sys.stderr, level=settings.LOG_LEVEL)
logger.add(
    "data/logs/bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{function}:{line} | {message}"
)
```

### 12.2 日志级别使用规范

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| `DEBUG` | 开发调试信息 | 检索到的文档列表、Prompt 内容 |
| `INFO` | 关键业务流程 | "收到问题: xxx"、"知识库构建完成，共 N 条" |
| `WARNING` | 非致命异常 | "检索未命中"、"模型响应慢 (>30s)" |
| `ERROR` | 业务异常 | "LLM 调用失败"、"钉钉 API 超时" |
| `CRITICAL` | 系统级故障 | "Ollama 服务不可用"、"数据库损坏" |

### 12.3 关键日志点

```python
# 收到消息
logger.info("收到问题 | sender={} | text={}", sender_id, question_text[:50])

# 问题分类
logger.info("问题分类 | category={} | confidence={:.2f}", category, confidence)

# RAG 检索
logger.info("检索结果 | top_k={} | max_score={:.3f}", len(docs), max_score)

# LLM 生成
logger.info("LLM 生成 | tokens={} | latency={:.1f}s", tokens, latency)

# 回答发送
logger.info("回答发送 | conversation={} | status={}", conversation_id, status)
```

---

## 13. 测试策略

### 13.1 测试分层

```
┌─────────────────────────────────────┐
│        E2E 测试 (少量)               │  钉钉消息 → 机器人 → 回答
├─────────────────────────────────────┤
│      集成测试 (适量)                 │  RAG管道、解析流水线
├─────────────────────────────────────┤
│      单元测试 (大量)                 │  各模块内部逻辑
└─────────────────────────────────────┘
```

### 13.2 测试目录结构

```
tests/
├── conftest.py                       # 全局 fixture (mock Ollama, mock DingTalk)
├── unit/
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
├── integration/
│   ├── test_qa_pipeline.py           # RAG + LLM 端到端
│   └── test_knowledge_build.py       # 代码解析 → 知识库构建
└── fixtures/
    ├── sample_vue_project/            # 模拟 Vue 2 项目文件
    └── sample_knowledge/              # 模拟知识条目
```

### 13.3 Mock 策略

| 外部依赖 | Mock 方式 | 说明 |
|----------|----------|------|
| Ollama API | pytest fixture 返回预设回答 | 避免测试时实际调用模型 |
| 钉钉 API | Mock HTTP 请求 | 验证消息格式正确 |
| ChromaDB | 使用临时目录 | 测试后自动清理 |
| SQLite | 使用内存数据库 | `:memory:` 模式 |

### 13.4 覆盖率目标

| 模块 | 目标 | 说明 |
|------|------|------|
| `domain/` | >90% | 纯逻辑，易测试 |
| `services/` | >80% | 业务编排，关键路径 |
| `rag/` | >70% | 检索逻辑，需要集成测试 |
| `parser/` | >70% | 解析逻辑，依赖 fixture |
| `infrastructure/` | >50% | 外部依赖多，重点测 Repository |

---

## 14. 编码规范

### 14.1 代码风格

| 规范 | 说明 |
|------|------|
| 风格指南 | PEP 8 |
| 格式化工具 | Ruff (替代 Black + isort) |
| 类型检查 | mypy，严格模式 |
| 行宽 | 120 字符 |
| 引号 | 双引号 (字符串)、单引号 (字典键) |
| Python 版本 | >= 3.11，使用新语法特性 |

### 14.2 命名规范

| 类型 | 风格 | 示例 |
|------|------|------|
| 文件名 | snake_case | `qa_service.py` |
| 类名 | PascalCase | `QAService`, `RAGPipeline` |
| 函数/方法 | snake_case | `process_question()`, `retrieve()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_QUEUE_SIZE`, `DEFAULT_TOP_K` |
| 枚举值 | UPPER_SNAKE_CASE | `QuestionCategory.OPERATION_GUIDE` |
| 私有成员 | 前缀 `_` | `_internal_state`, `_validate()` |
| 模块名 | snake_case，简短 | `rag`, `llm`, `bot` |

### 14.3 类型注解

所有公开接口必须有类型注解：

```python
# ✅ 正确
async def ask(self, question: str, conversation_id: str) -> Answer:
    ...

# ❌ 错误 — 缺少类型注解
async def ask(self, question, conversation_id):
    ...
```

### 14.4 文档字符串

每个公开类和函数必须有 docstring：

```python
class HybridRetriever:
    """
    混合检索器。
    
    组合 bge-m3 的 Dense 和 Sparse 两种检索模式，
    通过 RRF (Reciprocal Rank Fusion) 融合排序。
    """

    async def retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeItem]:
        """
        执行混合检索。
        
        Args:
            query: 用户问题文本
            top_k: 返回结果数量
            
        Returns:
            按相关性排序的知识条目列表
            
        Raises:
            VectorStoreError: 向量库查询失败
        """
        ...
```

### 14.5 import 顺序

```python
# 1. 标准库
import asyncio
from pathlib import Path
from typing import Protocol
from datetime import datetime

# 2. 第三方库
from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger

# 3. 项目内部模块
from src.domain.models import Question, Answer
from src.domain.ports import LLMClient, VectorStore
from src.config import settings
```

---

## 15. 依赖管理

### 15.1 依赖声明 (pyproject.toml)

```toml
[project]
name = "dingtalk-qa-bot"
version = "0.1.0"
description = "钉钉智能问答机器人 — 基于本地大模型的 RAG 问答系统"
requires-python = ">=3.11"

dependencies = [
    # Web & 钉钉
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "dingtalk-stream>=0.15",
    
    # RAG & 向量
    "chromadb>=0.5",
    "llama-index>=0.10",
    
    # LLM
    "httpx>=0.27",             # 异步 HTTP 客户端
    
    # 代码解析
    "tree-sitter>=0.22",
    "tree-sitter-vue>=0.2",
    "tree-sitter-javascript>=0.21",
    
    # 工具
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-dotenv>=1.0",
    "loguru>=0.7",
    "apscheduler>=3.10",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
]
dashboard = [
    "streamlit>=1.32",
]
```

### 15.2 Makefile 常用命令

```makefile
# Makefile

.PHONY: install run dev test lint format build-knowledge

install:
	uv sync

dev:
	uv run uvicorn src.main:create_app --reload --host 0.0.0.0 --port 8000

run:
	uv run uvicorn src.main:create_app --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v --cov=src

test-unit:
	uv run pytest tests/unit/ -v

lint:
	uv run ruff check src/
	uv run mypy src/

format:
	uv run ruff format src/ tests/

build-knowledge:
	uv run scripts/build_knowledge.py

parse-code:
	uv run scripts/parse_code.py --project-root $(PROJECT_ROOT)
```

---

## 16. 附录

### 16.1 Vue 2 代码解析要点

由于被解析项目使用 Vue 2 + Element UI，以下是解析时需要重点关注的模式：

**路由解析** (Vue Router 3):

```javascript
// src/router/index.js — 典型结构
import Router from 'vue-router'

const routes = [
  {
    path: '/order',
    component: Layout,
    meta: { title: '订单管理' },    // ← 提取页面名称
    children: [
      {
        path: 'list',
        name: 'OrderList',
        component: () => import('@/views/order/list'),  // ← 提取组件路径
        meta: { title: '订单列表' }
      }
    ]
  }
]
```

**组件提取** (Element UI):

```html
<!-- .vue 文件 template 部分 -->
<template>
  <div>
    <!-- 按钮提取: 文本、事件、权限 -->
    <el-button type="primary" @click="handleCreate" v-permission="['order:create']">
      新建订单
    </el-button>

    <!-- 表单提取: 字段名、类型、校验规则 -->
    <el-form :model="form" :rules="rules">
      <el-form-item label="订单编号" prop="orderNo">
        <el-input v-model="form.orderNo" />
      </el-form-item>
    </el-form>

    <!-- 表格提取: 列定义 -->
    <el-table :data="tableData">
      <el-table-column prop="orderNo" label="订单编号" />
      <el-table-column prop="status" label="状态" />
    </el-table>
  </div>
</template>
```

**API 提取** (Axios):

```javascript
// src/api/order.js — 典型结构
import request from '@/utils/request'

export function createOrder(data) {
  return request({ url: '/api/orders', method: 'post', data })
}

export function getOrderList(params) {
  return request({ url: '/api/orders', method: 'get', params })
}
```

### 16.2 关键第三方库文档

| 库 | 文档地址 | 用途 |
|----|---------|------|
| dingtalk-stream | https://github.com/open-dingtalk/dingtalk-stream-sdk-python | 钉钉 Stream 模式 |
| ChromaDB | https://docs.trychroma.com/ | 向量数据库 |
| LlamaIndex | https://docs.llamaindex.ai/ | RAG 框架 |
| Tree-sitter | https://tree-sitter.github.io/ | AST 解析 |
| FastAPI | https://fastapi.tiangolo.com/ | Web 框架 |
| Ollama API | https://github.com/ollama/ollama/blob/main/docs/api.md | 模型服务 API |

### 16.3 文档变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-15 | 初稿 | - |
