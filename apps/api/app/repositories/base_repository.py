from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import apply_cursor, encode_cursor

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get(self, id_: UUID) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id_, self.model.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_404(self, id_: UUID) -> ModelType:
        instance = await self.get(id_)
        if instance is None:
            raise NotFoundError(f"{self.model.__name__} {id_} not found")
        return instance

    async def list_paginated(
        self,
        *,
        cursor: str | None,
        limit: int,
        **filters: Any,
    ) -> tuple[Sequence[ModelType], str | None]:
        stmt = select(self.model).where(self.model.deleted_at.is_(None))
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)

        stmt = apply_cursor(stmt, self.model.created_at, self.model.id, cursor)
        stmt = stmt.order_by(self.model.created_at.desc(), self.model.id.desc()).limit(limit + 1)

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return rows, next_cursor

    async def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelType) -> None:
        instance.deleted_at = datetime.now(UTC)
        await self.session.flush()
