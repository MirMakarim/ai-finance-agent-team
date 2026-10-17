"""Tests for the finance agents. Run: python -m unittest discover tests"""
import tempfile
import unittest
from pathlib import Path

from finance_team import db
from finance_team.agents import BankReconciliationAgent, InvoicePoCheckAgent, VarianceAnalysisAgent
from finance_team.approval import PolicyReviewer
from finance_team.manager import ManagerAgent
from finance_team.memory import Memory

PERIOD = "2025-11"


class FinanceTeamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.sql = db.SqlTool(db.build(PERIOD, path=self.tmp / "finance.db"))
        self.memory = Memory(self.tmp / "memory.json")

    def keys(self, agent_cls):
        return {f.key.split(":")[0] for f in agent_cls(self.sql, self.memory, PERIOD).run().findings}

    def test_invoice_check_finds_planted_issues(self):
        findings = InvoicePoCheckAgent(self.sql, self.memory, PERIOD).run().findings
        titles = " ".join(f.title for f in findings)
        self.assertIn("INV-0005 price", titles)
        self.assertIn("INV-0018 price", titles)
        self.assertIn("INV-0024 quantity", titles)
        self.assertIn("INV-0042 has no purchase order", titles)
        self.assertIn("duplicate", titles)

    def test_vendor_tolerance_from_memory(self):
        # INV-0005 is from V104 and is 8% above PO; a 10% vendor tolerance in memory must clear it
        self.memory.data["vendor_rules"]["V104"] = {"price_tolerance_pct": 10.0}
        findings = InvoicePoCheckAgent(self.sql, self.memory, PERIOD).run().findings
        self.assertFalse(any(f.title.startswith("INV-0005 price") for f in findings))

    def test_bank_reconciliation(self):
        self.assertEqual(self.keys(BankReconciliationAgent), {"nobank", "amount", "noledger"})

    def test_variance_flags_over_budget_cost_centers(self):
        findings = VarianceAnalysisAgent(self.sql, self.memory, PERIOD).run().findings
        self.assertEqual({f.title.split()[0] for f in findings}, {"CC-LOG", "CC-IT"})

    def test_sql_tool_is_read_only(self):
        with self.assertRaises(PermissionError):
            self.sql("DELETE FROM invoices")
        with self.assertRaises(PermissionError):
            self.sql("SELECT 1; DROP TABLE invoices")

    def test_approved_items_are_remembered(self):
        first = ManagerAgent(self.sql, self.memory, PERIOD, PolicyReviewer()).run(log=lambda *_: None)
        self.assertEqual(len(first.approved), 1)
        second = ManagerAgent(self.sql, Memory(self.tmp / "memory.json"), PERIOD, PolicyReviewer()).run(log=lambda *_: None)
        self.assertEqual(len(second.approved), 0)
        self.assertEqual(len(second.rejected), len(first.rejected))


if __name__ == "__main__":
    unittest.main()
