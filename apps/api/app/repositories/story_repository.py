from app.db.models.story import Story
from app.repositories.base_repository import BaseRepository


class StoryRepository(BaseRepository[Story]):
    model = Story
