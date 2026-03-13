from __future__ import annotations
import argparse
import json
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser

from .models import Paper
from .sources_arxiv_api import fetch_arxiv_api
from .sources_openalex import fetch_openalex
from .ranker import rank_papers
from .template import render_digest
from .emailer import send_email

def within_hours(iso: str, hours: int) -> bool:
    try:
        t = dtparser.parse(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return t >= datetime.now(timezone.utc) - timedelta(hours=hours)

def norm_title(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return t

def dedup_papers(papers: list[Paper]) -> list[Paper]:
    seen = set()
    out = []
    for p in papers:
        key = None
        if p.arxiv_id:
            key = f"arxiv:{p.arxiv_id}"
        elif p.doi:
            key = f"doi:{p.doi.lower()}"
        else:
            key = "title:" + hashlib.sha256(norm_title(p.title).encode()).hexdigest()

        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out

def pre_score(p: Paper, keywords: list[str]) -> float:
    hay = f"{p.title} {p.summary}".lower()
    kw_hits = sum(1 for k in keywords if k.lower() in hay)
    recency = 1.0
    if p.source == "arXiv":
        source_bonus = 1.0
    else:
        source_bonus = 0.85
    return kw_hits * 0.7 + recency * 0.2 + source_bonus * 0.1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))

    hours_back = int(cfg.get("hours_back", 48))
    target_candidates = int(cfg.get("target_candidates", 1800))
    pre_rank_top_k = int(cfg.get("pre_rank_top_k", 150))
    top_n = int(cfg.get("top_n", 15))
    keywords = cfg.get("queries", [])

    arxiv_cfg = cfg["arxiv"]
    openalex_cfg = cfg["openalex"]

    collected: list[Paper] = []

    # arXiv API
    collected.extend(
        fetch_arxiv_api(
            categories=arxiv_cfg["categories"],
            queries=cfg["queries"],
            max_results_per_query=arxiv_cfg.get("max_results_per_query", 200)
        )
    )

    # OpenAlex
    if openalex_cfg.get("enabled", True):
        collected.extend(
            fetch_openalex(
                queries=cfg["queries"],
                per_page=openalex_cfg.get("per_page", 100),
                pages_per_query=openalex_cfg.get("pages_per_query", 2),
                api_key=os.getenv("OPENALEX_API_KEY")
            )
        )

    # time filter
    fresh = [p for p in collected if within_hours(p.published, hours_back)]

    # dedup
    fresh = dedup_papers(fresh)

    # pre-rank
    scored = [(pre_score(p, cfg.get("keywords", [])), p) for p in fresh]
    scored.sort(key=lambda x: x[0], reverse=True)

    # cap to target
    candidates = [p for _, p in scored[:target_candidates]]

    # llm stage only on top 150
    llm_pool = [p for _, p in scored[:pre_rank_top_k]]
    ranked = rank_papers(llm_pool, cfg.get("keywords", []))

    chosen = ranked[:top_n]

    body = render_digest(chosen)
    subject = f"Daily Paper Digest ({datetime.now().strftime('%Y-%m-%d')})"

    send_email(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ["SMTP_USER"],
        smtp_pass=os.environ["SMTP_PASS"],
        mail_from=os.environ["MAIL_FROM"],
        mail_to=os.environ["MAIL_TO"],
        subject=subject,
        body=body,
    )

if __name__ == "__main__":
    main()
