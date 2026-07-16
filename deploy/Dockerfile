# =============================================================================
# 元末逐鹿 3.0 · 生产环境 Dockerfile
# 阿里云 ECS / 任意 Linux 服务器通用
# =============================================================================
FROM python:3.11-slim

LABEL maintainer="元末逐鹿"
LABEL description="元末逐鹿 3.0 - 后端 API 服务"

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# Python 依赖（分层缓存 · 阿里云镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 复制后端代码
COPY server/ ./server/
COPY server.py .

# 复制前端构建产物（用于后端直接托管静态文件）
COPY frontend/dist/ ./frontend/dist/

# 数据目录（存档、NPC 记忆等运行时数据，通过 volume 挂载）
RUN mkdir -p data/archives data/npc_memory data/npc_relations logs

# 非 root 用户运行
RUN useradd -m -s /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8800/api/health || exit 1

# 启动
EXPOSE 8800
CMD ["python", "-m", "uvicorn", "server.api_server:app", "--host", "0.0.0.0", "--port", "8800", "--workers", "1", "--log-level", "info"]
