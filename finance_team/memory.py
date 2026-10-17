"""Persistent memory shared by all agents.

Stores two things between runs:
- vendor rules: for example a vendor-specific price tolerance agreed with procurement
- past exceptions: items a human already approved, so they are not flagged again
"""
import json
from pathlib import Path

MEMORY_PATH = Path(__file__).resolve().parents[1] / "data" / "memory.json"

DEFAULT = {
    "vendor_rules": {
        # Freight prices may vary with fuel surcharges, so this vendor gets a wider tolerance
        "V102": {"price_tolerance_pct": 5.0, "note": "Fuel surcharge agreed in contract"}
    },
    "approved_exceptions": [],
}


class Memory:
    def __init__(self, path: Path = MEMORY_PATH):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else json.loads(json.dumps(DEFAULT))

    def vendor_rule(self, vendor_id: str, key: str, default=None):
        return self.data["vendor_rules"].get(vendor_id, {}).get(key, default)

    def is_approved(self, exception_key: str) -> bool:
        return any(e["key"] == exception_key for e in self.data["approved_exceptions"])

    def remember_approval(self, exception_key: str, reason: str, period: str):
        if not self.is_approved(exception_key):
            self.data["approved_exceptions"].append({"key": exception_key, "reason": reason, "period": period})

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))
