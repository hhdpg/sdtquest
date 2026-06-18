# Git Push Skill

快速推送代码到 GitHub 仓库。

## 触发条件

当用户说以下类似的话时调用此 skill：
- "推送到 git"
- "push 代码"
- "提交并推送"
- "git push"
- "上传代码"
- "同步到 GitHub"

## 执行步骤

### 1. 检查 Git 状态

```bash
# 检查是否有 git 仓库
git status 2>&1

# 检查是否有未提交的更改
git status --short
```

### 2. 添加和提交文件

如果有未提交的更改：

```bash
# 添加所有更改
git add .

# 自动生成交互消息或询问用户
# 如果有明显的改动模式，自动生成 commit message
# 否则询问用户想要什么 commit message

git commit -m "提交消息"
```

### 3. 检查远程仓库配置

```bash
# 检查是否配置了远程仓库
git remote -v

# 如果没有配置，询问用户仓库地址
# 或者从当前目录名推断
```

### 4. 推送代码

```bash
# 检查分支
git branch --show-current

# 推送到远程
git push -u origin <branch>

# 如果需要认证，提示用户输入 Token
```

### 5. 处理认证问题

如果推送失败（403 错误）：

1. 提示用户检查 Token 权限
2. 引导用户到 https://github.com/settings/tokens 创建 Token
3. Token 需要的权限：`repo` scope
4. 使用临时方式推送：
   ```bash
   git remote set-url origin https://<username>:<token>@github.com/<username>/<repo>.git
   git push -u origin main
   # 推送完成后清除 token
   git remote set-url origin https://github.com/<username>/<repo>.git
   ```

### 6. 验证推送结果

```bash
# 显示最近的提交
git log --oneline -3

# 显示远程仓库信息
git remote -v
```

## 输出格式

推送完成后，显示：

```
✅ 推送成功！

📊 提交信息：
- <commit hash> <commit message>

🌐 仓库地址：
https://github.com/<username>/<repo>
```

## 注意事项

1. **不要存储 Token**：推送完成后立即清除 URL 中的 Token
2. **自动检测分支**：使用当前分支名推送
3. **智能 commit message**：根据改动内容自动生成，或让用户确认
4. **错误处理**：遇到错误时给出清晰的解决建议

## 示例交互

**用户**: "推送到 git"

**Claude**:
```
正在推送代码到 GitHub...

📝 检测到以下更改：
- 新增 3 个文件
- 修改 2 个文件

请确认 commit message 或使用默认的 "feat: 更新代码"

[确认后执行推送]

✅ 推送成功！

📊 提交信息：
- abc1234 feat: 更新代码

🌐 仓库地址：
https://github.com/hhdpg/sdtquest
```
