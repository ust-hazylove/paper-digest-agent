from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from .ranker import Ranked

def render_digest(items: List[Ranked]) -> str:
    now = datetime.now(timezone.utc).astimezone()
    lines = []
    lines.append(f"Daily Paper Digest ({now.strftime('%Y-%m-%d %H:%M %Z')})")
    lines.append("")
    if not items:
        lines.append("No high-relevance new papers found today.")
        return "\n".join(lines)

    for i, r in enumerate(items, 1):
        p = r.paper
        lines.append(f"{i}. [{r.score:.1f}/5] {p.title}")
        lines.append(f"   Authors: {p.authors}")
        lines.append(f"   Link: {p.url}")
        lines.append(f"   Why relevant: {r.reason}")
        lines.append(f"   Takeaway: {r.takeaway}")
        lines.append("")
    return "\n".join(lines)
