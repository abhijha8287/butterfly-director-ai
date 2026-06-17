from app.db.models.prompt_history import PromptHistory
from app.repositories.base_repository import BaseRepository


class PromptHistoryRepository(BaseRepository[PromptHistory]):
    model = PromptHistory
