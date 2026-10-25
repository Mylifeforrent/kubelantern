# HuntAI Web SPA 生产镜像：Vite 构建 + nginx 同源代理 API/SSE。
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# nginx 配置由 Helm ConfigMap 覆盖挂载；此文件用于独立 docker run 场景。
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
