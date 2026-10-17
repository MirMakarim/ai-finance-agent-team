"""Human-in-the-loop review of flagged items."""


class ConsoleReviewer:
    """Asks a person in the terminal to approve or reject each flagged item."""

    def review(self, finding):
        print(f"\n[{finding.severity.upper()}] {finding.agent}: {finding.title}")
        print(f"    {finding.detail}  (impact {finding.amount:,.2f})")
        while True:
            answer = input("    Approve? [y]es / [n]o: ").strip().lower()
            if answer in ("y", "yes", "n", "no"):
                break
        reason = input("    Reason (optional): ").strip() or "-"
        return ("approve" if answer.startswith("y") else "reject"), reason


class PolicyReviewer:
    """Non-interactive reviewer for demos and tests.

    Auto-approves low-severity items (for example small bank fees) and leaves
    everything else open, the way a cautious reviewer would.
    """

    def review(self, finding):
        if finding.severity == "low":
            return "approve", "Auto-approved by policy: low severity"
        return "reject", "Open: needs correction before close"
