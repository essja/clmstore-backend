"""
CLMStore — Generic Base Repository
Implements general CRUD database operations asynchronously.
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get(self, id: Any) -> Optional[T]:
        """Fetch a record by primary key."""
        result = await self.db.execute(select(self.model).filter(self.model.id == id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Fetch all records with optional offset and limit."""
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, obj_in: Any) -> T:
        """Create and persist a new record."""
        self.db.add(obj_in)
        await self.db.flush()  # Populate id without committing yet
        return obj_in

    async def update(self, db_obj: T, obj_in: Union[dict, Any]) -> T:
        """Update an existing record with new fields."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        self.db.add(db_obj)
        await self.db.flush()
        return db_obj

    async def delete(self, id: Any) -> Optional[T]:
        """Remove a record by id."""
        obj = await self.get(id)
        if obj:
            await self.db.delete(obj)
            await self.db.flush()
        return obj
