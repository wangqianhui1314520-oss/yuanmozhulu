# 将 SSL 证书文件（fullchain.pem 和 privkey.pem）放在此目录
# .gitignore 已配置排除 *.pem 文件，确保证书不会提交到版本控制
# 
# 获取免费 SSL 证书:
#   sudo certbot certonly --standalone -d qiankuntokenyun.cn -d www.qiankuntokenyun.cn
#   sudo cp /etc/letsencrypt/live/qiankuntokenyun.cn/fullchain.pem deploy/nginx/ssl/
#   sudo cp /etc/letsencrypt/live/qiankuntokenyun.cn/privkey.pem deploy/nginx/ssl/
#
# 或使用阿里云免费 SSL 证书（推荐）：下载后放此目录即可
