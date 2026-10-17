"""Optional language model for the written summary.

If the `anthropic` package is installed and ANTHROPIC_API_KEY is set, the manager
asks the model to write the executive summary of the month-end report. Without
them, a deterministic template is used, so the project runs fully offline.
Only aggregated findings are sent to the model, never raw ledger data.
"""
import os

MODEL = os.environ.get("FINANCE_TEAM_MODEL", "claude-sonnet-5-5")


def available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def write_summary(period: str, results, approved, rejected) -> str:
    if available():
        try:
            return _llm_summary(period, results, approved, rejected)
        except Exception as exc:  # network or API problems must not stop the close
            return _template_summary(period, results, approved, rejected) + f"\n\n_(LLM summary unavailable: {exc})_"
    return _template_summary(period, results, approved, rejected)


def _template_summary(period, results, approved, rejected) -> str:
    total = sum(len(r.findings) for r in results)
    high = sum(1 for r in results for f in r.findings if f.severity == "high")
    approved_txt = "1 was" if len(approved) == 1 else f"{len(approved)} were"
    open_txt = "1 remains" if len(rejected) == 1 else f"{len(rejected)} remain"
    return (f"Month-end checks for {period} raised {total} exceptions ({high} high severity). "
            f"{approved_txt} approved by a reviewer and {open_txt} open for correction "
            "before the books are closed.")


def _llm_summary(period, results, approved, rejected) -> str:
    import anthropic

    lines = [f"- [{f.severity}] {f.agent}: {f.title}. {f.detail}" for r in results for f in r.findings]
    prompt = (
        f"You are the finance manager closing the books for {period}. Write a short executive summary "
        "(max 120 words, plain business English, no bullet points) of these month-end exceptions. "
        f"{len(approved)} were approved by a reviewer, {len(rejected)} remain open.\n\n" + "\n".join(lines)
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=400, messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text.strip()
