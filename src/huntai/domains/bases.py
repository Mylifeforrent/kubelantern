"""ORM 列公共基座（01-data-model §2.1：bigint identity 主键、timestamptz、枚举 text+CHECK）。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Type

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from huntai.core.db import utcnow


def id_pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


def created_col(*, nullable: bool = False) -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
        default=None if nullable else utcnow,
        server_default=None if nullable else func.now(),
    )


def updated_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


def enum_col(enum_cls: Type[Enum]) -> SAEnum:
    """text 枚举（native_enum=False）；CHECK 约束在 Alembic 迁移显式声明。"""
    return SAEnum(
        enum_cls,
        native_enum=False,
        values_callable=lambda c: [e.value for e in c],
        length=32,
        validate_strings=True,
    )
