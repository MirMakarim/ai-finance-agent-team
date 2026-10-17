from datetime import date

from .base import Agent, AgentResult, Finding

MAX_DAYS_APART = 3


class BankReconciliationAgent(Agent):
    """Matches ledger payments to bank statement lines by reference, amount and date."""

    name = "Bank reconciliation"
    role = "Matches bank statement lines to ledger payments and explains every open item."

    def run(self) -> AgentResult:
        payments = self.sql(
            "SELECT payment_id, vendor_id, amount, payment_date, reference FROM ledger_payments "
            "WHERE substr(payment_date, 1, 7) = ?", (self.period,))
        # Bank lines may book a few days after month end, so the window runs into the next month
        bank = self.sql(
            "SELECT line_id, booking_date, -amount AS amount, counterparty, reference FROM bank_statement "
            "WHERE booking_date >= ? || '-01' AND booking_date < date(? || '-01', '+1 month', '+5 days')",
            (self.period, self.period))

        open_bank = {b["line_id"]: b for b in bank}
        findings, matched = [], 0
        for p in payments:
            # 1st pass: exact reference; 2nd pass: same amount within the date window
            hit = next((b for b in open_bank.values() if b["reference"] == p["reference"]), None)
            if hit is None:
                hit = next((b for b in open_bank.values()
                            if abs(b["amount"] - p["amount"]) < 0.01
                            and abs((date.fromisoformat(b["booking_date"]) - date.fromisoformat(p["payment_date"])).days)
                            <= MAX_DAYS_APART), None)
            if hit is None:
                findings.append(Finding(self.name, f"nobank:{p['payment_id']}", "high",
                                        f"{p['payment_id']} not found on bank statement",
                                        f"Ledger payment {p['amount']:,.2f} to {p['vendor_id']} on {p['payment_date']} "
                                        "has no bank booking.", p["amount"]))
                continue
            del open_bank[hit["line_id"]]
            diff = round(hit["amount"] - p["amount"], 2)
            if abs(diff) >= 0.01:
                findings.append(Finding(self.name, f"amount:{p['payment_id']}", "low",
                                        f"{p['payment_id']} differs by {diff:+,.2f}",
                                        f"Bank line {hit['line_id']} shows {hit['amount']:,.2f}, ledger {p['amount']:,.2f}. "
                                        "Likely bank fee; book to bank charges.", abs(diff)))
            else:
                matched += 1

        for b in open_bank.values():
            if b["booking_date"][:7] != self.period:
                continue   # belongs to a payment of the next period
            findings.append(Finding(self.name, f"noledger:{b['line_id']}", "high",
                                    f"Bank line {b['line_id']} has no ledger entry",
                                    f"{b['amount']:,.2f} to {b['counterparty']} ({b['reference']}) on {b['booking_date']}.",
                                    b["amount"]))

        findings = [f for f in findings if self.keep(f)]
        return AgentResult(self.name, f"Matched {matched} of {len(payments)} payments, {len(findings)} open items.",
                           findings, checked=len(payments))
