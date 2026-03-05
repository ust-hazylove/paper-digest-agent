from __future__ import annotations
import feedparser
from dateutil import parser as dtparser
from dataclasses import dataclass
from typing import Iterable, List, Optional
import re

@dataclass
class Paper:
    source: str
    title: str
    authors: str
    summary: str
    url: str
    published: str  # ISO string
    arxiv_id: Optional[str] = None

_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^?#]+)")

def fetch_rss(url: str) -> List[Paper]:
    feed = feedparser.parse(url)
    papers: List[Paper] = []
    for e in feed.entries:
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        summary = (e.get("summary") or "").strip()
        published = e.get("published") or e.get("updated") or ""
        authors = ""
        if "authors" in e and e.authors:
            authors = ", ".join([a.get("name", "").strip() for a in e.authors if a.get("name")])
        else:
            authors = (e.get("author") or "").strip()

        arxiv_id = None
        m = _ARXIV_ID_RE.search(link)
        if m:
            arxiv_id = m.group(1)

        # Normalize published to ISO if possible
        iso_pub = published
        try:
            iso_pub = dtparser.parse(published).isoformat()
        except Exception:
            pass

        papers.append(Paper(
            source="arXiv",
            title=title,
            authors=authors,
            summary=summary,
            url=link,
            published=iso_pub,
            arxiv_id=arxiv_id
        ))
    return papers

def fetch_from_feeds(feed_urls: Iterable[str]) -> List[Paper]:
    out: List[Paper] = []
    for u in feed_urls:
        out.extend(fetch_rss(u))
    return out
