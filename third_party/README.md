# third_party

本目录用于放入同仓编排依赖。

## RAGFlow

不要手工改业务代码集成；通过脚本拉取官方仓库：

```bash
./deploy/bootstrap-ragflow.sh
```

将克隆到 `third_party/ragflow`（默认 tag：`v1.0.0-rc2`），并生成 `deploy/ragflow.env`。

也可用 Git Submodule（可选）：

```bash
git submodule add -b v1.0.0-rc2 https://github.com/infiniflow/ragflow.git third_party/ragflow
./deploy/bootstrap-ragflow.sh   # 若已存在则跳过克隆，仍会生成 ragflow.env
```
