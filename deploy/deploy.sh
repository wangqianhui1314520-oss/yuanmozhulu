#!/bin/bash
# =============================================================================
# 元末逐鹿 3.0 · 一键部署脚本 (阿里云 ECS / Ubuntu 22.04+)
# =============================================================================
# 用法:
#   1. 首次部署:  bash deploy/deploy.sh --domain your-domain.com
#   2. 更新代码:  bash deploy/deploy.sh --update
#   3. 查看状态:  bash deploy/deploy.sh --status
#   4. 查看日志:  bash deploy/deploy.sh --logs
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOMAIN=""

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}==== $1 ====${NC}\n"; }

# ---- 检查依赖 ----
check_deps() {
    log_step "检查依赖"
    local missing=()

    command -v docker  >/dev/null 2>&1 || missing+=("docker")
    command -v node    >/dev/null 2>&1 || missing+=("node (npm)")
    command -v git     >/dev/null 2>&1 || missing+=("git")

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少依赖: ${missing[*]}"
        log_info "Ubuntu 安装命令:"
        log_info "  sudo apt update && sudo apt install -y docker.io docker-compose-v2 nodejs npm git"
        log_info "  sudo systemctl enable --now docker"
        log_info "  sudo usermod -aG docker \$USER  # 重新登录后生效"
        exit 1
    fi
    log_info "所有依赖就绪"
}

# ---- 构建前端 ----
build_frontend() {
    log_step "构建前端"
    cd "$PROJECT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖..."
        npm install
    fi

    log_info "执行 vite build..."
    npm run build

    if [ ! -f "dist/index.html" ]; then
        log_error "前端构建失败！dist/index.html 不存在"
        exit 1
    fi
    log_info "前端构建完成 → frontend/dist/"
}

# ---- 生成 SSL 证书 ----
setup_ssl() {
    if [ -z "$DOMAIN" ]; then
        log_warn "未指定域名，跳过 SSL 配置"
        return
    fi

    log_step "配置 SSL 证书 (Let's Encrypt)"

    local ssl_dir="$SCRIPT_DIR/nginx/ssl"
    mkdir -p "$ssl_dir"

    # 检查是否已有证书
    if [ -f "$ssl_dir/fullchain.pem" ] && openssl x509 -checkend 2592000 -noout -in "$ssl_dir/fullchain.pem" 2>/dev/null; then
        log_info "SSL 证书有效，跳过签发"
        return
    fi

    # 用 certbot 申请证书
    if command -v certbot >/dev/null 2>&1; then
        log_info "运行 certbot..."
        sudo certbot certonly --standalone \
            -d "$DOMAIN" -d "www.$DOMAIN" \
            --non-interactive --agree-tos -m "admin@$DOMAIN" \
            || log_warn "certbot 申请失败，请手动申请或使用阿里云免费证书"

        # 拷贝到 deploy 目录
        if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
            sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$ssl_dir/"
            sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$ssl_dir/"
            sudo chown "$(whoami)" "$ssl_dir/"*
            log_info "SSL 证书配置完成"
        fi
    else
        log_warn "certbot 未安装，请手动配置 SSL："
        log_info "  sudo apt install certbot"
        log_info "  sudo certbot certonly --standalone -d $DOMAIN"
        log_info "  sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem deploy/nginx/ssl/"
        log_info "  sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem deploy/nginx/ssl/"
        log_info ""
        log_info "或使用阿里云免费SSL证书：下载后放 deploy/nginx/ssl/ 目录"
    fi
}

# ---- 替换 Nginx 域名占位符 ----
patch_nginx_config() {
    if [ -z "$DOMAIN" ]; then
        return
    fi
    log_info "替换 Nginx 配置中的域名 → $DOMAIN"
    sed -i "s/YOUR_DOMAIN.com/$DOMAIN/g" "$SCRIPT_DIR/nginx/default.conf"
}

