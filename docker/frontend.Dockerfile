# 不在镜像内拉取 Node：避免 Docker Hub / IPv6 鉴权失败。
# 先在本机构建：npm --prefix frontend ci && npm --prefix frontend run build
# 或运行：.\scripts\docker-up.ps1
FROM nginx:1.27-alpine

COPY frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
