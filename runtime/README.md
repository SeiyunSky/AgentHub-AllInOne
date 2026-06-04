# AgentHub Runtime Image

`agenthub-runtime:python3.11` —— AgentHub 部署 Python 应用时使用的运行时容器镜像。

## 用途

主 Agent 调用 `deploy_app` 工具时,后端的 `DockerRuntimeService` 用此镜像起一个会话级容器:
- 沙箱目录(`sandbox/{conv_id}/`)挂载到容器 `/app`
- 容器内跑 Agent 写的 FastAPI / Flask 应用,监听 `0.0.0.0:8000`
- AgentHub 后端通过 `/preview/{conv_id}/` 反向代理转发请求到容器

## 预装依赖

镜像里**只**有这些库可用,Agent 写代码必须遵守。完整清单见
`backend/skills/python_runtime_environment.md`。

| 类别 | 库 |
|------|---|
| Web | fastapi 0.115 / uvicorn / flask 3 / jinja2 / aiofiles / python-multipart |
| HTTP | httpx / requests |
| DB | sqlalchemy 2 / aiosqlite (sqlite only) |
| 数据 | pandas 2.2 / numpy 2 / matplotlib 3.9 |
| 其他 | pydantic 2 / pydantic-settings / python-dotenv |

## 构建

```bash
docker build -t agenthub-runtime:python3.11 runtime/
```

AgentHub 启动时会自动 `ensure_image()`(镜像不存在则自动 build),不需要手动构建。

## 验证

```bash
docker run --rm agenthub-runtime:python3.11 python -c "import fastapi, pandas, sqlalchemy, matplotlib; print('ok')"
```

应该输出 `ok`。

## 改动注意

**任何依赖版本变化必须同步改 `backend/skills/python_runtime_environment.md`**,
否则 Agent 看到的版本和容器实际版本错位,部署会出诡异 bug。

镜像层数和大小:
- 目标镜像大小 < 500MB
- 改 Dockerfile 时尽量用 `&& \` 拼到一层,减少层数
