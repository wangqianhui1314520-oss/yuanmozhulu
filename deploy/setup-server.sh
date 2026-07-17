#!/bin/bash
# =============================================================================
# 元末逐鹿 3.0 · 阿里云服务器一键部署脚本
# 适用: Ubuntu 22.04 64位 + Docker 社区版
# 用法: bash deploy/setup-server.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOMAIN="qiankuntokenyun.cn"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}==== $1 ====${NC}\n"; }

# ============================
# 第1步：安装系统依赖
# ============================
install_deps() {
    log_step "第1步：安装系统依赖"

    # 更新包列表
    sudo apt update -qq

    # 安装 git（通常已预装）
    if ! command -v git >/dev/null 2>&1; then
        log_info "安装 git..."
        sudo apt install -y git
    else
        log_info "git 已安装 ✓"
    fi

    # 安装 Node.js 18.x（Vite 5 需要 Node 18+）
    if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" -lt 18 ]; then
        log_info "安装 Node.js 18.x..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
    log_info "Node.js $(node -v) ✓"
    log_info "npm $(npm -v) ✓"

    # 安装 certbot（用于 Let's Encrypt SSL）
    if ! command -v certbot >/dev/null 2>&1; then
        log_info "安装 certbot..."
        sudo apt install -y certbot
    else
        log_info "certbot 已安装 ✓"
    fi

    # 确认 Docker
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker 未安装！请先安装 Docker 社区版"
        exit 1
    fi
    log_info "Docker $(docker --version | cut -d' ' -f3 | cut -d',' -f1) ✓"

    # 确认 docker compose 可用
    if ! docker compose version >/dev/null 2>&1; then
        log_error "docker compose 不可用！请确保 Docker 版本 >= 20.10"
        exit 1
    fi
    log_info "Docker Compose ✓"

    # 确保当前用户在 docker 组中（root 用户跳过）
    if [ "$(id -u)" != "0" ] && ! groups | grep -q docker; then
        log_warn "当前用户不在 docker 组，添加中..."
        sudo usermod -aG docker "$USER"
        log_warn "请重新登录以生效，然后重新运行本脚本"
        exit 0
    fi
}

# ============================
# 第2步：确认代码仓库
# ============================
check_repo() {
    log_step "第2步：确认代码仓库"

    cd "$PROJECT_DIR"

    if [ ! -f "server.py" ]; then
        log_error "未找到 server.py！请确保在仓库根目录运行本脚本"
        log_info "用法: git clone <仓库地址> yuanmo && cd yuanmo && bash deploy/setup-server.sh"
        exit 1
    fi

    # 拉取最新代码
    log_info "拉取最新代码..."
    git pull origin master 2>/dev/null || log_warn "无法拉取（可能已是最新）"

    log_info "代码仓库就绪 ✓"
}

# ============================
# 第3步：构建前端
# ============================
build_frontend() {
    log_step "第3步：构建前端"

    cd "$PROJECT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log_info "安装前端依赖（可能需要几分钟）..."
        npm install
    fi

    log_info "执行 vite build..."
    npm run build

    if [ ! -f "dist/index.html" ]; then
        log_error "前端构建失败！dist/index.html 不存在"
        exit 1
    fi
    log_info "前端构建完成 → frontend/dist/ ✓"
}

