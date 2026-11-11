# 方案 B：日常推 Gitee，自动同步到 GitHub

- Gitee（日常）：`https://gitee.com/git_lixianglong/LangGraph_Agent`
- GitHub（镜像）：`https://github.com/LiXianglong0/LangGraph_Agent`

## 日常使用

```bash
git add .
git commit -m "说明"
git push origin main    # 只推 Gitee
```

## GitHub Secrets（仓库 Settings → Secrets → Actions）

| Name | Value |
|---|---|
| `GITEE_REPO` | `https://gitee.com/git_lixianglong/LangGraph_Agent.git` |
| `GITEE_TOKEN` | Gitee 私人令牌（projects） |
| `GH_PAT` | GitHub classic token（`repo` + `workflow`） |

工作流：`.github/workflows/sync-from-gitee.yml`（每天 08:00 北京时间；也可手动 Run workflow）

注意：不要提交 `.env`；勿把 Token 写进代码或聊天。
