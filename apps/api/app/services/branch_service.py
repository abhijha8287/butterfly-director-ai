from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import MAX_BRANCHES_PER_DECISION
from app.core.exceptions import ConflictError
from app.db.models.branch import Branch
from app.repositories.branch_repository import BranchRepository
from app.repositories.timeline_repository import TimelineRepository
from app.schemas.branch import BranchCreate, BranchUpdate
from app.schemas.common import Page
from app.services.timeline_scoring_service import (
    compute_butterfly_score,
    compute_probability_confidence_explanation,
)


class BranchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BranchRepository(session)
        self.timeline_repo = TimelineRepository(session)

    async def create(self, data: BranchCreate) -> Branch:
        await self.timeline_repo.get_or_404(data.timeline_id)

        depth = 0
        if data.parent_branch_id is not None:
            parent = await self.repo.get_or_404(data.parent_branch_id)
            if parent.timeline_id != data.timeline_id:
                raise ConflictError("Parent branch does not belong to the given timeline")
            depth = parent.depth + 1

            siblings = await self.repo.list_children(data.parent_branch_id)
            if len(siblings) >= MAX_BRANCHES_PER_DECISION:
                raise ConflictError(
                    f"Decision already has {len(siblings)} branches; "
                    f"max is {MAX_BRANCHES_PER_DECISION} per the hackathon build scope"
                )

        branch = await self.repo.create(**data.model_dump(), depth=depth)
        await self._recompute_decision_group(data.timeline_id, data.parent_branch_id)
        await self.session.commit()
        await self.session.refresh(branch)
        return branch

    async def get(self, branch_id: UUID) -> Branch:
        return await self.repo.get_or_404(branch_id)

    async def list_for_timeline(
        self, timeline_id: UUID, cursor: str | None, limit: int
    ) -> Page[Branch]:
        items, next_cursor = await self.repo.list_paginated(
            cursor=cursor, limit=limit, timeline_id=timeline_id
        )
        return Page(items=list(items), next_cursor=next_cursor)

    async def update(self, branch_id: UUID, data: BranchUpdate) -> Branch:
        branch = await self.repo.get_or_404(branch_id)
        updates = data.model_dump(exclude_unset=True)
        branch = await self.repo.update(branch, **updates)

        if "decision_summary" in updates:
            await self._recompute_decision_group(branch.timeline_id, branch.parent_branch_id)

        await self.session.commit()
        await self.session.refresh(branch)
        return branch

    async def delete(self, branch_id: UUID) -> None:
        branch = await self.repo.get_or_404(branch_id)
        timeline_id, parent_branch_id = branch.timeline_id, branch.parent_branch_id
        await self._soft_delete_subtree(branch)
        await self._recompute_decision_group(timeline_id, parent_branch_id)
        await self.session.commit()

    async def _soft_delete_subtree(self, branch: Branch) -> None:
        children = await self.repo.list_children(branch.id)
        for child in children:
            await self._soft_delete_subtree(child)
        await self.repo.soft_delete(branch)

    async def _recompute_decision_group(
        self, timeline_id: UUID, parent_branch_id: UUID | None
    ) -> None:
        if parent_branch_id is None:
            siblings = await self.repo.list_roots(timeline_id)
        else:
            siblings = await self.repo.list_children(parent_branch_id)

        sibling_count = len(siblings)
        for sibling in siblings:
            sibling.butterfly_score = compute_butterfly_score(sibling, sibling_count)
            probability, confidence, explanation = compute_probability_confidence_explanation(
                sibling, sibling_count
            )
            sibling.probability = probability
            sibling.confidence_score = confidence
            sibling.stability_explanation = explanation

        await self.session.flush()
