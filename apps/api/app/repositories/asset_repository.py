from app.db.models.asset import Asset
from app.repositories.base_repository import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    model = Asset
