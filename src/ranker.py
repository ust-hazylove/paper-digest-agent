from __future__ import annotations
from dataclasses import dataclass
from typing import List
from openai import OpenAI
from .arxiv import Paper

@dataclass
class Ranked:
    paper: Paper
    score: float
    reason: str
    takeaway: str

SYSTEM = """You are a research paper triage assistant.
Score relevance to the user's interests:
AI, Computer Vision, LLM/VLM, embodied intelligence, robotics/manipulation, intelligent manufacturing systems, digital twin, physical AI, planning/assembly, sim2real, RL.
Output JSON only.
"""

def build_user_prompt(p: Paper, keywords: List[str]) -> str:
    # keep it short; RSS summaries are sometimes long
    abstract = (p.summary or "")[:2000]
    return f"""
Title: {p.title}
Authors: {p.authors}
Published: {p.published}
Link: {p.url}
Abstract/Summary: {abstract}

Keyword hints (not strict): {", ".join(keywords[:40])}

Return JSON with fields:
score: number 0-5 (5 highest),
reason: short (<=30 words),
takeaway: 1-2 sentences, no jargon if possible.
"""

def rank_papers(papers: List[Paper], keywords: List[str], api_key: str) -> List[Ranked]:
    client = OpenAI(api_key=api_key)
    ranked: List[Ranked] = []
    for p in papers:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_user_prompt(p, keywords)}
            ],
            response_format={"type": "json_object"},
        )
        obj = resp.choices[0].message.content
        # light parse without extra deps
        import json
        data = json.loads(obj)
        ranked.append(Ranked(
            paper=p,
            score=float(data.get("score", 0)),
            reason=str(data.get("reason", "")).strip(),
            takeaway=str(data.get("takeaway", "")).strip(),
        ))
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked
