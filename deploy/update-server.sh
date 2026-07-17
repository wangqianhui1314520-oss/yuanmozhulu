#!/bin/bash
# =============================================================================
# 元末逐鹿 · 服务器端更新脚本
# 用法: bash deploy/update-server.sh [--force-nginx]
#   默认跳过 nginx 配置更新（保护已有 SSL 配置）
#   传入 --force-nginx 强制更新 nginx 配置
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FORCE_NGINX=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force-nginx) FORCE_NGINX=true; shift ;;
        --help) echo "用法: $0 [--force-nginx]"; echo "  --force-nginx  强制更新 nginx 配置（谨慎使用）"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}==== $1 ====${NC}\n"; }

# ------------------------------------------------------------
# Step 1: 备份旧版本（安全回滚）
# ------------------------------------------------------------
log_step "1/5 备份旧版本"
BACKUP_DIR="$PROJECT_DIR/../yuanmo-backup-$(date +%Y%m%d-%H%M%S)"
if [ -f "$PROJECT_DIR/deploy/docker-compose.yml" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -r "$PROJECT_DIR/server" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$PROJECT_DIR/server.py" "$BACKUP_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_DIR/frontend/dist" "$BACKUP_DIR/dist" 2>/dev/null || true
    cp "$PROJECT_DIR/requirements.txt" "$BACKUP_DIR/" 2>/dev/null || true
    # 备份 SSL 证书（避免意外丢失）
    if [ -d "$SCRIPT_DIR/nginx/ssl" ]; then
        cp -r "$SCRIPT_DIR/nginx/ssl" "$BACKUP_DIR/ssl" 2>/dev/null || true
    fi
    log_info "备份到 $BACKUP_DIR"
else
    log_warn "未检测到旧版本，跳过备份"
fi

# ------------------------------------------------------------
# Step 2: 停止旧容器
# ------------------------------------------------------------
log_step "2/5 停止旧容器"
cd "$SCRIPT_DIR"
if docker compose ps 2>/dev/null | grep -q "yuanmo"; then
    docker compose down
    log_info "旧容器已停止"
else
    log_warn "未找到运行中的容器"
fi

# ------------------------------------------------------------
# Step 3: 更新 Nginx 配置（默认跳过，保护已有 SSL 配置）
# ------------------------------------------------------------
if [ "$FORCE_NGINX" = true ]; then
    log_step "3/5 强制更新 Nginx 配置"
    if [ ! -f "$SCRIPT_DIR/nginx/ssl/fullchain.pem" ]; then
        log_error "SSL 证书不存在！请先将证书放到 deploy/nginx/ssl/ 目录"
        log_error "如果服务器上已有运行中的 HTTPS 配置，请先确认证书路径"
        log_error "提示: 使用 --force-nginx 仅在你清楚 SSL 配置时才安全"
        exit 1
    fi
    log_info "Nginx 配置已更新，将在容器重建时生效"
else
    log_step "3/5 保留现有 Nginx 配置（已有 HTTPS 配置不会被覆盖）"
    log_info "如需更新 nginx 配置，请使用: bash deploy/update-server.sh --force-nginx"
fi

# ------------------------------------------------------------
# Step 4: 构建并启动新版本
# ------------------------------------------------------------
log_step "4/5 构建新版本"

# 构建后端镜像
log_info "构建 Docker 镜像..."
docker compose build --no-cache backend

# 启动服务
log_info "启动服务..."
docker compose up -d

# ------------------------------------------------------------
# Step 5: 健康检查
# ------------------------------------------------------------
log_step "5/5 健康检查"
log_info "等待服务就绪..."
sleep 10

MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost/api/health > /dev/null 2>&1; then
        log_info "✓ 服务启动成功！健康检查通过"
        echo ""
        echo "  ========================================="
        echo "  ✓ 更新完成！访问: https://qiankuntokenyun.cn"
        echo "  ========================================="
        echo ""
        echo "  当前状态:"
        docker compose ps
        echo ""
        if [ -d "$BACKUP_DIR" ]; then
            echo "  回滚命令: cp -r $BACKUP_DIR/* $PROJECT_DIR/"
        fi
        exit 0
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    log_info "等待中... (${ELAPSED}s)"
done

log_error "健康检查超时！请手动检查: docker compose logs backend"
if [ -d "$BACKUP_DIR" ]; then
    log_error "需要回滚？运行: cp -r $BACKUP_DIR/* $PROJECT_DIR/ && docker compose up -d"
fi
exit 1
