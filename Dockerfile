# =============================================================================
# 元末逐鹿 3.0 · 多阶段 Docker 构建
# CloudStudio / 腾讯云一键部署
# =============================================================================

# ---- Stage 1: 前端构建 (Node.js) ----
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: 最终镜像 (Python 3.11 + Nginx) ----
FROM python:3.11-slim

# 安装 Nginx + 运行时依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ---- 部署目录结构 ----
WORKDIR /app

# Python 后端
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt
COPY server/      /app/server/
COPY server.py    /app/server.py

# 游戏数据（存档、配置等）
COPY data/        /app/data/

# 前端构建产物
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Nginx 配置（debian nginx 使用 conf.d，不使用 sites-enabled）
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/conf.d/default 2>/dev/null || true \
    && echo 'daemon off;' >> /etc/nginx/nginx.conf

# Supervisor 配置（管理 Nginx + Uvicorn）
RUN mkdir -p /var/log/supervisor
COPY supervisor.conf /etc/supervisor/conf.d/yuanmo.conf

# 创建日志目录
RUN mkdir -p /app/logs \
    && mkdir -p /var/log/nginx

# .env 支持（可选挂载；构建时不强制）
RUN touch /app/.env

# ---- 健康检查 ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:80/api/health 2>/dev/null || curl -f http://127.0.0.1:8800/api/health 2>/dev/null || exit 1

# ---- 启动 ----
EXPOSE 80
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
