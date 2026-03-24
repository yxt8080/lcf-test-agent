from __future__ import annotations

from local_test_agent.models import ScenarioDescriptor
from local_test_agent.store.database import LocalDatabase


class ScenarioIndexService:
    def __init__(self, database: LocalDatabase) -> None:
        self.database = database

    def search(self, query: str, limit: int = 8) -> list[ScenarioDescriptor]:
        if not query.strip():
            return []
        return self.database.search_scenarios(query, limit=limit)

    def get_by_ids(self, scenario_ids: list[str]) -> list[ScenarioDescriptor]:
        return self.database.list_scenarios(scenario_ids)