# ============================
# 第4步：配置 SSL 证书
# ============================
setup_ssl() {
    log_step "第4步：配置 SSL 证书"

    local ssl_dir="$SCRIPT_DIR/nginx/ssl"
    mkdir -p "$ssl_dir"

    # 检查是否已有有效证书
    if [ -f "$ssl_dir/fullchain.pem" ] && openssl x509 -checkend 2592000 -noout -in "$ssl_dir/fullchain.pem" 2>/dev/null; then
        log_info "SSL 证书有效（距过期 > 30 天），跳过签发 ✓"
        return
    fi

    # 使用 certbot standalone 申请（需 80 端口空闲）
    log_info "使用 Let's Encrypt 申请 SSL 证书..."
    log_info "域名: $DOMAIN, www.$DOMAIN"

    # 先确保 80 端口空闲
    if sudo lsof -i :80 2>/dev/null | grep -q LISTEN; then
        log_warn "80 端口被占用，尝试停止占用进程..."
        sudo fuser -k 80/tcp 2>/dev/null || true
        sleep 2
    fi

    sudo certbot certonly --standalone \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --non-interactive --agree-tos -m "admin@$DOMAIN" \
        --preferred-challenges http \
        || {
            log_error "Let's Encrypt 证书申请失败！"
            log_info ""
            log_info "可能原因："
            log_info "  1. 域名 DNS 未指向本服务器 IP"
            log_info "  2. 阿里云安全组未开放 80/443 端口"
            log_info "  3. 80 端口被防火墙拦截"
            log_info ""
            log_info "替代方案：使用阿里云免费 SSL 证书"
            log_info "  1. 登录阿里云控制台 → SSL 证书 → 免费证书"
            log_info "  2. 下载 Nginx 格式证书"
            log_info "  3. 将 .pem 文件放到: $ssl_dir/"
            log_info "     fullchain.pem = 证书链文件"
            log_info "     privkey.pem   = 私钥文件"
            log_info "  4. 重新运行: bash deploy/setup-server.sh --skip-ssl"
            exit 1
        }

    # 拷贝证书到 deploy/nginx/ssl/
    if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
        sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$ssl_dir/"
        sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$ssl_dir/"
        sudo chown "$(whoami)" "$ssl_dir/"*
        log_info "SSL 证书配置完成 ✓"
    fi

    # 配置自动续期 cron
    if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
        log_info "配置 SSL 自动续期（每月1号凌晨3点）..."
        (crontab -l 2>/dev/null; echo "0 3 1 * * certbot renew --quiet --post-hook 'cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $ssl_dir/ && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $ssl_dir/ && docker compose -f $SCRIPT_DIR/docker-compose.yml restart nginx'") | crontab -
        log_info "自动续期已配置 ✓"
    fi
}

