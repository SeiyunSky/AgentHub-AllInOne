---
name: python_runtime_environment
description: AgentHub 内置 Docker 容器的 Python 运行时白名单。代码 Agent / 部署 Agent / 数据分析 Agent 必读,只能用清单内的库。
trigger_keywords: [Python, 部署, 运行, 依赖, requirements, import]
applicable_agents: [claude, custom]
---

# AgentHub Python 运行时

写 Python 代码部署到 AgentHub 沙箱时,**只能 import 下面清单里的库**。镜像里没有的库,部署会失败。

## 镜像

`agenthub-runtime:python3.11`(基于 `python:3.11-slim`)

## 预装依赖清单(锁版本)

### Web 框架

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
flask==3.0.*
starlette  # fastapi 自带
jinja2==3.1.*
python-multipart  # form / file upload
aiofiles
```

**首选 FastAPI**(默认推荐);Flask 仅在用户明确要求或场景极简(单 endpoint 静态)时用。

### HTTP 调用

```
httpx
requests
```

异步用 `httpx.AsyncClient`,同步用 `requests`。

### 数据存储

```
sqlalchemy==2.0.*
aiosqlite     # async sqlite driver
```

**只支持 sqlite**。需要数据库时:`sqlite:///data.db`(数据落沙箱目录,会话级持久)。

不要尝试连接 PostgreSQL / MySQL / Redis,容器里没有这些 server。

### 数据处理

```
pandas==2.2.*
numpy==2.0.*
matplotlib==3.9.*
```

pandas / numpy 数据分析主力。matplotlib 出图存沙箱 PNG (`plt.savefig(...)`,**不要** `plt.show()`,容器无 GUI)。

### 配置

```
python-dotenv
pydantic==2.*
pydantic-settings
```

## 硬约束

1. **不要写 `pip install xxx`** —— 容器外网受限,而且新装的库会话停了就消失
2. **不要写 import 清单外的库** —— 例如 `django` / `redis` / `psycopg2` / `celery` 都没有
3. **不要 import 标准库以外的"系统级"模块**:`os.system` / `subprocess` 在受限沙箱里也跑不通
4. **网络访问**:容器默认能访问外网,但**不要假定可以连内网/host 的服务**

## 标准 entry point

代码 Agent 写出的应用,**必须**满足:

```python
# app.py 或 main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"hello": "world"}

# uvicorn 由 deploy_app 工具调起来,不要在文件里写 if __name__ == "__main__"
# 部署助手会执行: uvicorn app:app --host 0.0.0.0 --port 8000
```

或者 Flask 等价写法:

```python
# app.py
from flask import Flask
app = Flask(__name__)

@app.route("/")
def root():
    return {"hello": "world"}
```

## requirements.txt(可选)

如果应用需要的所有库都在预装清单里,**不要写 requirements.txt**(无意义)。

只在一种情况下写:某个库的**特定版本**和镜像不一样,而且代码必须用那个版本。这种情况罕见,先确认默认版本是不是真不行。

## 静态资源

```
sandbox/{conv_id}/
  app.py
  templates/        # Jinja2 模板
    index.html
  static/           # CSS / JS / 图片
    style.css
```

FastAPI 挂静态:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
```

## 端口

容器内**必须**监听 `0.0.0.0:8000`。AgentHub 反向代理只转发这个端口。

监听其他端口或 127.0.0.1 → 部署 URL 打不开。

## 速查

写完代码 import 之前心里过一遍:
- 这个库在清单里吗? → 在 → OK
- 不在 → 找清单里能替代的(例如想用 `redis` 改用 `sqlite`,想用 `celery` 改用 `BackgroundTasks`)
- 实在不行 → 告诉部署助手,让用户决定要不要扩镜像
