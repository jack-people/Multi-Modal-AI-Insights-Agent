from typing import Any


class HarnessRunner:
    def run_case(self, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
