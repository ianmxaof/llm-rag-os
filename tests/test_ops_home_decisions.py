"""Deepen/Fade moves Open bullets in DECISIONS.md without wiping other sections."""
from pathlib import Path

from src.app.ops_home import (
    move_open_to,
    open_belief_titles,
    parse_decisions_sections,
    parse_digest_briefing_actions,
    parse_recall_evals,
    write_recall_evals,
)

SAMPLE = """---
type: second-brain-decisions
updated: 2026-10-25T04:00:02Z
---

# Second-brain decisions

## Deepen

- **vault para hygiene 2026-09-12** — keep PARA clean.

## Fade

_None yet._

## Open

- **Vault corpora indexed but nervous system thin** — still open. Copy this bullet into Deepen (work it) or Fade (stop proposing).
- **RAG recall ready for operator queries** — still open. Copy this bullet into Deepen (work it) or Fade (stop proposing).

## Recall evals

| # | Question | Pass? | Notes | When (UTC) |
|---|----------|-------|-------|------------|
| 1 | What is PARA hygiene? | yes | hit vault note | 2026-10-28T12:00Z |
| 2 | _(second)_ |  |  |  |
| 3 | _(third)_ |  |  |  |
"""


def test_parse_open_titles():
    sections = parse_decisions_sections(SAMPLE)
    titles = [t for t, _ in open_belief_titles(sections)]
    assert "Vault corpora indexed but nervous system thin" in titles
    assert len(sections["Deepen"]) == 1


def test_move_open_to_deepen():
    updated = move_open_to(
        SAMPLE,
        "Vault corpora indexed but nervous system thin",
        "Deepen",
    )
    sections = parse_decisions_sections(updated)
    open_titles = [t for t, _ in open_belief_titles(sections)]
    assert "Vault corpora indexed but nervous system thin" not in open_titles
    assert any("nervous system thin" in line for line in sections["Deepen"])
    assert any("RAG recall" in line for line in sections["Open"])
    assert "vault para hygiene" in "".join(sections["Deepen"])


def test_move_open_to_fade():
    updated = move_open_to(
        SAMPLE,
        "RAG recall ready for operator queries",
        "Fade",
    )
    sections = parse_decisions_sections(updated)
    assert any("RAG recall" in line for line in sections["Fade"])
    assert "RAG recall ready for operator queries" not in [
        t for t, _ in open_belief_titles(sections)
    ]
    assert "## Recall evals" in updated
    assert "What is PARA hygiene?" in updated


def test_parse_digest_briefing_actions():
    digest = """# Evening digest

## Briefing

- 🔴 **Review** — Still open — deepen or fade: «Sell lanes» → `3-Resources/second-brain/DECISIONS.md`
- 🟡 **Optional** — Brainstorm note: «Graph» → `0-Inbox/thinktank-corpus-x.md`
- ⚫ **Ignore** — faded noise → `0-Inbox/skip.md`
"""
    actions = parse_digest_briefing_actions(digest)
    assert len(actions) == 2
    assert actions[0]["path"].endswith("DECISIONS.md")
    assert "Sell" in actions[0]["chat_prompt"] or "lanes" in actions[0]["chat_prompt"].lower()


def test_write_recall_evals(tmp_path: Path):
    vault = tmp_path / "notes"
    sb = vault / "3-Resources" / "second-brain"
    sb.mkdir(parents=True)
    (sb / "DECISIONS.md").write_text(SAMPLE, encoding="utf-8")
    rows = parse_recall_evals(SAMPLE)
    rows[1]["question"] = "Where is DECISIONS.md?"
    rows[1]["pass"] = "yes"
    rows[1]["notes"] = "top hit"
    rows[1]["when"] = "2026-10-28T13:00Z"
    write_recall_evals(vault, rows)
    text = (sb / "DECISIONS.md").read_text(encoding="utf-8")
    assert "Where is DECISIONS.md?" in text
    assert "top hit" in text
    assert "## Deepen" in text
