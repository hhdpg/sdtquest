# 钉钉智能问答机器人 — 开发任务列表

> **版本**: v1.0  
> **日期**: 2026-06-15  
> **关联文档**: 概要设计文档、代码架构设计文档

---

## 〇、进度总览

> **状态说明**: ✅ 已完成 | 🔄 进行中 | ⏳ 被阻塞 | 🔲 可开始 | ❌ 取消

| # | 任务名称 | 状态 | 阻塞依赖 | 预估 | 备注 |
|---|---------|------|---------|------|------|
| 1 | 项目初始化与骨架搭建 | ✅ | 无 | 0.5天 | 已完成 |
| 2 | Domain 层 — 模型/枚举/接口/异常 | ✅ | #1 | 1天 | 已完成 |
| 3 | LLM 模块 — Ollama 客户端 + Prompt | ✅ | #2 | 1-2天 | 已完成 |
| 4 | RAG 模块 — Embedding + 检索 + 上下文 | ✅ | #2, #3 | 2-3天 | 已完成 |
| 5 | Parser 模块 — Vue 2 代码解析器 | ✅ | #2 | 3-4天 | 已完成 |
| 6 | Infrastructure 层 — SQLite + Repository | ✅ | #2 | 1-2天 | 已完成 |
| 7 | Services 层 — QA/知识库/分析服务 | ✅ | #3,#4,#5,#6 | 2天 | 已完成（通过 Protocol 可选注入 Parser/Analyzer） |
| 8 | Bot 模块 — 钉钉 Stream 消息收发 | ✅ | #7 | 2-3天 | 已完成（含会话管理/消息处理器/发送器/Stream连接） |
| 9 | Analyzer 模块 — 分类/汇总/日报 | 🔲 | #2, #6 | 1-2天 | |
| 10 | API 层 — FastAPI 路由 + 启动入口 | ✅ | #7, #8 | 1天 | 已完成（含 FastAPI 应用/依赖注入/4个路由模块/完整启动入口） |
| 11 | 脚本开发 — 知识库构建/导入脚本 | 🔲 | #4, #5, #6 | 1天 | |
| 12 | 测试 — 单元测试 + 集成测试 | 🔲 | #7 | 2天 | |
| 13 | 端到端联调 — 钉钉群实测 | 🔲 | #8,#10,#11,#12 | 2-3天 | |

**总进度**: 9/13 完成 · 0 进行中 · 0 被阻塞 · 4 可开始 · 0 取消  
**总计预估**: 15-20 个工作日

> 开发时按状态列更新：完成的任务改为 ✅，开始做的改为 🔄，被阻塞的保持 ⏳，可以开始但还没做的保持 🔲

---

## 一、依赖关系图

```
#1 项目骨架
 │
 └→ #2 Domain 层 (模型/接口)
     │
     ├→ #3 LLM 模块 ─────────────┐
     │                            │
     ├→ #5 Parser 模块 ──┐        │
     │                   │        │
     └→ #6 基础设施层 ───┤        │
         │               │        │
         │    #4 RAG 模块 ←─ #3   │
         │    (依赖 #2, #3)       │
         │               │        │
         └─── #9 Analyzer        │
              (依赖 #2, #6)       │
              │                   │
              ├───────────────────┘
              │
              ▼
         #7 Services 层 (汇总 #3 #4 #5 #6)
          │
          ├──→ #8 Bot 模块 ──────────┐
          │                          │
          ├──→ #10 API + 启动入口 ←──┘
          │
          └──→ #12 测试
          
     #11 脚本 (依赖 #4 #5 #6)
     
         全部就绪 → #13 端到端联调
```

---

## 二、分批开发节奏

| 批次 | 任务 | 可并行的任务 | 预估时间 | 状态 |
|------|------|-------------|---------|------|
| **第一批** | #1 项目骨架 → #2 Domain 层 | 无，串行 | 1-2 天 | ✅ ✅ |
| **第二批** | #3 LLM + #5 Parser + #6 基础设施 | #3、#5、#6 三个可并行 | 3-4 天 | ✅ ✅ ✅ |
| **第三批** | #4 RAG 模块 | 等 #3 完成后开始 | 2-3 天 | ✅ |
| **第四批** | #7 Services 层 | 等 #3 #4 #5 #6 全完成 | 2 天 | ✅ (通过可选注入解除 #5 阻塞) |
| **第五批** | #8 Bot + #9 Analyzer + #10 API + #11 脚本 | 部分可并行 | 3-4 天 | ✅ 🔲 ✅ 🔲 |
| **第六批** | #12 测试 | 与第五批同步进行 | 2 天 | 🔲 |
| **第七批** | #13 端到端联调 | 全部完成后 | 2-3 天 | 🔲 |

