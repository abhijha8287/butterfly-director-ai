from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.db.models.enums import PromptStage
from app.db.models.prompt_history import PromptHistory
from app.repositories.base_repository import BaseRepository


class PromptHistoryRepository(BaseRepository[PromptHistory]):
    model = PromptHistory

    async def list_by_storyboard_version(
        self, *, branch_id: UUID, storyboard_version_id: UUID, stage: PromptStage
    ) -> Sequence[PromptHistory]:
        """Scopes rows to one Prompt Director run: reruns are additive (no
        upsert), so a branch can have several batches of shot prompts over
        time, each tagged with the storyboard_version_id it was directed for
        in input_payload (there's no other column linking them together).
        """
        stmt = (
            select(PromptHistory)
            .where(
                PromptHistory.deleted_at.is_(None),
                PromptHistory.branch_id == branch_id,
                PromptHistory.stage == stage,
                PromptHistory.input_payload["storyboard_version_id"].astext
                == str(storyboard_version_id),
            )
            .order_by(PromptHistory.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
