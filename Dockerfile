# 同镜像多角色（ADR-0009）：api 与 worker 共用本镜像，仅启动命令不同。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev

EXPOSE 8000
# 部署安装必须 uv sync --locked；迁移在 api 启动前由流水线执行（编排 [TBD-INFRA]）
CMD ["uv", "run", "huntai-api"]