**总计预估：15-20 个工作日**

---

## 三、任务详情

### ✅ #1 项目初始化与骨架搭建

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | 无 |
| **预估时间** | 0.5 天 |
| **交付路径** | `pyproject.toml`, `src/main.py`, `src/config.py`, `Makefile`, `.env.example` |

**任务内容**：
- 创建 `pyproject.toml`，声明所有依赖（fastapi, uvicorn, dingtalk-stream, chromadb, llama-index, tree-sitter, httpx, pydantic, loguru 等）
- 创建完整目录结构（src/api, src/bot, src/services, src/domain, src/rag, src/parser, src/llm, src/analyzer, src/infrastructure, src/shared, scripts, tests, data）
- 实现 `src/config.py` — Pydantic Settings 全局配置类
- 实现 `src/main.py` — 最小启动入口（FastAPI app 创建）
- 创建 `Makefile` — install, dev, run, test, lint 等常用命令
- 创建 `.env.example` — 环境变量示例
- 创建 `README.md` — 项目说明和快速启动指南
- 验证：`uv sync` 安装依赖成功，`uv run uvicorn` 启动不报错

---

### ✅ #2 Domain 层 — 模型、枚举、接口、异常定义

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #1 |
| **预估时间** | 1 天 |
| **交付路径** | `src/domain/` |

**任务内容**：

**模型定义** (`src/domain/models/`):
- `question.py` — Question 模型（id, text, sender_id, conversation_id, category, created_at）
- `answer.py` — Answer 模型（id, question_id, text, sources, confidence, category, created_at）
- `knowledge.py` — KnowledgeItem 模型（id, type, title, content, page_name, page_path, source_file, tags）
- `conversation.py` — Conversation、Message 模型

**枚举定义** (`src/domain/enums.py`):
- `QuestionCategory` — operation_guide / process_inquiry / anomaly_troubleshoot / general
- `KnowledgeType` — page / button / form / workflow / api / manual
- `AnswerStatus` — success / no_match / error / timeout

**端口接口** (`src/domain/ports.py`):
- `LLMClient` — generate(), embed(), generate_stream()
- `VectorStore` — add(), search(), delete()
- `QuestionRepository` — save(), find_recent(), count_by_category()
- `MessageSender` — send_text(), send_markdown(), update_message()

**异常定义** (`src/domain/exceptions.py`):
- AppException（基类）、QuestionProcessingError、KnowledgeNotFoundError
- LLMServiceError、VectorStoreError、DingTalkAPIError、ParserError

**约束**: 此模块不 import 任何其他 src/ 下的模块，纯 Python + Pydantic。

---

### ✅ #3 LLM 模块 — Ollama 客户端 + Prompt 模板

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #2 |
| **预估时间** | 1-2 天 |
| **交付路径** | `src/llm/` |

**任务内容**：

**Ollama 客户端** (`src/llm/client.py`):
- OllamaClient 类，实现 domain/ports.py 中的 LLMClient 接口
- 使用 httpx 异步调用 Ollama API（/api/generate、/api/embed）
- 支持超时控制（默认 120s）
- 支持并发限制（asyncio.Semaphore，默认 max_concurrent=2）
- 支持流式生成（generate_stream）
- 错误处理：连接失败、超时、模型未加载等场景

**Prompt 模板管理** (`src/llm/templates.py`):
- 模板加载器，从 prompts/ 目录加载 .txt 或 .py 模板
- 支持变量替换

**Prompt 模板文件** (`src/llm/prompts/`):
- `qa.py` — 问答场景 Prompt（系统提示词 + 知识上下文 + 对话历史 + 用户问题）
- `enrichment.py` — 知识丰富 Prompt（读代码片段生成通俗描述）
- `classify.py` — 问题分类 Prompt

**验证**: 本地启动 Ollama，调用 generate() 和 embed() 返回正常结果。

---

### ✅ #4 RAG 模块 — Embedding + ChromaDB + 混合检索 + 上下文组装

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #2, #3 |
| **预估时间** | 2-3 天 |
| **交付路径** | `src/rag/` |

**任务内容**：

**Embedding 服务** (`src/rag/embedding.py`):
- EmbeddingService 类，封装 bge-m3 向量化
- 调用 OllamaClient.embed()，支持批量编码
- 支持查询时添加 instruction prefix（bge-m3 要求）

