from functools import lru_cache
from app.service.agent_runner import AgentRunner


@lru_cache
def get_agent_runner() -> AgentRunner:
    return AgentRunner()
