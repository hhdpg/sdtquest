# 钉钉智能问答机器人

基于本地大模型的 RAG 问答系统,为钉钉群提供智能问答服务。

## 功能特点

- 🤖 **智能问答**: 基于 RAG (检索增强生成) 技术,提供准确的操作指南和问题解答
- 📚 **知识库自动构建**: 自动解析 Vue 2 前端代码,提取操作知识并构建知识库
- 🔍 **混合检索**: 结合 Dense + Sparse 向量检索,提高检索准确率
- 💬 **钉钉集成**: 通过钉钉 Stream 模式实现实时消息收发
- 📊 **统计分析**: 自动统计问题分类,生成日报

## 技术栈

- **后端框架**: FastAPI + Uvicorn
- **LLM 运行时**: Ollama (qwen3.5:9b)
- **Embedding 模型**: bge-m3
- **向量数据库**: ChromaDB
- **代码解析**: Tree-sitter + BeautifulSoup4
- **钉钉 SDK**: dingtalk-stream

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv 安装依赖
make install

# 或者直接使用 uv
uv sync
```

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件,填写钉钉配置
vim .env
```

### 3. 启动 Ollama 服务

```bash
# 确保 Ollama 已安装并运行
ollama serve

# 拉取所需模型
ollama pull qwen3.5:9b
ollama pull bge-m3
```

### 4. 启动应用

```bash
# 开发模式(热重载)
make dev

# 或者生产模式
make run
```

应用将在 `http://localhost:8000` 启动。

## 切换 LLM 供应商（本地 / 远程）

支持本地 Ollama 与远程智谱 GLM 两套模型，可随时切换。

**1. 配置**

```bash
# .env
LLM_PROVIDER=local          # 启动时默认用哪个：local / glm
GLM_API_KEY=your_key_here   # 用 glm 时必填，申请: https://bigmodel.cn
GLM_MODEL=glm-4-flash-250414
```

**免费模型选型（实测 2026-11）**

| 模型 | 能力 | 稳定性 | 结论 |
|---|---|---|---|
| glm-4.7-flash | 30B SOTA，最强 | ❌ 高峰期限流严重（连续 3 次 429）| 作降级备选 |
| glm-4-flash-250414 | 够用 | ✅ 稳定（每次 <2s）| **默认** |
| glm-4.5-flash | 中等 | ❌ 限流严重 | 作降级备选 |
| glm-z1-flash | 推理型 | 输出含 `<think>` 标签 | 不建议 |

已内置 **429 自动降级**：主模型被限流时按 `GLM_FALLBACK_MODELS`
顺序切换，任一成功即返回（实测 0.9 秒内完成降级）。
另默认关闭思考模式（`GLM_THINKING=false`），避免推理过程吃光输出配额。

**2. 两套索引必须分别构建**

两个模型的向量维度与语义空间不同，不能共用一份索引：

```bash
make build-index                 # 本地 bge-m3 → knowledge_base
make build-index provider=glm    # GLM embedding-3 → knowledge_base_glm
make build-index provider=all    # 两份都建
```

**3. 运行时切换（无需重启）**

```bash
curl localhost:8000/api/llm/status                       # 查看当前 provider 与索引条数
curl -X POST localhost:8000/api/llm/switch \
     -H 'Content-Type: application/json' \
     -d '{"provider":"glm"}'                              # 切换
```

切换会同时更换对话模型与配套索引。若目标索引为空会返回 409 并提示先建库，
避免切过去检索不到知识（可加 `"force":true` 强制）。

> 运行时切换只影响当前进程，重启后以 `.env` 的 `LLM_PROVIDER` 为准。

## 项目结构

```
dingtalk-qa-bot/
├── src/                        # 源代码
│   ├── api/                    # API 路由
│   ├── bot/                    # 钉钉机器人模块
│   ├── services/               # 业务服务层
│   ├── domain/                 # 领域模型
│   ├── rag/                    # RAG 检索模块
│   ├── parser/                 # 代码解析模块
│   ├── llm/                    # LLM 服务模块
│   ├── analyzer/               # 问题分析模块
│   ├── infrastructure/         # 基础设施层
│   ├── shared/                 # 公共模块
│   ├── main.py                 # 应用入口
│   └── config.py               # 全局配置
├── scripts/                    # 独立脚本
├── tests/                      # 测试
├── data/                       # 数据目录
└── docs/                       # 文档
```

## 开发指南

### 运行测试

```bash
# 运行所有测试
make test

# 运行单元测试
make test-unit
```

### 代码检查

```bash
# 代码风格检查
make lint

# 代码格式化
make format
```

### 知识库构建

```bash
# 解析前端代码
make parse-code PROJECT_ROOT=/path/to/frontend

# 构建知识库
make build-knowledge
```

## 文档

- [开发任务清单](docs/dev-tasks.md)
- [代码架构设计](docs/code-architecture.md)
- [概要设计文档](docs/design-dingtalk-qa-bot.md)

## 许可证

MIT License