# ---- 设置环境变量 ----
setup_env() {
    log_step "配置环境变量"
    if [ -z "${TENCENT_API_KEY:-}" ]; then
        log_info "TENCENT_API_KEY 未设置 → 玩家自带 Key 模式"
        log_info "每个玩家在前端配置自己的腾讯混元 API Key，你无需承担 API 费用"
    else
        log_info "TENCENT_API_KEY 已设置 → 服务端统一 Key 模式"
    fi

    if [ -n "$DOMAIN" ]; then
        if [ -z "${YUANMO_CORS_ORIGINS:-}" ]; then
            export YUANMO_CORS_ORIGINS="https://$DOMAIN,https://www.$DOMAIN"
            log_info "自动设置 CORS: $YUANMO_CORS_ORIGINS"
        fi
    fi
}

# ---- 构建并启动 ----
deploy() {
    log_step "Docker Compose 部署"

    cd "$SCRIPT_DIR"

    # 构建镜像
    log_info "构建 Docker 镜像..."
    docker compose build --no-cache backend

    # 启动
    log_info "启动服务..."
    docker compose up -d

    # 等待健康检查
    log_info "等待服务就绪..."
    sleep 10
    if docker compose ps | grep -q "healthy"; then
        log_info "✓ 服务启动成功！"
    else
        log_warn "服务可能尚未就绪，运行 'docker compose logs' 查看详情"
    fi
}

# ---- 更新部署 ----
update() {
    log_step "更新部署"
    cd "$PROJECT_DIR"

    log_info "拉取最新代码..."
    git pull

    log_info "重新构建..."
    build_frontend
    cd "$SCRIPT_DIR"
    docker compose build --no-cache backend
    docker compose up -d --force-recreate

    log_info "✓ 更新完成"
}

# ---- 状态检查 ----
status() {
    log_step "服务状态"
    cd "$SCRIPT_DIR"
    docker compose ps
    echo ""
    log_info "健康检查:"
    if command -v curl >/dev/null 2>&1; then
        curl -s http://localhost/api/health | python3 -m json.tool 2>/dev/null || echo "  后端未响应"
    fi
}

# ---- 查看日志 ----
show_logs() {
    cd "$SCRIPT_DIR"
    docker compose logs --tail=50 -f
}

# ---- 主入口 ----
main() {
    echo ""
    echo "  ⚔️  元末逐鹿 3.0 · 部署脚本"
    echo "  =============================="

    while [[ $# -gt 0 ]]; do
        case $1 in
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --update)
                build_frontend
                update
                exit 0
                ;;
            --status)
                status
                exit 0
                ;;
            --logs)
                show_logs
                exit 0
                ;;
            --build-only)
                check_deps
                build_frontend
                log_info "构建完成，跳过 Docker 部署"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "用法: $0 [--domain DOMAIN] [--update] [--status] [--logs] [--build-only]"
                exit 1
                ;;
        esac
    done

    check_deps
    build_frontend

    if [ -n "$DOMAIN" ]; then
        patch_nginx_config
        setup_ssl
    else
        log_warn "未指定 --domain，将使用 HTTP 模式（不推荐公网使用）"
        # 生成仅 HTTP 的简单 nginx 配置
        sed -i '/443/d; /ssl_/d; /return 301/d' "$SCRIPT_DIR/nginx/default.conf" 2>/dev/null || true
    fi

    setup_env
    deploy

    echo ""
    echo "  ========================================="
    if [ -n "$DOMAIN" ]; then
        echo "  ✓ 部署完成！访问: https://$DOMAIN"
    else
        echo "  ✓ 部署完成！访问: http://<服务器IP>"
    fi
    echo "  ========================================="
    echo ""
    echo "  常用命令:"
    echo "    状态: docker compose -f deploy/docker-compose.yml ps"
    echo "    日志: docker compose -f deploy/docker-compose.yml logs -f"
    echo "    重启: docker compose -f deploy/docker-compose.yml restart"
    echo "    停止: docker compose -f deploy/docker-compose.yml down"
    echo ""
}

main "$@"
