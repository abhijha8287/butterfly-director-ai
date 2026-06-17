from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.timeline import Timeline
from app.repositories.branch_repository import BranchRepository
from app.repositories.movie_repository import MovieRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.story_repository import StoryRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.common import Page
from app.schemas.timeline import BranchTreeNode, TimelineCreate, TimelineRead, TimelineTree, TimelineUpdate


class TimelineService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TimelineRepository(session)
        self.project_repo = ProjectRepository(session)
        self.story_repo = StoryRepository(session)
        self.branch_repo = BranchRepository(session)
        self.movie_repo = MovieRepository(session)

    async def create(self, data: TimelineCreate) -> Timeline:
        await self.project_repo.get_or_404(data.project_id)
        if data.story_id is not None:
            await self.story_repo.get_or_404(data.story_id)
        timeline = await self.repo.create(**data.model_dump())
        await self.session.commit()
        return timeline

    async def get(self, timeline_id: UUID) -> Timeline:
        return await self.repo.get_or_404(timeline_id)

    async def list_for_project(
        self, project_id: UUID, cursor: str | None, limit: int
    ) -> Page[Timeline]:
        items, next_cursor = await self.repo.list_paginated(
            cursor=cursor, limit=limit, project_id=project_id
        )
        return Page(items=list(items), next_cursor=next_cursor)

    async def update(self, timeline_id: UUID, data: TimelineUpdate) -> Timeline:
        timeline = await self.repo.get_or_404(timeline_id)
        updates = data.model_dump(exclude_unset=True)
        timeline = await self.repo.update(timeline, **updates)
        await self.session.commit()
        return timeline

    async def delete(self, timeline_id: UUID) -> None:
        timeline = await self.repo.get_or_404(timeline_id)
        await self.repo.soft_delete(timeline)
        await self.session.commit()

    async def get_tree(self, timeline_id: UUID) -> TimelineTree:
        timeline = await self.repo.get_or_404(timeline_id)
        branches = await self.branch_repo.list_by_timeline(timeline_id)

        nodes: list[BranchTreeNode] = []
        for branch in branches:
            movie = await self.movie_repo.get_by_branch_id(branch.id)
            nodes.append(
                BranchTreeNode(
                    id=branch.id,
                    parent_branch_id=branch.parent_branch_id,
                    name=branch.name,
                    summary=branch.summary,
                    decision_summary=branch.decision_summary,
                    depth=branch.depth,
                    position=branch.position,
                    status=branch.status.value,
                    is_canonical=branch.is_canonical,
                    butterfly_score=branch.butterfly_score,
                    probability=branch.probability,
                    confidence_score=branch.confidence_score,
                    stability_explanation=branch.stability_explanation,
                    movie_id=movie.id if movie else None,
                    movie_status=movie.status.value if movie else None,
                )
            )

        return TimelineTree(timeline=TimelineRead.model_validate(timeline), branches=nodes)
