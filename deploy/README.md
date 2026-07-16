# 元末逐鹿 3.0 · 阿里云 ECS 部署快速指南

---

## 前置准备

- [ ] 阿里云 ECS（建议 Ubuntu 22.04，2C4G 起步）
- [ ] 域名已解析到 ECS 公网 IP（A 记录）
- [ ] 安全组已放行：**80**(HTTP)、**443**(HTTPS)、**22**(SSH)
- [ ] SSH 可登录服务器

---

## 第一步：服务器环境初始化

```bash
# SSH 登录
ssh root@你的服务器IP

# 安装基础依赖
apt update && apt install -y git docker.io docker-compose-v2 nodejs npm curl

# 启动 Docker
systemctl enable --now docker

# 创建部署用户（可选但推荐）
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
```

---

## 第二步：上传项目代码

**方式 A — git clone（推荐）：**
```bash
git clone <你的仓库地址> /opt/yuanmo
cd /opt/yuanmo
```

**方式 B — scp 上传：**
```bash
# 在本地执行
scp -r d:/AI/元末逐鹿/* root@你的服务器IP:/opt/yuanmo/
```

---

## 第三步：配置密钥与域名

```bash
cd /opt/yuanmo

# 设置 CORS 来源（你的域名，HTTPS 必须）
export YUANMO_CORS_ORIGINS='https://你的域名.com'

# 玩家自带 LLM Key 模式：不设置 TENCENT_API_KEY，
# 每个玩家在前端配置自己的腾讯混元 API Key
# 如果留空，服务器启动时 LLM 状态为降级但可正常运行

# 会话 TTL（可选，默认30分钟无活动自动清理）
export YUANMO_SESSION_TTL=1800

# 写入 /etc/environment 持久化
echo 'YUANMO_CORS_ORIGINS=https://你的域名.com' | sudo tee -a /etc/environment
echo 'YUANMO_SESSION_TTL=1800' | sudo tee -a /etc/environment
```

---

## 第四步：一键部署

```bash
cd /opt/yuanmo

# 首次部署（带域名 + SSL）
bash deploy/deploy.sh --domain 你的域名.com

# 如果暂时不用 SSL（仅测试）
bash deploy/deploy.sh
```

脚本会自动：
1. 安装前端依赖并 `vite build`
2. 替换 Nginx 配置中的域名
3. 尝试通过 Let's Encrypt 签发 SSL 证书
4. 构建 Docker 镜像并启动服务
5. Docker 外部端口:80/443 → Nginx → 内部 :8800 (FastAPI)

---

## 第五步：验证

```bash
# 检查服务状态
docker compose -f deploy/docker-compose.yml ps

# 检查健康
curl http://localhost/api/health

# 浏览器访问
# https://你的域名.com
```

---

## 更新代码

```bash
cd /opt/yuanmo
bash deploy/deploy.sh --update
```

---

## 故障排查

```bash
# 查看后端日志
docker compose -f deploy/docker-compose.yml logs backend -f

# 查看 Nginx 日志
docker compose -f deploy/docker-compose.yml logs nginx -f

# 重启全部服务
docker compose -f deploy/docker-compose.yml restart

# 完全重建
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml up -d --build
```

---

## SSL 证书续期

```bash
# Let's Encrypt 有效期 90 天，设置自动续期
sudo certbot renew --dry-run  # 测试
sudo crontab -e
# 添加: 0 3 * * * certbot renew --quiet && docker compose -f /opt/yuanmo/deploy/docker-compose.yml restart nginx
```

---

## 安全加固（上线前必做）

1. **确认 .env 不在代码仓库中**：`git log --all -- .env` 如曾提交过，立即轮换 API Key
2. **添加用户认证**：Nginx 层 HTTP Basic Auth 或实现 JWT 登录
3. **限制 SSH**：禁用 root 密码登录，改用密钥
4. **开启防火墙**：`ufw allow 80,443,22/tcp && ufw enable`

---

## 成本预估

| 项目 | 约月费 |
|------|--------|
| 阿里云 ECS 2C4G | ¥60-80 |
| 域名 .com | ¥5-10/月 |
| SSL 证书 | ¥0 (Let's Encrypt) |
| LLM API | 按量（取决于玩家活跃度） |
| **合计** | **~¥70-90/月起步** |
