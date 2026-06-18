#!/usr/bin/env python3
"""验证项目骨架搭建是否完成"""

import sys
from pathlib import Path


def check_file_exists(path: str) -> bool:
    """检查文件是否存在"""
    return Path(path).exists()


def check_dir_exists(path: str) -> bool:
    """检查目录是否存在"""
    return Path(path).is_dir()


def main():
    """主验证函数"""
    print("=" * 60)
    print("🔍 验证项目骨架搭建")
    print("=" * 60)

    checks = []

    # 检查核心文件
    print("\n📄 检查核心文件:")
    core_files = [
        "pyproject.toml",
        "src/main.py",
        "src/config.py",
        "Makefile",
        ".env.example",
        "README.md",
        ".gitignore",
    ]

    for file in core_files:
        exists = check_file_exists(file)
        status = "✅" if exists else "❌"
        print(f"  {status} {file}")
        checks.append(exists)

    # 检查目录结构
    print("\n📁 检查目录结构:")
    required_dirs = [
        "src/api",
        "src/api/routes",
        "src/bot",
        "src/services",
        "src/domain",
        "src/domain/models",
        "src/rag",
        "src/parser",
        "src/llm",
        "src/llm/prompts",
        "src/analyzer",
        "src/infrastructure",
        "src/infrastructure/repositories",
        "src/infrastructure/external",
        "src/shared",
        "scripts",
        "tests",
        "tests/unit",
        "tests/integration",
        "data",
    ]

    for dir_path in required_dirs:
        exists = check_dir_exists(dir_path)
        status = "✅" if exists else "❌"
        print(f"  {status} {dir_path}/")
        checks.append(exists)

    # 检查 __init__.py 文件
    print("\n📦 检查 Python 包初始化文件:")
    init_files = [
        "src/__init__.py",
        "src/api/__init__.py",
        "src/bot/__init__.py",
        "src/services/__init__.py",
        "src/domain/__init__.py",
        "src/rag/__init__.py",
        "src/parser/__init__.py",
        "src/llm/__init__.py",
        "src/analyzer/__init__.py",
        "src/infrastructure/__init__.py",
        "src/shared/__init__.py",
    ]

    for init_file in init_files:
        exists = check_file_exists(init_file)
        status = "✅" if exists else "❌"
        print(f"  {status} {init_file}")
        checks.append(exists)

    # 检查配置文件内容
    print("\n⚙️  检查配置文件内容:")

    # 检查 pyproject.toml 是否包含关键依赖
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        content = pyproject_path.read_text()
        has_fastapi = "fastapi" in content
        has_chromadb = "chromadb" in content
        has_httpx = "httpx" in content
        has_pydantic = "pydantic" in content

        print(f"  {'✅' if has_fastapi else '❌'} pyproject.toml 包含 fastapi")
        print(f"  {'✅' if has_chromadb else '❌'} pyproject.toml 包含 chromadb")
        print(f"  {'✅' if has_httpx else '❌'} pyproject.toml 包含 httpx")
        print(f"  {'✅' if has_pydantic else '❌'} pyproject.toml 包含 pydantic")

        checks.extend([has_fastapi, has_chromadb, has_httpx, has_pydantic])

    # 检查 config.py 是否包含 Settings 类
    config_path = Path("src/config.py")
    if config_path.exists():
        content = config_path.read_text()
        has_settings = "class Settings" in content
        has_settings_instance = "settings = Settings()" in content

        print(f"  {'✅' if has_settings else '❌'} config.py 包含 Settings 类")
        print(f"  {'✅' if has_settings_instance else '❌'} config.py 包含 settings 实例")

        checks.extend([has_settings, has_settings_instance])

    # 检查 main.py 是否包含 FastAPI 应用
    main_path = Path("src/main.py")
    if main_path.exists():
        content = main_path.read_text()
        has_fastapi_app = "FastAPI" in content
        has_create_app = "def create_app" in content

        print(f"  {'✅' if has_fastapi_app else '❌'} main.py 包含 FastAPI 应用")
        print(f"  {'✅' if has_create_app else '❌'} main.py 包含 create_app 函数")

        checks.extend([has_fastapi_app, has_create_app])

    # 总结
    print("\n" + "=" * 60)
    total_checks = len(checks)
    passed_checks = sum(checks)
    failed_checks = total_checks - passed_checks

    print(f"📊 验证结果:")
    print(f"  总检查项: {total_checks}")
    print(f"  通过: {passed_checks}")
    print(f"  失败: {failed_checks}")

    if all(checks):
        print("\n✅ 所有检查通过!项目骨架搭建完成!")
        print("=" * 60)
        return 0
    else:
        print("\n❌ 部分检查未通过,请检查上述失败项!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
