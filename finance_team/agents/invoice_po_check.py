from .base import Agent, AgentResult, Finding

DEFAULT_PRICE_TOLERANCE_PCT = 2.0


class InvoicePoCheckAgent(Agent):
    """Two-way match: every invoice must reference a PO line with matching price and quantity."""

    name = "Invoice-to-PO check"
    role = "Matches invoices to purchase order lines and flags price, quantity and duplicate issues."

    def run(self) -> AgentResult:
        invoices = self.sql(
            """
            SELECT i.invoice_id, i.vendor_id, i.vendor_invoice_no, i.po_number, i.po_line,
                   i.quantity AS inv_qty, i.unit_price AS inv_price, i.amount,
                   p.quantity AS po_qty, p.unit_price AS po_price
            FROM   invoices i
            LEFT JOIN purchase_orders p ON p.po_number = i.po_number AND p.po_line = i.po_line
            WHERE  substr(i.invoice_date, 1, 7) = ?
            """,
            (self.period,),
        )
        findings = []
        for inv in invoices:
            if inv["po_number"] is None or inv["po_qty"] is None:
                findings.append(Finding(self.name, f"nopo:{inv['invoice_id']}", "high",
                                        f"{inv['invoice_id']} has no purchase order",
                                        f"Vendor {inv['vendor_id']} invoiced {inv['amount']:,.2f} without a PO reference.",
                                        inv["amount"]))
                continue
            tol = self.memory.vendor_rule(inv["vendor_id"], "price_tolerance_pct", DEFAULT_PRICE_TOLERANCE_PCT)
            diff_pct = (inv["inv_price"] - inv["po_price"]) / inv["po_price"] * 100
            if abs(diff_pct) > tol:
                impact = round((inv["inv_price"] - inv["po_price"]) * inv["inv_qty"], 2)
                findings.append(Finding(self.name, f"price:{inv['invoice_id']}", "high" if impact > 500 else "medium",
                                        f"{inv['invoice_id']} price {diff_pct:+.1f}% vs PO",
                                        f"PO {inv['po_number']}: invoiced {inv['inv_price']:.2f}, ordered {inv['po_price']:.2f} "
                                        f"(tolerance {tol:.1f}%).", impact))
            if inv["inv_qty"] > inv["po_qty"]:
                extra = inv["inv_qty"] - inv["po_qty"]
                findings.append(Finding(self.name, f"qty:{inv['invoice_id']}", "medium",
                                        f"{inv['invoice_id']} quantity above PO",
                                        f"PO {inv['po_number']}: invoiced {inv['inv_qty']}, ordered {inv['po_qty']} (+{extra}).",
                                        round(extra * inv["inv_price"], 2)))

        dups = self.sql(
            """
            SELECT vendor_id, vendor_invoice_no, COUNT(*) AS n, GROUP_CONCAT(invoice_id) AS ids, MAX(amount) AS amount
            FROM   invoices
            WHERE  substr(invoice_date, 1, 7) = ?
            GROUP BY vendor_id, vendor_invoice_no
            HAVING COUNT(*) > 1
            """,
            (self.period,),
        )
        for d in dups:
            findings.append(Finding(self.name, f"dup:{d['vendor_id']}:{d['vendor_invoice_no']}", "high",
                                    f"Possible duplicate invoice {d['vendor_invoice_no']}",
                                    f"Booked {d['n']} times as {d['ids']}.", d["amount"]))

        findings = [f for f in findings if self.keep(f)]
        return AgentResult(self.name, f"Checked {len(invoices)} invoices, {len(findings)} exceptions.",
                           findings, checked=len(invoices))