**ChromaDB 封装** (`src/rag/vectorstore.py`):
- ChromaVectorStore 类，实现 domain/ports.py 中的 VectorStore 接口
- 支持：添加文档、删除文档、按向量检索、按元数据过滤
- 持久化到 data/chroma_db/
- Collection 管理（创建、获取）

**混合检索器** (`src/rag/retriever.py`):
- HybridRetriever 类
- 实现 bge-m3 Dense 检索（语义匹配）
- 实现 bge-m3 Sparse 检索（关键词匹配）
- RRF (Reciprocal Rank Fusion) 融合排序
- 根据问题类型切换阈值（标准类 >0.8，灵活类 >0.6）

**上下文组装** (`src/rag/context.py`):
- ContextAssembler 类
- 将检索到的知识文档 + 对话历史 + 问题类型 → 组装为最终 Prompt
- 标准操作类和灵活推理类使用不同的 Prompt 模板

**RAG 主流程** (`src/rag/pipeline.py`):
- RAGPipeline 类，编排完整检索流程
- 输入 Question → 输出 RAGResult（检索到的文档 + 组装好的 Prompt）

---

### ✅ #5 Parser 模块 — Vue 2 代码解析器（路由/组件/Store/API）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #2 |
| **预估时间** | 3-4 天 |
| **交付路径** | `src/parser/` |

**任务内容**：

**路由解析** (`src/parser/router_parser.py`):
- 解析 Vue Router 3 配置文件（src/router/index.js）
- 提取：路由路径、页面名称（meta.title）、组件路径、嵌套关系
- 构建页面层级树

**组件解析** (`src/parser/component_parser.py`):
- 解析 .vue 文件的 `<template>` 部分
- 提取 Element UI 组件：
  - `el-button` — 按钮文本、@click 事件、v-permission 权限
  - `el-form` + `el-form-item` — 表单字段名、标签、校验规则
  - `el-table` + `el-table-column` — 表格列定义
  - `el-dialog` — 弹窗内容和触发条件

**Vuex Store 解析** (`src/parser/store_parser.py`):
- 解析 src/store/ 下的 modules
- 提取：actions、mutations、state 字段
- 关联页面组件中的 dispatch/commit 调用

**API 解析** (`src/parser/api_parser.py`):
- 解析 src/api/ 下的接口定义文件
- 提取：函数名、请求路径、HTTP 方法、参数
- 关联页面组件中的 API 调用

**Vue SFC 解析入口** (`src/parser/vue_parser.py`):
- VueSFCParser 类，解析单个 .vue 文件
- 拆分 `<template>`、`<script>`、`<style>` 三部分
- 串联上述各解析器

**知识构建器** (`src/parser/builder.py`):
- KnowledgeBuilder 类
- 将解析结果转换为 KnowledgeItem 列表
- 按页面组织知识（同一页面的按钮/表单/表格合并为一个文档）
- 支持调用 LLM 丰富描述（可选）

**测试 Fixture**:
- 创建 `tests/fixtures/sample_vue_project/` — 模拟一个小型 Vue 2 项目
- 包含路由配置、几个页面组件、Store、API 文件
- 用于解析器单元测试

---

### ✅ #6 Infrastructure 层 — SQLite + Repository + 钉钉 API 客户端

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #2 |
| **预估时间** | 1-2 天 |
| **交付路径** | `src/infrastructure/` |

**任务内容**：

**数据库管理** (`src/infrastructure/database.py`):
- SQLite 连接管理（单例模式）
- 表初始化：question_records、daily_summary
- 索引创建

**Repository 实现** (`src/infrastructure/repositories/`):
- `question_repo.py` — SQLiteQuestionRepository，实现 QuestionRepository 接口
  - save(): 保存问答记录
  - find_recent(): 查询最近 N 天的记录
  - count_by_category(): 按分类统计
  - find_unanswered(): 查询未回答的问题
  - get_top_questions(): 查询高频问题
- `knowledge_repo.py` — KnowledgeRepository，知识条目 CRUD

**钉钉 API 客户端** (`src/infrastructure/external/dingtalk_client.py`):
- DingTalkClient 类
- 封装钉钉开放平台 API：发送消息、更新消息、获取群信息
- 错误处理和重试

---

### ✅ #7 Services 层 — QA 问答服务 + 知识库管理 + 分析汇总

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #3, #4, #5, #6（#5 通过 Protocol 可选注入解除阻塞） |
| **预估时间** | 2 天 |
| **交付路径** | `src/services/` |

