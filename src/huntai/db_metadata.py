"""全量模型注册表：Alembic env 与测试建库用（保证 Base.metadata 完整）。"""

from __future__ import annotations

from huntai.core.db import Base
from huntai.domains.ai import models as _ai
from huntai.domains.alerts import models as _alerts
from huntai.domains.clusters import models as _clusters
from huntai.domains.iam import models as _iam
from huntai.domains.incidents import models as _incidents
from huntai.domains.inspections import models as _inspections
from huntai.domains.notifications import models as _notifications
from huntai.domains.oncall import models as _oncall
from huntai.domains.workflows import models as _workflows

EXPECTED_TABLE_COUNT = 32


def assert_metadata_complete() -> None:
    count = len(Base.metadata.tables)
    assert count == EXPECTED_TABLE_COUNT, f"表数量 {count} != {EXPECTED_TABLE_COUNT}"
