# 同镜像多角色（ADR-0009）：api 与 worker 共用本镜像，仅启动命令不同。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
# pyproject 的 readme 指向 frontend/README.md；构建元数据需要该文件存在。
COPY frontend/README.md ./frontend/README.md
COPY src ./src
RUN uv sync --locked --no-dev
# 迁移在 API 的 initContainer 执行；镜像必须携带 alembic 配置与迁移脚本。
COPY alembic.ini ./
COPY migrations ./migrations

EXPOSE 8000
# 部署安装必须 uv sync --locked；迁移在 api 启动前由流水线执行（编排 [TBD-INFRA]）
CMD ["huntai-api"]
