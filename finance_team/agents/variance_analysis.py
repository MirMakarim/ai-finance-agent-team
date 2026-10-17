from .base import Agent, AgentResult, Finding

THRESHOLD_PCT = 10.0


class VarianceAnalysisAgent(Agent):
    """Compares actual spend with budget per cost center and explains the drivers."""

    name = "Variance analysis"
    role = "Compares budget with actuals per cost center and names the vendors behind each deviation."

    def run(self) -> AgentResult:
        rows = self.sql(
            """
            WITH actual AS (
                SELECT p.cost_center, SUM(i.amount) AS actual
                FROM   invoices i
                JOIN   purchase_orders p ON p.po_number = i.po_number AND p.po_line = i.po_line
                WHERE  substr(i.invoice_date, 1, 7) = ?
                GROUP BY p.cost_center
            )
            SELECT b.cost_center, b.budget_amount AS budget, COALESCE(a.actual, 0) AS actual
            FROM   budget b
            LEFT JOIN actual a ON a.cost_center = b.cost_center
            WHERE  b.period = ?
            ORDER BY b.cost_center
            """,
            (self.period, self.period),
        )
        findings = []
        for r in rows:
            var = r["actual"] - r["budget"]
            pct = var / r["budget"] * 100 if r["budget"] else 0.0
            if pct <= THRESHOLD_PCT:
                continue
            drivers = self.sql(
                """
                SELECT v.vendor_name, SUM(i.amount) AS amount
                FROM   invoices i
                JOIN   purchase_orders p ON p.po_number = i.po_number AND p.po_line = i.po_line
                JOIN   vendors v         ON v.vendor_id = i.vendor_id
                WHERE  p.cost_center = ? AND substr(i.invoice_date, 1, 7) = ?
                GROUP BY v.vendor_name
                ORDER BY amount DESC
                LIMIT 2
                """,
                (r["cost_center"], self.period),
            )
            driver_text = ", ".join(f"{d['vendor_name']} ({d['amount']:,.0f})" for d in drivers)
            findings.append(Finding(self.name, f"var:{r['cost_center']}:{self.period}",
                                    "high" if pct > 25 else "medium",
                                    f"{r['cost_center']} {pct:+.1f}% over budget",
                                    f"Actual {r['actual']:,.0f} vs budget {r['budget']:,.0f}. Main drivers: {driver_text}.",
                                    round(var, 2)))
        findings = [f for f in findings if self.keep(f)]
        return AgentResult(self.name, f"Reviewed {len(rows)} cost centers, {len(findings)} above {THRESHOLD_PCT:.0f}% threshold.",
                           findings, checked=len(rows))
