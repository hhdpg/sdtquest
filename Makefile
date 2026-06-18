# Makefile for dingtalk-qa-bot

.PHONY: install run dev test lint format build-knowledge parse-code clean

# 安装依赖
install:
	uv sync

# 开发模式运行(热重载)
dev:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式运行
run:
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# 运行所有测试
test:
	uv run pytest tests/ -v --cov=src

# 运行单元测试
test-unit:
	uv run pytest tests/unit/ -v

# 代码检查
lint:
	uv run ruff check src/
	uv run mypy src/

# 代码格式化
format:
	uv run ruff format src/ tests/

# 构建知识库
build-knowledge:
	uv run scripts/build_knowledge.py

# 解析代码
parse-code:
	uv run scripts/parse_code.py --project-root $(PROJECT_ROOT)

# 清理临时文件
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
