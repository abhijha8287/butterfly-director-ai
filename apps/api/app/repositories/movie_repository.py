from uuid import UUID

from sqlalchemy import select

from app.db.models.movie import Movie
from app.repositories.base_repository import BaseRepository


class MovieRepository(BaseRepository[Movie]):
    model = Movie

    async def get_by_branch_id(self, branch_id: UUID) -> Movie | None:
        stmt = select(Movie).where(Movie.branch_id == branch_id, Movie.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
