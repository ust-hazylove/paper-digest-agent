from __future__ import annotations
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
from typing import List
from dateutil import parser as dtparser
from .models import Paper

ARXIV_API = "http://export.arxiv.org/api/query"

def build_query(categories: list[str], text_query: str) -> str:
    cat_part = " OR ".join([f"cat:{c}" for c in categories])
    text_part = f'all:("{text_query}")'
    return f"({cat_part}) AND ({text_part})"

def fetch_arxiv_api(categories: list[str], queries: list[str], max_results_per_query: int = 200) -> List[Paper]:
    papers: List[Paper] = []

    for q in queries:
        search_query = build_query(categories, q)
        url = (
            f"{ARXIV_API}?search_query={quote(search_query)}"
            f"&start=0&max_results={max_results_per_query}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            authors = ", ".join([
                (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
                for a in entry.findall("atom:author", ns)
            ])

            arxiv_id = None
            if "/abs/" in entry_id:
                arxiv_id = entry_id.split("/abs/")[-1]

            papers.append(Paper(
                source="arXiv",
                title=title,
                authors=authors,
                summary=summary,
                url=entry_id,
                published=dtparser.parse(published).isoformat() if published else "",
                arxiv_id=arxiv_id
            ))

    return papers
