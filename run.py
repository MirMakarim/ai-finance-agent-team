"""Run the month-end close with the AI finance team.

    python run.py                       # interactive review in the terminal
    python run.py --auto                # non-interactive policy review (demo)
    python run.py --period 2025-11 --reset
"""
import argparse

from finance_team import db
from finance_team.approval import ConsoleReviewer, PolicyReviewer
from finance_team.manager import ManagerAgent
from finance_team.memory import MEMORY_PATH, Memory
from finance_team.report import write_report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", default="2025-11", help="month to close, YYYY-MM")
    ap.add_argument("--auto", action="store_true", help="use the policy reviewer instead of asking")
    ap.add_argument("--reset", action="store_true", help="forget earlier approvals")
    args = ap.parse_args()

    if args.reset and MEMORY_PATH.exists():
        MEMORY_PATH.unlink()
    path = db.build(args.period)
    sql = db.SqlTool(path)
    reviewer = PolicyReviewer() if args.auto else ConsoleReviewer()
    run = ManagerAgent(sql, Memory(), args.period, reviewer).run()
    report = write_report(run, sql.calls)
    print(f"\nOpen items: {len(run.rejected)} · approved: {len(run.approved)}")
    print(f"Report written to {report}")


if __name__ == "__main__":
    main()
