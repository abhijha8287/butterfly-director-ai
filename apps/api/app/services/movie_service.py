from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.movie import Movie
from app.repositories.branch_repository import BranchRepository
from app.repositories.movie_repository import MovieRepository
from app.schemas.movie import MovieCreate, MovieUpdate


class MovieService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MovieRepository(session)
        self.branch_repo = BranchRepository(session)

    async def create(self, data: MovieCreate) -> Movie:
        await self.branch_repo.get_or_404(data.branch_id)
        existing = await self.repo.get_by_branch_id(data.branch_id)
        if existing is not None:
            raise ConflictError(f"Branch {data.branch_id} already has a movie")

        movie = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return movie

    async def get(self, movie_id: UUID) -> Movie:
        return await self.repo.get_or_404(movie_id)

    async def get_by_branch(self, branch_id: UUID) -> Movie:
        movie = await self.repo.get_by_branch_id(branch_id)
        if movie is None:
            raise NotFoundError(f"Branch {branch_id} has no movie yet")
        return movie

    async def update(self, movie_id: UUID, data: MovieUpdate) -> Movie:
        movie = await self.repo.get_or_404(movie_id)
        updates = data.model_dump(exclude_unset=True)
        movie = await self.repo.update(movie, **updates)
        await self.session.commit()
        return movie
