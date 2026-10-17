"""Shared building blocks for all agents."""
from dataclasses import dataclass, field


@dataclass
class Finding:
    agent: str
    key: str                 # stable id, used by memory to recognise approved exceptions
    severity: str            # "high" | "medium" | "low"
    title: str
    detail: str
    amount: float = 0.0
    needs_approval: bool = True


@dataclass
class AgentResult:
    agent: str
    summary: str
    findings: list = field(default_factory=list)
    checked: int = 0


class Agent:
    """A specialist with a role, a set of tools and access to shared memory."""

    name = "agent"
    role = ""

    def __init__(self, sql, memory, period: str):
        self.sql = sql          # tool: read-only SQL
        self.memory = memory    # tool: shared memory
        self.period = period

    def run(self) -> AgentResult:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def keep(self, finding: Finding) -> bool:
        """Drop findings a human approved in an earlier run."""
        return not self.memory.is_approved(finding.key)
