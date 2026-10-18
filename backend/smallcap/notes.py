"""Research notes: one Markdown file per company, kept in git.

Format: a JSON front-matter block between `---` lines, then free Markdown.

    ---
    {"company_id": "ABC US", "conviction": "high", ...}
    ---
    Free-form notes from the annual report...
"""
from __future__ import annotations

import json
import re
from datetime import date

from pydantic import BaseModel, Field

from .config import NOTES_DIR

CHECKLIST = {
    "annual_report": "Read the last annual report: what drives revenue, who are the customers?",
    "fcf_one_offs": "FCF not flattered by one-offs (working capital release, asset sales, capitalised costs)",
    "roe_vs_roic": "ROE checked against ROIC: margins, or leverage and buybacks?",
    "management": "Management ownership and capital allocation record noted",
    "governance": "Governance red flags checked",
    "thesis": "Thesis in three sentences and sell trigger in one",
}

GOVERNANCE_FLAGS = {
    "related_party": "Material related-party transactions",
    "complex_structure": "Complex group or ownership structure",
    "turnover": "High turnover of CEO, CFO, directors or auditor",
    "audit_issues": "Auditor disputes, qualified opinions, restatements or late filings",
    "aggressive_targets": "Aggressive targets; pay tied to short-term earnings or share price",
    "violations": "History of securities-law or reporting violations",
}


class Note(BaseModel):
    company_id: str
    status: str = "watch"  # watch | buy | hold | sold | rejected
    conviction: str | None = None  # high | medium | low
    thesis: str = ""
    sell_trigger: str = ""
    checklist: dict[str, bool] = Field(default_factory=lambda: {k: False for k in CHECKLIST})
    governance_flags: list[str] = Field(default_factory=list)
    governance_justification: str = ""
    review_dates: list[str] = Field(default_factory=list)
    updated: str = ""
    body: str = ""

    @property
    def governance_blocked(self) -> bool:
        """Two or more flags exclude; one flag needs a written justification."""
        n = len(self.governance_flags)
        return n >= 2 or (n == 1 and not self.governance_justification.strip())


def _path(company_id: str):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", company_id).strip("_")
    return NOTES_DIR / f"{safe}.md"


def read(company_id: str) -> Note:
    path = _path(company_id)
    if not path.exists():
        return Note(company_id=company_id)
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, flags=re.S)
    if not m:
        return Note(company_id=company_id, body=text)
    meta = json.loads(m.group(1))
    return Note(**meta, body=m.group(2).strip())


def write(note: Note) -> Note:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    note.updated = date.today().isoformat()
    meta = note.model_dump(exclude={"body"})
    text = "---\n" + json.dumps(meta, indent=2, ensure_ascii=False) + "\n---\n" + note.body.strip() + "\n"
    _path(note.company_id).write_text(text, encoding="utf-8")
    return note


def read_all() -> dict[str, Note]:
    if not NOTES_DIR.exists():
        return {}
    out = {}
    for path in NOTES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, flags=re.S)
        if m:
            meta = json.loads(m.group(1))
            out[meta["company_id"]] = read(meta["company_id"])
    return out