# ============================
# 第5步：清理默认 API Key（生产安全）
# ============================
sanitize_config() {
    log_step "第5步：安全配置"

    local llm_config="$PROJECT_DIR/server/config/llm_runtime.json"
    if [ -f "$llm_config" ]; then
        log_info "清理 llm_runtime.json 中的默认 API Key..."
        # 用 Python 精确清空所有 api_key 字段
        python3 -c "
import json
with open('$llm_config', 'r') as f:
    cfg = json.load(f)

def clear_keys(obj):
    if isinstance(obj, dict):
        if 'api_key' in obj:
            obj['api_key'] = ''
        for v in obj.values():
            clear_keys(v)

clear_keys(cfg)
with open('$llm_config', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
        log_info "API Key 已清空，玩家需在前端配置自己的 Key ✓"
    fi
}

# ============================
# 第6步：配置环境变量
# ============================
setup_env() {
    log_step "第6步：配置环境变量"

    # 检查 deploy/.env 是否存在
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        log_info "创建 deploy/.env..."
        cat > "$SCRIPT_DIR/.env" << 'EOF'
# 元末逐鹿 3.0 · 生产环境变量
YUANMO_CORS_ORIGINS=https://qiankuntokenyun.cn,https://www.qiankuntokenyun.cn
YUANMO_SESSION_TTL=1800
YUANMO_CLEANUP_INTERVAL=300
PYTHONUNBUFFERED=1
EOF
    fi

    # 加载环境变量
    set -a
    source "$SCRIPT_DIR/.env"
    set +a

    log_info "环境变量配置完成 ✓"
    log_info "  CORS: ${YUANMO_CORS_ORIGINS:-未设置}"
    log_info "  API Key 模式: 玩家自带 Key（推荐）"
}

# ============================
# 第7步：Docker Compose 构建与启动
# ============================
deploy() {
    log_step "第7步：Docker Compose 部署"

    cd "$SCRIPT_DIR"

    # 创建必要目录
    mkdir -p "$PROJECT_DIR/data/archives"
    mkdir -p "$PROJECT_DIR/data/npc_memory"
    mkdir -p "$PROJECT_DIR/data/npc_relations"
    mkdir -p "$PROJECT_DIR/logs/nginx"

    # 构建后端镜像
    log_info "构建 Docker 镜像（首次可能需要几分钟）..."
    docker compose build --no-cache backend

    # 拉取 nginx 镜像
    log_info "拉取 Nginx 镜像..."
    docker compose pull nginx

    # 启动服务
    log_info "启动服务..."
    docker compose up -d

    # 等待健康检查
    log_info "等待后端健康检查（最多60秒）..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost/api/health >/dev/null 2>&1; then
            log_info "后端健康检查通过 ✓"
            break
        fi
        if [ "$i" -eq 30 ]; then
            log_error "后端启动超时！查看日志: docker compose -f $SCRIPT_DIR/docker-compose.yml logs backend"
            exit 1
        fi
        sleep 2
    done

    # 验证 HTTPS 访问
    if curl -sf -o /dev/null -w "%{http_code}" "https://$DOMAIN/api/health" 2>/dev/null | grep -q "200"; then
        log_info "HTTPS 访问验证通过 ✓"
    else
        log_warn "HTTPS 访问暂时不通，请检查："
        log_info "  1. 阿里云安全组是否开放 80/443 端口"
        log_info "  2. DNS 是否已解析到本服务器"
        log_info "  3. 稍等几分钟 DNS 生效后再试"
    fi
}

# ============================
# 主入口
# ============================
main() {
    SKIP_SSL=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-ssl)
                SKIP_SSL=true
                shift
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            *)
                log_error "未知参数: $1"
                echo "用法: $0 [--skip-ssl] [--domain DOMAIN]"
                exit 1
                ;;
        esac
    done

    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   ⚔️  元末逐鹿 3.0 · 服务器部署      ║"
    echo "  ║   域名: $DOMAIN                  ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""

    # 前置检查：确认 80/443 端口未被占用（Docker 之外）
    log_step "前置检查"
    if sudo lsof -i :80 2>/dev/null | grep -v docker | grep -q LISTEN; then
        log_warn "80 端口被非 Docker 进程占用，可能导致 Nginx 无法启动"
        sudo lsof -i :80 2>/dev/null | grep LISTEN
    fi
    if sudo lsof -i :443 2>/dev/null | grep -v docker | grep -q LISTEN; then
        log_warn "443 端口被非 Docker 进程占用，可能导致 Nginx 无法启动"
        sudo lsof -i :443 2>/dev/null | grep LISTEN
    fi

    install_deps
    check_repo
    build_frontend

    if [ "$SKIP_SSL" = false ]; then
        setup_ssl
    else
        log_warn "跳过 SSL 配置（--skip-ssl）"
        log_info "请确保 deploy/nginx/ssl/ 中已有证书文件"
    fi

    sanitize_config
    setup_env
    deploy

    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   ✅ 部署完成！                      ║"
    echo "  ║                                      ║"
    echo "  ║   游戏地址: https://$DOMAIN          ║"
    echo "  ║   健康检查: https://$DOMAIN/api/health ║"
    echo "  ║                                      ║"
    echo "  ║   常用命令:                           ║"
    echo "  ║   状态: cd deploy && docker compose ps ║"
    echo "  ║   日志: cd deploy && docker compose logs -f ║"
    echo "  ║   重启: cd deploy && docker compose restart ║"
    echo "  ║   停止: cd deploy && docker compose down ║"
    echo "  ║   更新: bash deploy/deploy.sh --update ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""
}

main "$@"
