#!/bin/bash
# Git 快速推送脚本
# 用法: ./scripts/git-push.sh [commit message]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否在 git 仓库中
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo -e "${RED}❌ 错误: 当前目录不是 git 仓库${NC}"
    exit 1
fi

# 获取仓库信息
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE_URL" ]; then
    echo -e "${RED}❌ 错误: 没有配置远程仓库${NC}"
    echo "请先添加远程仓库: git remote add origin <url>"
    exit 1
fi

# 检查是否有更改
CHANGES=$(git status --short)
if [ -z "$CHANGES" ]; then
    echo -e "${YELLOW}📝 没有检测到更改${NC}"

    # 即使没有更改也允许推送
    read -p "是否仍然推送？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
else
    echo -e "${GREEN}📝 检测到以下更改:${NC}"
    echo "$CHANGES"
    echo ""

    # 生成 commit message
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        # 自动统计更改
        ADDED=$(echo "$CHANGES" | grep "^??" | wc -l | tr -d ' ')
        MODIFIED=$(echo "$CHANGES" | grep "^ M\|^M " | wc -l | tr -d ' ')
        DELETED=$(echo "$CHANGES" | grep "^ D\|^D " | wc -l | tr -d ' ')

        AUTO_MSG="update:"
        [ "$ADDED" -gt 0 ] && AUTO_MSG="$AUTO_MSG 新增 $ADDED 个文件"
        [ "$MODIFIED" -gt 0 ] && AUTO_MSG="$AUTO_MSG 修改 $MODIFIED 个文件"
        [ "$DELETED" -gt 0 ] && AUTO_MSG="$AUTO_MSG 删除 $DELETED 个文件"

        echo -e "${YELLOW}建议的 commit message: $AUTO_MSG${NC}"
        read -p "请输入 commit message (回车使用建议): " INPUT_MSG
        COMMIT_MSG="${INPUT_MSG:-$AUTO_MSG}"
    fi

    # 添加和提交
    echo ""
    echo "📦 添加文件..."
    git add .

    echo "💾 提交更改..."
    git commit -m "$COMMIT_MSG"
fi

# 获取当前分支
BRANCH=$(git branch --show-current)
echo ""
echo "🚀 推送到 origin/$BRANCH..."

# 尝试推送
if git push -u origin "$BRANCH" 2>&1; then
    echo ""
    echo -e "${GREEN}✅ 推送成功！${NC}"
    echo ""
    echo "📊 最近提交:"
    git log --oneline -3
    echo ""
    echo "🌐 仓库地址:"
    # 从 URL 提取干净的地址
    CLEAN_URL=$(echo "$REMOTE_URL" | sed 's/.*@//' | sed 's/\.git$//' | sed 's|https://[^@]*@|https://|')
    echo "https://$CLEAN_URL" | sed 's|https://https://|https://|'
else
    echo ""
    echo -e "${RED}❌ 推送失败${NC}"
    echo ""
    echo "可能的原因和解决方案:"
    echo "1. Token 权限不足 - 请检查 Token 是否有 repo scope"
    echo "2. Token 已过期 - 请到 https://github.com/settings/tokens 重新创建"
    echo "3. 网络问题 - 请检查网络连接"
    echo ""
    echo "手动推送命令:"
    echo "  git remote set-url origin https://<username>:<token>@github.com/<username>/<repo>.git"
    echo "  git push -u origin $BRANCH"
    echo "  git remote set-url origin https://github.com/<username>/<repo>.git  # 清除 token"
    exit 1
fi
