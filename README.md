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
- **LLM 运行时**: Ollama (qwen3.5:35b-a3b-instruct-4bit)
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
ollama pull qwen3.5:35b-a3b-instruct-4bit
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
