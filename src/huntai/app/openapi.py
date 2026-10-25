"""OpenAPI 导出模块：uv run python -m huntai.app.openapi [--out PATH]。

契约阶段二事实源（04-backend-design §4.5）：改代码 → 导出 docs/04-api/openapi.json →
CI `git diff --exit-code` 校验。本模块只负责导出；切换 PR 流程见 05-fe-be-boundary §2。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_OUT = Path("docs/04-api/openapi.json")


def export_spec(out_path: Path | None = None) -> Path:
    from huntai.app.main import create_app

    app = create_app()
    spec = app.openapi()
    target = out_path or DEFAULT_OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 FastAPI OpenAPI spec（契约阶段二事实源）")
    parser.add_argument("--out", type=Path, default=None, help=f"输出路径（默认 {DEFAULT_OUT}）")
    args = parser.parse_args(argv)
    path = export_spec(args.out)
    print(f"openapi spec 已导出：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
