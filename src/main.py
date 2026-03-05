from __future__ import annotations
import argparse, json, os
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser

from .arxiv import fetch_from_feeds, Paper
from .store import PaperStore
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

def keyword_prefilter(p: Paper, keywords: list[str]) -> bool:
    hay = f"{p.title}\n{p.summary}".lower()
    return any(k.lower() in hay for k in keywords)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))
    hours_back = int(cfg.get("hours_back", 26))
    max_candidates = int(cfg.get("max_candidates", 120))
    top_n = int(cfg.get("top_n", 15))
    keywords = cfg.get("keywords", [])
    feeds = cfg["arxiv"]["rss_feeds"]

    openai_key = os.environ["OPENAI_API_KEY"]
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    mail_to = os.environ["MAIL_TO"]
    mail_from = os.environ["MAIL_FROM"]

    store = PaperStore("data/papers.db")

    # 1) fetch
    all_papers = fetch_from_feeds(feeds)

    # 2) time filter + prefilter + dedup
    fresh = [p for p in all_papers if within_hours(p.published, hours_back)]
    rough = [p for p in fresh if keyword_prefilter(p, keywords)]

    # stable ordering: newest first
    rough.sort(key=lambda p: p.published, reverse=True)

    candidates: list[Paper] = []
    for p in rough:
        key = store.make_key(p)
        if store.is_seen(key):
            continue
        candidates.append(p)
        if len(candidates) >= max_candidates:
            break

    # 3) LLM rank
    ranked = rank_papers(candidates, keywords, openai_key)

    # 4) choose top_n and mark seen
    chosen = [r for r in ranked if r.score >= 2.5][:top_n]
    for r in chosen:
        key = store.make_key(r.paper)
        store.mark_seen(key, datetime.now(timezone.utc).isoformat())

    store.close()

    # 5) email
    body = render_digest(chosen)
    subject = f"Daily Paper Digest ({datetime.now().strftime('%Y-%m-%d')})"
    send_email(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        mail_from=mail_from,
        mail_to=mail_to,
        subject=subject,
        body=body,
    )

if __name__ == "__main__":
    main()