**任务内容**：

**问答服务** (`src/services/qa_service.py`):
- QAService 类 — 核心业务编排
- ask() 方法完整流程：
  1. 问题验证（空值/超长校验）
  2. 获取会话上下文（通过可选 SessionManager Protocol）
  3. 问题分类（通过可选 Classifier Protocol）
  4. RAG 检索（RAGPipeline）
  5. Prompt 组装（内置于 RAG 管道的 ContextAssembler）
  6. LLM 生成（OllamaClient）
  7. 回答后处理（去 <think> 标签、统一编号格式）
  8. 记录问答日志（QuestionRepository）
- 标准操作类：temperature=0.3，阈值>0.8
- 灵活推理类：temperature=0.7，阈值>0.6
- 容错设计：KnowledgeNotFoundError 生成友好提示、LLM 异常兜底返回 ERROR 状态答案
- 置信度计算：基于检索文档数量和分类动态调整

**知识库管理服务** (`src/services/knowledge_service.py`):
- KnowledgeService 类
- build_from_code(): 调用 Parser 解析结果 → LLM 丰富（build_enrichment_prompt） → 向量化（EmbeddingService） → 写入 ChromaDB + SQLite
- import_document(): 导入手动文档
- import_from_file(): 从 Markdown/纯文本文件导入，支持自动分块
- import_from_directory(): 批量导入目录
- get_stats(): 知识库统计（合并向量库 + SQLite）
- get_knowledge_items() / delete_knowledge() / get_pages(): 完整 CRUD
- _split_content(): 长文档按段落/句号自动分块

**分析汇总服务** (`src/services/analytics_service.py`):
- AnalyticsService 类
- get_summary(): 问题分类统计 + 平均置信度 + 成功率
- get_top_questions(): 高频问题 TOP N
- get_unanswered(): 知识库盲区分析
- generate_daily_report(): 生成 Markdown 格式日报/周报
- save_daily_summary(): 持久化到 daily_summary 表

**模块导出** (`src/services/__init__.py`):
- 导出 QAService、KnowledgeService、AnalyticsService 及对应异常类

**设计说明**：
- 通过 Protocol 定义 Classifier、SessionManager 可选依赖，不硬依赖尚未完成的 parser/ 和 analyzer/ 模块
- Bot 模块完成后可注入 SessionManager，Analyzer 模块完成后可注入 Classifier，无缝集成

---

### ✅ #8 Bot 模块 — 钉钉 Stream 消息收发 + 会话管理

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #7 |
| **预估时间** | 2-3 天 |
| **交付路径** | `src/bot/` |

**任务内容**：

**Stream 连接管理** (`src/bot/router.py`):
- BotRouter 类
- ✅ 初始化 dingtalk-stream 客户端
- ✅ 自动重连机制（指数退避策略，最大延迟 300s）
- ✅ 注册消息回调
- ✅ 优雅关闭

**消息处理器** (`src/bot/handler.py`):
- BotHandler 类
- ✅ 检测 @提及
- ✅ 提取问题文本（去除 @部分）
- ✅ 去重检查（消息 ID，保留最近 1000 条）
- ✅ 限流检查（同一用户 60 秒内限流）
- ✅ 异步调用 QAService
- ✅ 即时回复 "正在思考..." 反馈
- ✅ 异常兜底（LLM 错误/处理错误/未知错误分级处理）
- ✅ 会话历史自动维护

**消息发送** (`src/bot/sender.py`):
- DingTalkMessageSender 类，实现 domain/ports.py 中的 MessageSender 接口
- ✅ send_text(): 发送纯文本
- ✅ send_markdown(): 发送 Markdown 格式
- ✅ update_message(): 更新已发送消息（支持撤回重发回退）
- ✅ send_thinking_hint(): 即时反馈
- ✅ send_error_message(): 错误提示
- ✅ 消息注册表（维护 message_id 到会话的映射）

**会话管理** (`src/bot/session.py`):
- SessionManager 类
- ✅ 维护每个会话的对话历史（最近 N 轮）
- ✅ LRU 淘汰过期会话（可配置 max_sessions）
- ✅ TTL 过期（默认 5 分钟）
- ✅ 线程安全（threading.Lock）
- ✅ 消息溢出保护（超过 max_history*2 时自动截断）
- ✅ 统计接口（get_stats）

**模块导出** (`src/bot/__init__.py`):
- ✅ 导出 BotRouter、BotHandler、DingTalkMessageSender、SessionManager

