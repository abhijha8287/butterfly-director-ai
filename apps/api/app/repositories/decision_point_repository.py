from app.db.models.decision_point import DecisionPoint
from app.repositories.base_repository import BaseRepository


class DecisionPointRepository(BaseRepository[DecisionPoint]):
    model = DecisionPoint
