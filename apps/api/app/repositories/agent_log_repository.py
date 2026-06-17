from app.db.models.agent_log import AgentLog
from app.repositories.base_repository import BaseRepository


class AgentLogRepository(BaseRepository[AgentLog]):
    model = AgentLog
