#!/usr/bin/env python3
"""代码解析脚本。

解析 Vue 2 前端项目代码，提取操作知识。

用法:
    uv run scripts/parse_code.py --project-root /path/to/vue-project
    uv run scripts/parse_code.py --project-root /path/to/vue-project --json
    uv run scripts/parse_code.py --project-root /path/to/vue-project --output result.json

依赖:
    - src.parser: Vue 2 代码解析模块
"""

import argparse
import json
import sys
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.parser import KnowledgeBuilder, VueProjectParser
from src.parser.models import ParseResult


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="解析 Vue 2 前端项目代码，提取操作知识",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --project-root ./frontend
  %(prog)s --project-root ./frontend --json
  %(prog)s --project-root ./frontend --output result.json
        """,
    )

    parser.add_argument(
        "--project-root",
        type=str,
        required=True,
        help="前端项目根目录路径",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出解析结果",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="将解析结果保存到文件",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志",
    )

    return parser.parse_args()


def print_stats(result: ParseResult) -> None:
    """打印解析统计信息"""
    print("\n" + "=" * 60)
    print("📊 代码解析统计")
    print("=" * 60)

    print(f"\n📁 路由数量: {len(result.routes)}")
    print(f"📄 页面数量: {len(result.pages)}")
    print(f"🔘 按钮数量: {sum(len(p.buttons) for p in result.pages)}")
    print(f"📝 表单数量: {sum(len(p.forms) for p in result.pages)}")
    print(f"📊 表格数量: {sum(len(p.tables) for p in result.pages)}")
    print(f"💬 弹窗数量: {sum(len(p.dialogs) for p in result.pages)}")
    print(f"📦 Store 模块: {len(result.store_modules)}")
    print(f"🔌 API 接口: {len(result.api_definitions)}")
    print(f"🔄 操作流程: {sum(len(p.operation_flows) for p in result.pages)}")

    # 按页面统计
    if result.pages:
        print("\n📋 页面详情:")
        print("-" * 60)
        for page in result.pages[:10]:  # 最多显示10个页面
            btn_count = len(page.buttons)
            form_count = len(page.forms)
            print(f"  • {page.name or page.path}")
            print(f"    路径: {page.path}")
            print(f"    按钮: {btn_count}, 表单: {form_count}")

        if len(result.pages) > 10:
            print(f"  ... 还有 {len(result.pages) - 10} 个页面")


def print_json(result: ParseResult) -> None:
    """以 JSON 格式输出解析结果"""
    data = {
        "stats": {
            "routes": len(result.routes),
            "pages": len(result.pages),
            "buttons": sum(len(p.buttons) for p in result.pages),
            "forms": sum(len(p.forms) for p in result.pages),
            "tables": sum(len(p.tables) for p in result.pages),
            "dialogs": sum(len(p.dialogs) for p in result.pages),
            "store_modules": len(result.store_modules),
            "api_definitions": len(result.api_definitions),
            "operation_flows": sum(len(p.operation_flows) for p in result.pages),
        },
        "pages": [
            {
                "name": page.name,
                "path": page.path,
                "source_file": page.source_file,
                "buttons": [
                    {
                        "text": btn.text,
                        "event": btn.event,
                        "permission": btn.permission,
                    }
                    for btn in page.buttons
                ],
                "forms": [
                    {
                        "fields": [
                            {"name": f.name, "label": f.label, "type": f.field_type}
                            for f in form.fields
                        ],
                    }
                    for form in page.forms
                ],
            }
            for page in result.pages
        ],
        "routes": [
            {
                "path": route.path,
                "name": route.name,
                "title": route.title,
            }
            for route in result.routes
        ],
    }

    print(json.dumps(data, ensure_ascii=False, indent=2))


def save_output(result: ParseResult, output_path: str) -> None:
    """保存解析结果到文件"""
    data = {
        "stats": {
            "routes": len(result.routes),
            "pages": len(result.pages),
            "buttons": sum(len(p.buttons) for p in result.pages),
            "forms": sum(len(p.forms) for p in result.pages),
        },
        "pages": [
            {
                "name": page.name,
                "path": page.path,
                "source_file": page.source_file,
                "buttons_count": len(page.buttons),
                "forms_count": len(page.forms),
            }
            for page in result.pages
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 解析结果已保存到: {output_path}")


def main() -> int:
    """主函数"""
    args = parse_args()

    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # 验证项目路径
    project_root = Path(args.project_root)
    if not project_root.exists():
        print(f"❌ 项目路径不存在: {project_root}")
        return 1

    if not project_root.is_dir():
        print(f"❌ 路径不是目录: {project_root}")
        return 1

    print(f"\n🔍 开始解析项目: {project_root}")

    try:
        # 创建解析器
        parser = VueProjectParser(project_root=str(project_root))

        # 执行解析
        print("📖 正在解析代码...")
        result = parser.parse()

        # 输出结果
        if args.output:
            save_output(result, args.output)
        elif args.json:
            print_json(result)
        else:
            print_stats(result)

        print("\n" + "=" * 60)
        print("✅ 代码解析完成")
        print("=" * 60)

        return 0

    except Exception as e:
        logger.error("代码解析失败: {}", str(e))
        print(f"\n❌ 代码解析失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
