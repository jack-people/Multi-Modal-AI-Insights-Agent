RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def normalize_risk(risk: str) -> str:
    value = (risk or "high").strip().lower()
    if value not in RISK_ORDER:
        return "high"
    return value


def should_auto_execute(action_risk: str, max_risk: str) -> bool:
    max_level_name = (max_risk or "").strip().lower()
    if max_level_name == "none":
        return False
    action_level = RISK_ORDER[normalize_risk(action_risk)]
    max_level = RISK_ORDER[normalize_risk(max_risk)]
    return action_level <= max_level