**测试** (`tests/unit/test_bot/`):
- ✅ 73 个单元测试全部通过
- ✅ 覆盖: session(17)、sender(14)、handler(26)、router(12)、模块导出(4)
- ✅ 全部 144 个测试无回归

**设计说明**：
- SessionManager 实现 qa_service.py 中定义的 SessionManager Protocol，可直接注入 QAService
- DingTalkMessageSender 实现 domain/ports.py 中的 MessageSender Protocol
- BotHandler 支持完整容错: 即使 "思考中" 提示发送失败也不影响主回答流程
- BotRouter 重连策略: 指数退避（base_delay * 2^count，最大 300s），可配置最大重试次数

---

### ⏳ #9 Analyzer 模块 — 问题分类 + 统计汇总 + 日报生成

| 属性 | 值 |
|------|-----|
| **状态** | ⏳ 被阻塞 (等待 #2, #6) |
| **阻塞依赖** | #2, #6 |
| **预估时间** | 1-2 天 |
| **交付路径** | `src/analyzer/` |

**任务内容**：

**问题分类器** (`src/analyzer/classifier.py`):
- QuestionClassifier 类
- 初始实现：规则 + 关键词匹配
  - 操作指南：包含 "怎么" "如何" "在哪里" "步骤"
  - 流程咨询：包含 "流程" "审批" "步骤" "先后"
  - 异常排查：包含 "报错" "失败" "为什么" "不了"
  - 其他：不匹配以上规则
- 预留 ML 分类器接口（后续可替换为 SVM/TextCNN）

**问题汇总** (`src/analyzer/summarizer.py`):
- QuestionSummarizer 类
- 按天/周统计各分类数量
- 提取高频问题 TOP N
- 标记未回答问题

**报告生成** (`src/analyzer/reporter.py`):
- ReportGenerator 类
- 生成 Markdown 格式日报
- 支持推送到钉钉管理群（调用 DingTalkClient）
- 配合 APScheduler 实现每日凌晨自动执行

---

### ✅ #10 API 层 — FastAPI 路由 + 应用启动入口

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **阻塞依赖** | #7, #8 |
| **预估时间** | 1 天 |
| **交付路径** | `src/api/`, `src/main.py` |

**任务内容**：

**FastAPI 应用** (`src/api/app.py`):
- ✅ 创建 FastAPI 实例
- ✅ 注册所有路由
- ✅ 全局异常处理（捕获 AppException，返回统一错误格式）
- ✅ CORS 配置
- ✅ 请求日志中间件

**依赖注入** (`src/api/deps.py`):
- ✅ 从 app.state 获取 service 实例
- ✅ 提供 get_qa_service()、get_knowledge_service()、get_analytics_service() 等依赖函数

**API 路由** (`src/api/routes/`):
- ✅ `health.py` — GET /health 健康检查、GET /health/detailed 详细健康检查
- ✅ `chat.py` — POST /api/chat 调试用对话接口、POST /api/chat/simple 简化接口
- ✅ `knowledge.py` — POST /api/knowledge/build 触发构建、GET /api/knowledge/stats 统计、GET /api/knowledge/items 查询、DELETE /api/knowledge/items/{item_id} 删除、POST /api/knowledge/import 导入
- ✅ `analytics.py` — GET /api/analytics/summary 统计摘要、GET /api/analytics/top-questions 高频问题、GET /api/analytics/unanswered 未回答问题、GET /api/analytics/report 生成报告、POST /api/analytics/report/save 保存报告

**应用启动入口** (`src/main.py`):
- ✅ 完善启动逻辑：
  1. ✅ 加载配置
  2. ✅ 初始化基础设施（SQLite、ChromaDB）
  3. ✅ 创建服务实例（QAService、KnowledgeService、AnalyticsService）
  4. ✅ 启动 FastAPI（uvicorn）
  5. ✅ 启动 DingTalk Stream（异步任务）
  6. ✅ 注册定时任务（每日汇总）

**交付清单**:
- `src/api/app.py` — FastAPI 应用工厂（创建应用、配置CORS、异常处理、路由注册）
- `src/api/deps.py` — 依赖注入函数（从 app.state 获取服务实例）
- `src/api/routes/health.py` — 健康检查路由（2个接口）
- `src/api/routes/chat.py` — 对话路由（2个接口）
- `src/api/routes/knowledge.py` — 知识库路由（6个接口）
- `src/api/routes/analytics.py` — 统计分析路由（5个接口）
- `src/main.py` — 应用启动入口（完整的生命周期管理）

**测试验证**:
- ✅ 所有模块导入成功
- ✅ FastAPI 应用创建成功
- ✅ 15个API路由正确注册
- ✅ 144个单元测试全部通过（无回归）

---

### ⏳ #11 脚本开发 — 知识库构建 + 文档导入 + 分类器种子数据

| 属性 | 值 |
|------|-----|
| **状态** | ⏳ 被阻塞 (等待 #4, #5, #6) |
| **阻塞依赖** | #4, #5, #6 |
| **预估时间** | 1 天 |
| **交付路径** | `scripts/` |

**任务内容**：

**代码解析脚本** (`scripts/parse_code.py`):
- 命令行参数：--project-root（前端项目路径）
- 调用 Parser 模块解析代码
- 输出解析结果统计（页面数、按钮数、表单数等）
- 可选输出 JSON 格式的解析详情

**知识库构建脚本** (`scripts/build_knowledge.py`):
- 命令行参数：--project-root, --enrich（是否用 LLM 丰富描述）
- 完整流程：解析代码 → LLM 丰富 → 向量化 → 写入 ChromaDB
- 支持全量构建和增量构建（--incremental）
- 输出构建统计

**手动文档导入脚本** (`scripts/import_docs.py`):
- 命令行参数：--file（文件路径）或 --dir（目录路径）
- 支持 Markdown、纯文本文件
- 自动分块、向量化、入库

**分类器种子数据脚本** (`scripts/seed_classifier.py`):
- 预置一批分类样本数据（每类 20-30 条）
- 写入 SQLite 供分类器使用

---

### ⏳ #12 测试 — 单元测试 + 集成测试 + 覆盖率

| 属性 | 值 |
|------|-----|
| **状态** | ⏳ 被阻塞 (等待 #7) |
| **阻塞依赖** | #7 |
| **预估时间** | 2 天 |
| **交付路径** | `tests/` |

**任务内容**：

**全局 Fixture** (`tests/conftest.py`):
- Mock Ollama（返回预设回答）
- Mock 钉钉 API
- 临时 ChromaDB 目录（测试后自动清理）
- 内存 SQLite（`:memory:` 模式）
- sample_vue_project fixture 路径

**单元测试** (`tests/unit/`):
- `test_parser/` — 路由解析、组件解析、Store 解析、API 解析
- `test_rag/` — 混合检索、RRF 排序、上下文组装
- `test_llm/` — OllamaClient（mock HTTP）
- `test_services/` — QAService 编排逻辑（mock 所有依赖）

**集成测试** (`tests/integration/`):
- `test_qa_pipeline.py` — 完整问答流程（真实 ChromaDB + mock Ollama）
- `test_knowledge_build.py` — 代码解析 → 知识库构建

**覆盖率目标**:
- domain/ >90%
- services/ >80%
- rag/、parser/ >70%
- infrastructure/ >50%

---

### ⏳ #13 端到端联调 — 钉钉群实测 + 知识库验证 + 问题修复

| 属性 | 值 |
|------|-----|
| **状态** | ⏳ 被阻塞 (等待 #8, #10, #11, #12) |
| **阻塞依赖** | #8, #10, #11, #12 |
| **预估时间** | 2-3 天 |
| **交付路径** | 全链路 |

**任务内容**：

**环境准备**:
- 在钉钉开放平台创建应用，配置机器人，获取 AppKey/AppSecret
- 确保 Ollama 运行，模型已拉取（qwen3.5:35b-a3b-instruct-4bit, bge-m3）
- 准备实际前端代码路径

**知识库构建**:
- 用实际前端代码运行 build_knowledge.py
- 验证解析结果质量（页面数、按钮数是否合理）
- 手动检查部分知识条目的描述质量

**端到端验证**:
- 启动完整服务（Ollama + FastAPI + DingTalk Stream）
- 在钉钉群里 @机器人 提问，验证：
  - 能收到 "正在思考..." 即时反馈
  - 最终回答内容正确、格式清晰
  - 操作指南类问题能匹配到正确知识
  - 灵活推理类问题能合理回答
  - 超出知识库范围的问题能诚实告知

**性能验证**:
- 平均响应时间 <30s
- 并发 2-3 个用户同时提问不崩溃
- 内存使用不超 24GB

**问题修复**:
- 修复联调中发现的 bug
- 优化 Prompt 和检索策略
- 补充缺失的知识条目

---

## 四、文档变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-06-15 | 初稿，创建 13 个开发任务 |
