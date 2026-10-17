"""Month-end report in Markdown."""
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def write_report(run, sql_calls: int) -> Path:
    lines = [f"# Month-end report {run.period}", "",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M} by the AI finance team. {sql_calls} SQL tool calls._", "",
             "## Executive summary", "", run.summary, "",
             "## Checks", "", "| Agent | Result |", "|---|---|"]
    lines += [f"| {r.agent} | {r.summary} |" for r in run.results]

    def table(title, items):
        out = ["", f"## {title} ({len(items)})", ""]
        if not items:
            return out + ["None."]
        out += ["| Severity | Agent | Item | Impact | Reviewer note |", "|---|---|---|--:|---|"]
        out += [f"| {f.severity} | {f.agent} | {f.title} | {f.amount:,.2f} | {reason} |" for f, reason in items]
        return out

    lines += table("Open items to fix before close", run.rejected)
    lines += table("Approved exceptions", run.approved)
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"month_end_report_{run.period}.md"
    path.write_text("\n".join(lines) + "\n")
    return path
