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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))

    # --- Config ---
    hours_back = int(cfg.get("hours_back", 26))
    max_candidates = int(cfg.get("max_candidates", 250))  # 宽召回建议更大
    top_n = int(cfg.get("top_n", 15))
    keywords = cfg.get("keywords", [])
    feeds = cfg["arxiv"]["rss_feeds"]

    # --- Email env ---
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    mail_to = os.environ["MAIL_TO"]
    mail_from = os.environ["MAIL_FROM"]

    store = PaperStore("data/papers.db")

    # 1) Fetch from RSS feeds
    all_papers = fetch_from_feeds(feeds)

    # 2) Wide recall: time filter only (no keyword prefilter)
    fresh = [p for p in all_papers if within_hours(p.published, hours_back)]

    # If too few, expand time window (RSS timestamp can be unstable)
    if len(fresh) < 30:
        fresh = [p for p in all_papers if within_hours(p.published, max(48, hours_back))]

    # Newest first
    fresh.sort(key=lambda p: p.published, reverse=True)

    # 3) Dedup and take up to max_candidates
    candidates: list[Paper] = []
    for p in fresh:
        key = store.make_key(p)
        if store.is_seen(key):
            continue
        candidates.append(p)
        if len(candidates) >= max_candidates:
            break

    # 4) Rank by LLM (OpenRouter -> DeepSeek fallback inside ranker)
    ranked = rank_papers(candidates, keywords)

    # 5) Non-empty sending strategy
    #    Prefer high relevance, but never send empty.
    HIGH_TH = 3.0
    MID_TH = 2.0

    high = [r for r in ranked if r.score >= HIGH_TH]
    mid = [r for r in ranked if MID_TH <= r.score < HIGH_TH]

    chosen = (high[:top_n] if high else (mid[:top_n] if mid else ranked[:min(top_n, 10)]))

    # Mark seen for chosen items so tomorrow won't repeat
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in chosen:
        key = store.make_key(r.paper)
        store.mark_seen(key, now_iso)

    store.close()

    # 6) Send email
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
