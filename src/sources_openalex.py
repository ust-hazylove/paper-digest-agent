from __future__ import annotations
import requests
from typing import List
from .models import Paper

OPENALEX_URL = "https://api.openalex.org/works"

def fetch_openalex(queries: list[str], per_page: int = 100, pages_per_query: int = 2, api_key: str | None = None) -> List[Paper]:
    papers: List[Paper] = []
    headers = {"User-Agent": "paper-digest-agent/2.0"}
    params_base = {
        "sort": "publication_date:desc",
        "select": "id,display_name,publication_date,doi,primary_location,abstract_inverted_index,authorships",
        "per_page": per_page
    }
    if api_key:
        params_base["api_key"] = api_key

    for q in queries:
        for page in range(1, pages_per_query + 1):
            params = dict(params_base)
            params["search"] = q
            params["page"] = page

            r = requests.get(OPENALEX_URL, params=params, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()

            for w in data.get("results", []):
                title = (w.get("display_name") or "").strip()
                doi = w.get("doi")
                pub = w.get("publication_date") or ""
                oa_id = w.get("id")
                url = doi or oa_id or ""
                authors = ", ".join(
                    a.get("author", {}).get("display_name", "")
                    for a in w.get("authorships", [])[:8]
                    if a.get("author", {}).get("display_name")
                )

                papers.append(Paper(
                    source="OpenAlex",
                    title=title,
                    authors=authors,
                    summary="",
                    url=url,
                    published=pub,
                    doi=doi,
                    openalex_id=oa_id
                ))
    return papers
