"""
Microsoft Agent Framework (MAF) GA 1.0 → AgentTrace adapter.
This is an intentional stub — MAF GA 1.0 released April 2026 and the
real trace output format is not yet confirmed.
"""
from ..models.trace import AgentTrace


def adapt(raw: dict) -> AgentTrace:
    """
    MAF GA 1.0 adapter — stub pending real trace format confirmation.
    Replace this implementation once a real MAF trace is available.
    See: https://github.com/harinarayn/agent-trace-intelligence/issues (track here)
    """
    raise NotImplementedError(
        "MAF adapter is not yet implemented. "
        "MAF GA 1.0 released April 2026 — real trace format not yet confirmed. "
        "Pass your trace directly as AgentTrace JSON instead, or contribute "
        "the MAF mapping at https://github.com/harinarayn/agent-trace-intelligence"
    )
