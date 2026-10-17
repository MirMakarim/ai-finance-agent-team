"""Manager agent: plans the month-end run, delegates to specialists and routes exceptions."""
from dataclasses import dataclass, field

from . import llm
from .agents import BankReconciliationAgent, InvoicePoCheckAgent, VarianceAnalysisAgent

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class RunResult:
    period: str
    results: list
    approved: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    summary: str = ""


class ManagerAgent:
    name = "Manager agent"

    def __init__(self, sql, memory, period: str, reviewer):
        self.sql, self.memory, self.period, self.reviewer = sql, memory, period, reviewer
        self.team = [InvoicePoCheckAgent, BankReconciliationAgent, VarianceAnalysisAgent]

    def plan(self) -> list:
        """Order of work: invoices first, then cash, then budget (variance uses checked invoices)."""
        return [agent_cls(self.sql, self.memory, self.period) for agent_cls in self.team]

    def run(self, log=print) -> RunResult:
        log(f"[{self.name}] Closing period {self.period}. Delegating to {len(self.team)} specialists.")
        results = []
        for agent in self.plan():
            result = agent.run()
            log(f"  -> {agent.name}: {result.summary}")
            results.append(result)

        # Route every exception that needs a decision to the human reviewer, most severe first
        queue = sorted((f for r in results for f in r.findings if f.needs_approval),
                       key=lambda f: (SEVERITY_ORDER[f.severity], -abs(f.amount)))
        log(f"[{self.name}] {len(queue)} items flagged for human approval.")
        run = RunResult(self.period, results)
        for finding in queue:
            decision, reason = self.reviewer.review(finding)
            if decision == "approve":
                run.approved.append((finding, reason))
                self.memory.remember_approval(finding.key, reason, self.period)
            else:
                run.rejected.append((finding, reason))
        self.memory.save()
        run.summary = llm.write_summary(self.period, results, run.approved, run.rejected)
        return run
