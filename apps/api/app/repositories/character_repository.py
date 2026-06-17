from app.db.models.character import Character
from app.repositories.base_repository import BaseRepository


class CharacterRepository(BaseRepository[Character]):
    model = Character
