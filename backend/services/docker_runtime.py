"""
DockerRuntimeService —— 会话级 Docker 容器调度 + reverse proxy 后端

职责:
- 启动时确保 agenthub-runtime:python3.11 镜像存在(不存在自动 build)
- 每个 conversation 起一个长驻容器,挂载会话沙箱目录到 /app
- 提供 exec_in_container 让 deploy_app 工具用 docker exec 起 uvicorn
- 暴露容器内部 IP 给 preview reverse proxy 转发流量
- 闲置回收(30 分钟无流量自动停)

容器策略(选 "长驻 + exec",见 Phase 2.A 设计文档):
- docker run agenthub-runtime sleep infinity (常驻)
- 实际服务由 docker exec uvicorn ... 触发
- 重 deploy 时 pkill + 新 exec,容器不重建,沙箱 / 已 pip install 的库不丢

并发模型:
- docker SDK 是同步的,本 service 用 asyncio.to_thread 包成 async
- 模块级单例(get_docker_runtime),所有 conversation 共用
- 容器命名 agenthub-{conv_id 前 12 位}, 由 conv_id 唯一映射

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-04
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container


logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================

IMAGE_NAME = "agenthub-runtime"
IMAGE_TAG = "python3.11"
IMAGE_FULL = f"{IMAGE_NAME}:{IMAGE_TAG}"

# Dockerfile 位置:仓库根 runtime/
_DOCKERFILE_DIR = Path(__file__).resolve().parent.parent.parent / "runtime"

CONTAINER_NAME_PREFIX = "agenthub-"
CONTAINER_INTERNAL_PORT = 8000  # 容器内 uvicorn 监听端口

# 资源限制
MEMORY_LIMIT = "512m"
CPU_QUOTA = 100_000   # 100ms / 100ms = 1.0 CPU(用 cpu_period + cpu_quota,跨平台稳定)
CPU_PERIOD = 100_000

# 闲置回收
DEFAULT_IDLE_MINUTES = 30


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ContainerHandle:
    """容器对外暴露的元数据(屏蔽 docker SDK 对象)"""
    conv_id: str
    container_id: str
    container_name: str
    internal_ip: str        # 容器在 docker bridge 上的 IP(Linux host 可达,Windows Docker Desktop 不可达)
    host_port: int          # 容器 8000 端口映射到 host 的实际端口 — reverse proxy 用这个,跨平台稳定
    started_at: float       # epoch seconds


@dataclass
class ExecResult:
    exit_code: int
    output: str             # stdout + stderr 合并


# ============================================================
# Service
# ============================================================

class DockerRuntimeService:
    """
    会话级 Docker 容器调度 facade。

    单例:get_docker_runtime() 拿全局唯一实例,不要直接 new。
    """

    def __init__(self) -> None:
        # docker.from_env() 自动读环境(DOCKER_HOST 等),Windows Docker Desktop 默认走 npipe
        # 失败延后到第一次实际调用,避免 import 阶段就炸
        self._client: Optional[docker.DockerClient] = None
        # 闲置追踪:conv_id -> 最后访问时间(reverse proxy 每次转发更新)
        self._last_seen: dict[str, float] = {}

    # ----------------------------------------------------------
    # 客户端
    # ----------------------------------------------------------

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            try:
                self._client = docker.from_env()
                # 触发实际连接验证(否则 socket 不通也不会立即报)
                self._client.ping()
            except Exception as exc:
                # 不打 stack trace —— Docker Desktop 未启动是预期场景,
                # 一长串 npipe pywintypes trace 让用户以为是 bug。
                # 调用方(lifespan / deploy_app)会再 log 一次 RuntimeError 摘要。
                logger.warning(
                    "Docker daemon 连接失败 (Docker Desktop 未启动?): %s", exc
                )
                raise RuntimeError(
                    "无法连接 Docker daemon。请确认 Docker Desktop / dockerd 已启动。"
                ) from exc
        return self._client

    # ----------------------------------------------------------
    # 镜像
    # ----------------------------------------------------------

    async def ensure_image(self) -> None:
        """
        启动时调:agenthub-runtime:python3.11 镜像不存在则 build。
        幂等。第一次 build 约 3-5 分钟(下载基础镜像 + pip install)。
        """
        await asyncio.to_thread(self._ensure_image_sync)

    def _ensure_image_sync(self) -> None:
        client = self._get_client()
        try:
            client.images.get(IMAGE_FULL)
            logger.info("Docker image %s 已存在,跳过 build", IMAGE_FULL)
            return
        except ImageNotFound:
            pass

        if not _DOCKERFILE_DIR.exists():
            raise RuntimeError(
                f"Dockerfile 目录不存在: {_DOCKERFILE_DIR}。"
                "确认仓库根有 runtime/Dockerfile"
            )

        logger.info("Docker image %s 不存在,开始 build (耗时 3-5 分钟,会实时输出进度)...", IMAGE_FULL)
        # 用 low-level api.build 拿到流式 iterator,一边 build 一边打 log
        # (high-level images.build() 是同步返回,所有 log 都在 build 完成后才一次性给,
        # 长时间 build 看不到进度,用户以为卡住了)
        try:
            stream = client.api.build(
                path=str(_DOCKERFILE_DIR),
                tag=IMAGE_FULL,
                rm=True,
                forcerm=True,
                pull=True,
                decode=True,        # 自动 json.loads 每一行
            )
            for chunk in stream:
                if "stream" in chunk:
                    line = chunk["stream"].rstrip()
                    if line:
                        logger.info("docker build: %s", line)
                elif "status" in chunk:
                    # pull 阶段的进度行,只 log 关键状态(避免几百行 layer pull 进度刷屏)
                    status = chunk.get("status", "")
                    if status.startswith(("Pulling from", "Status:", "Digest:", "Pulled")):
                        logger.info("docker pull: %s", status)
                elif "error" in chunk:
                    logger.error("docker build error: %s", chunk["error"])
                    raise APIError(chunk["error"])
            logger.info("Docker image %s build 成功", IMAGE_FULL)
        except APIError as exc:
            logger.exception("Docker build 失败: %s", exc)
            raise

    # ----------------------------------------------------------
    # 容器名 / 查询
    # ----------------------------------------------------------

    @staticmethod
    def _container_name(conv_id: str) -> str:
        # 截前 12 位避免 docker container name 限制(最长 63),冒号转下划线
        # 同 conv_id 总是映射到同名容器,便于 reuse 查询
        safe = conv_id.replace("/", "_").replace(":", "_")[:12]
        return f"{CONTAINER_NAME_PREFIX}{safe}"

    async def get_container(self, conv_id: str) -> Optional[ContainerHandle]:
        """
        查会话当前是否有运行中的容器。返回 None 表示需要 start_container。

        如果容器存在但已停止 / 异常,返回 None(让 start_container 重建)。
        """
        return await asyncio.to_thread(self._get_container_sync, conv_id)

    def _get_container_sync(self, conv_id: str) -> Optional[ContainerHandle]:
        client = self._get_client()
        name = self._container_name(conv_id)
        try:
            container = client.containers.get(name)
        except NotFound:
            return None

        # 容器存在但状态不对 → 视为不可用(让上层 stop + 重建)
        container.reload()
        if container.status != "running":
            logger.warning(
                "Container %s 状态 %s,不可用",
                name, container.status,
            )
            return None

        ip = self._extract_ip(container)
        host_port = self._extract_host_port(container)
        if not ip or not host_port:
            logger.warning(
                "Container %s 缺少 ip/host_port (ip=%s,port=%s),不可用",
                name, ip, host_port,
            )
            return None

        return ContainerHandle(
            conv_id=conv_id,
            container_id=container.id,
            container_name=name,
            internal_ip=ip,
            host_port=host_port,
            started_at=self._last_seen.get(conv_id, time.time()),
        )

    @staticmethod
    def _extract_ip(container: Container) -> Optional[str]:
        """从容器 NetworkSettings 取第一个 bridge 上的 IP"""
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress")
            if ip:
                return ip
        return None

    @staticmethod
    def _extract_host_port(container: Container) -> Optional[int]:
        """从容器 NetworkSettings.Ports 取 8000/tcp 映射到 host 的端口"""
        ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
        binding = ports.get(f"{CONTAINER_INTERNAL_PORT}/tcp")
        if not binding:
            return None
        # binding 是 list[{"HostIp": "0.0.0.0", "HostPort": "12345"}]
        for entry in binding:
            host_port_str = entry.get("HostPort")
            if host_port_str:
                try:
                    return int(host_port_str)
                except ValueError:
                    continue
        return None

    # ----------------------------------------------------------
    # 容器生命周期
    # ----------------------------------------------------------

    async def start_container(self, conv_id: str, sandbox_path: Path) -> ContainerHandle:
        """
        给会话起一个长驻容器(sleep infinity)。

        sandbox_path 必须是 host 上的绝对路径,会被挂载到容器 /app。
        Windows Docker Desktop 自动把 C:\\... 转成 /run/desktop/mnt/host/c/...
        理论上无需手动转。

        如果同名容器已存在(可能是上次 dirty 残留),先 stop+remove。
        """
        return await asyncio.to_thread(
            self._start_container_sync, conv_id, sandbox_path,
        )

    def _start_container_sync(self, conv_id: str, sandbox_path: Path) -> ContainerHandle:
        client = self._get_client()
        name = self._container_name(conv_id)

        # 残留清理:同名容器存在就停 + 删
        try:
            old = client.containers.get(name)
            logger.info("Removing stale container %s (status=%s)", name, old.status)
            try:
                old.stop(timeout=2)
            except Exception:
                pass
            old.remove(force=True)
        except NotFound:
            pass

        # 沙箱目录必须存在(memory_service.ensure_memory_dir 在 resolve 时创建)
        # 这里兜底创建,避免容器启动后才发现挂载点为空
        sandbox_path.mkdir(parents=True, exist_ok=True)
        host_path = str(sandbox_path.resolve())

        logger.info(
            "Starting container %s (sandbox=%s)",
            name, host_path,
        )

        try:
            container = client.containers.run(
                IMAGE_FULL,
                name=name,
                command=["sleep", "infinity"],
                detach=True,
                # 挂载沙箱
                volumes={host_path: {"bind": "/app", "mode": "rw"}},
                working_dir="/app",
                # 资源限制
                mem_limit=MEMORY_LIMIT,
                cpu_period=CPU_PERIOD,
                cpu_quota=CPU_QUOTA,
                # 端口映射:容器 8000 → host 随机可用端口。
                # 必须做端口映射的原因:Windows Docker Desktop 上 host 直连
                # 容器 bridge IP (172.x.x.x) 不通(容器跑在 WSL2 / Hyper-V 虚拟机
                # 网络隔离),只有通过端口映射经 vEthernet 才能访问。
                # Linux host 也用同样配置,跨平台行为一致。
                # None 表示让 Docker 自动选可用 host 端口,避免端口冲突 / 自己维护池
                ports={f"{CONTAINER_INTERNAL_PORT}/tcp": None},
                # 网络:default bridge,容器之间隔离
                # 标识便于 docker ps 过滤
                labels={"agenthub.role": "runtime", "agenthub.conv_id": conv_id},
                # 不自动重启
                restart_policy={"Name": "no"},
            )
        except APIError as exc:
            logger.exception("Container start 失败 conv=%s: %s", conv_id, exc)
            raise

        # 等待容器拿到 IP + host_port (刚启动 Docker 还在分配)
        ip: Optional[str] = None
        host_port: Optional[int] = None
        for _ in range(20):  # 最多等 2 秒
            container.reload()
            ip = self._extract_ip(container)
            host_port = self._extract_host_port(container)
            if ip and host_port:
                break
            time.sleep(0.1)

        if not ip or not host_port:
            logger.error(
                "Container %s 启动后缺 ip/host_port (ip=%s,port=%s)",
                name, ip, host_port,
            )
            try:
                container.stop(timeout=2)
                container.remove(force=True)
            except Exception:
                pass
            raise RuntimeError(
                f"Container {name} 启动后缺少 IP 或 host 端口映射"
            )

        now = time.time()
        self._last_seen[conv_id] = now
        logger.info(
            "Container %s started, ip=%s host_port=%d",
            name, ip, host_port,
        )

        return ContainerHandle(
            conv_id=conv_id,
            container_id=container.id,
            container_name=name,
            internal_ip=ip,
            host_port=host_port,
            started_at=now,
        )

    async def stop_container(self, conv_id: str) -> bool:
        """停 + 删容器。返回 True 表示有容器被清理。"""
        return await asyncio.to_thread(self._stop_container_sync, conv_id)

    def _stop_container_sync(self, conv_id: str) -> bool:
        client = self._get_client()
        name = self._container_name(conv_id)
        try:
            container = client.containers.get(name)
        except NotFound:
            return False
        try:
            container.stop(timeout=3)
        except Exception:
            logger.exception("Container %s stop 失败", name)
        try:
            container.remove(force=True)
        except Exception:
            logger.exception("Container %s remove 失败", name)
        self._last_seen.pop(conv_id, None)
        logger.info("Container %s stopped + removed", name)
        return True

    # ----------------------------------------------------------
    # 容器内执行
    # ----------------------------------------------------------

    async def exec_in_container(
        self,
        container_id: str,
        cmd: list[str] | str,
        *,
        detach: bool = False,
        workdir: str = "/app",
        timeout: Optional[float] = None,
    ) -> ExecResult:
        """
        容器内执行命令。

        - detach=False: 等命令结束,返回 exit_code + 合并 stdout/stderr
        - detach=True: 后台跑,立即返回(用于起 uvicorn 这种长进程)。
          此时 exit_code = 0(无意义),output = "" (拿不到)

        cmd 可以是 list 或 str:
        - list 直接 exec,无 shell wrapping(推荐,避免转义)
        - str 自动包成 ["sh", "-c", cmd],方便用 && / | 等
        """
        return await asyncio.to_thread(
            self._exec_sync, container_id, cmd, detach, workdir, timeout,
        )

    def _exec_sync(
        self,
        container_id: str,
        cmd: list[str] | str,
        detach: bool,
        workdir: str,
        timeout: Optional[float],
    ) -> ExecResult:
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
        except NotFound:
            raise RuntimeError(f"Container {container_id} 不存在")

        # str → sh -c 包装
        if isinstance(cmd, str):
            exec_cmd = ["sh", "-c", cmd]
        else:
            exec_cmd = list(cmd)

        try:
            result = container.exec_run(
                exec_cmd,
                workdir=workdir,
                detach=detach,
                stdout=True,
                stderr=True,
                stream=False,
            )
        except APIError as exc:
            logger.exception("exec failed: cmd=%s err=%s", exec_cmd, exc)
            raise

        if detach:
            return ExecResult(exit_code=0, output="")

        exit_code = result.exit_code if result.exit_code is not None else -1
        output_bytes = result.output if isinstance(result.output, bytes) else b""
        output = output_bytes.decode("utf-8", errors="replace")
        return ExecResult(exit_code=exit_code, output=output)

    # ----------------------------------------------------------
    # 闲置追踪 + 回收
    # ----------------------------------------------------------

    def touch(self, conv_id: str) -> None:
        """reverse proxy 每次转发请求调一次,刷新最后访问时间"""
        self._last_seen[conv_id] = time.time()

    async def stop_idle(self, idle_minutes: int = DEFAULT_IDLE_MINUTES) -> int:
        """
        回收闲置容器。返回回收数量。
        闲置 = last_seen 超过 idle_minutes 之前。
        """
        return await asyncio.to_thread(self._stop_idle_sync, idle_minutes)

    def _stop_idle_sync(self, idle_minutes: int) -> int:
        threshold = time.time() - idle_minutes * 60
        # 拷贝 keys 防迭代时修改
        idle_convs = [
            cid for cid, last in list(self._last_seen.items())
            if last < threshold
        ]
        if not idle_convs:
            return 0
        count = 0
        for conv_id in idle_convs:
            try:
                if self._stop_container_sync(conv_id):
                    count += 1
            except Exception:
                logger.exception("idle stop failed conv=%s", conv_id)
        return count

    # ----------------------------------------------------------
    # 关闭
    # ----------------------------------------------------------

    async def shutdown(self) -> None:
        """AgentHub 进程退出时调:停所有 agenthub-* 容器,关 SDK client"""
        await asyncio.to_thread(self._shutdown_sync)

    def _shutdown_sync(self) -> None:
        if self._client is None:
            return
        try:
            containers = self._client.containers.list(
                all=True,
                filters={"label": "agenthub.role=runtime"},
            )
            for c in containers:
                try:
                    c.stop(timeout=2)
                    c.remove(force=True)
                    logger.info("Shutdown stopped container %s", c.name)
                except Exception:
                    logger.exception("Shutdown stop failed: %s", c.name)
        except Exception:
            logger.exception("Shutdown listing containers failed")
        try:
            self._client.close()
        except Exception:
            pass
        self._client = None


# ============================================================
# 模块级单例
# ============================================================

_instance: Optional[DockerRuntimeService] = None


def get_docker_runtime() -> DockerRuntimeService:
    """全局 DockerRuntimeService。所有调用方走这个,不要直接 new。"""
    global _instance
    if _instance is None:
        _instance = DockerRuntimeService()
    return _instance
