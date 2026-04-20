import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from tavily import TavilyClient

SEARCH_QUERIES = [
    "{company} ESG rating climate sustainability score",
    "{company} latest news 2025 developments",
    "{company} financial performance revenue profit",
    "{company} carbon emissions net zero climate risk",
    "{company} green investment renewable energy strategy",
    "{company} regulatory compliance climate policy",
]

TRUSTED_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "sec.gov", "epa.gov", "iea.org", "msci.com",
    "sustainalytics.com", "cdp.net", "unfccc.int",
]

CACHE_TTL_HOURS = 24
CHROMA_BASE = "https://api.trychroma.com/api/v2"


def simple_embedding(text, dim=384):
    """Deterministic pseudo-embedding from text hash — no ML library needed."""
    import hashlib, math
    vec = []
    for i in range(dim):
        h = int(hashlib.md5((text + str(i)).encode()).hexdigest(), 16)
        vec.append((h % 10000) / 10000.0 - 0.5)
    norm = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x / norm for x in vec]


class ChromaCloudClient:
    def __init__(self, api_key, tenant, database):
        self.headers = {
            "x-chroma-token": api_key,
            "Content-Type": "application/json",
        }
        self.base = "{}/tenants/{}/databases/{}/collections".format(CHROMA_BASE, tenant, database)

    def get_or_create_collection(self, name):
        r = requests.get("{}/{}".format(self.base, name), headers=self.headers)
        if r.status_code == 200:
            return r.json()["id"]
        r = requests.post(self.base, headers=self.headers, json={"name": name})
        r.raise_for_status()
        return r.json()["id"]

    def upsert(self, collection_id, ids, documents, metadatas):
        embeddings = [simple_embedding(doc[:200]) for doc in documents]
        url = "{}/{}/upsert".format(self.base, collection_id)
        r = requests.post(url, headers=self.headers, json={
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "embeddings": embeddings,
        })
        r.raise_for_status()

    def get(self, collection_id, where=None):
        url = "{}/{}/get".format(self.base, collection_id)
        body = {"include": ["documents", "metadatas"]}
        if where:
            body["where"] = where
        r = requests.post(url, headers=self.headers, json=body)
        r.raise_for_status()
        return r.json()

    def count(self, collection_id):
        url = "{}/{}/count".format(self.base, collection_id)
        r = requests.get(url, headers=self.headers)
        r.raise_for_status()
        return r.json()


class ClimateResearcher:
    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self.chroma = ChromaCloudClient(
            api_key=os.getenv("CHROMA_API_KEY"),
            tenant=os.getenv("CHROMA_TENANT"),
            database=os.getenv("CHROMA_DATABASE"),
        )
        self.collection_id = self.chroma.get_or_create_collection("climate_research")

    def research_company(self, company_name, progress_callback=None, force_refresh=False):
        if not force_refresh:
            cached = self._load_from_cache(company_name)
            if cached:
                if progress_callback:
                    progress_callback(1.0, "✅ Loaded from Chroma cache ({})".format(cached["cached_at"][:16]))
                return cached

        all_results, seen_urls = [], set()
        total = len(SEARCH_QUERIES)
        for i, template in enumerate(SEARCH_QUERIES):
            query = template.format(company=company_name)
            if progress_callback:
                progress_callback(i / total, "🔎 {}...".format(query[:60]))
            try:
                response = self.tavily.search(query, max_results=4, search_depth="advanced")
                for r in response.get("results", []):
                    url = r.get("url", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        r["is_trusted"] = any(d in url for d in TRUSTED_DOMAINS)
                        all_results.append(r)
            except Exception as e:
                print("Query failed: {}".format(e))

        if progress_callback:
            progress_callback(0.9, "💾 Storing in Chroma Cloud...")

        now_str = datetime.now().isoformat()
        self._store(company_name, all_results, now_str)

        if progress_callback:
            progress_callback(1.0, "✅ Research complete.")
        return {"results": all_results, "from_cache": False, "cached_at": now_str}

    def _load_from_cache(self, company_name):
        try:
            res = self.chroma.get(self.collection_id, where={"company": company_name})
            if not res.get("documents"):
                return None
            cached_at_str = res["metadatas"][0].get("cached_at", "")
            if cached_at_str:
                cached_dt = datetime.fromisoformat(cached_at_str)
                if datetime.now() - cached_dt > timedelta(hours=CACHE_TTL_HOURS):
                    return None
            results = []
            for doc, meta in zip(res["documents"], res["metadatas"]):
                results.append({
                    "content":    doc,
                    "url":        meta.get("url", ""),
                    "title":      meta.get("title", ""),
                    "score":      float(meta.get("score", 0)),
                    "is_trusted": meta.get("is_trusted", "False") == "True",
                    "query_used": meta.get("query_used", ""),
                })
            return {"results": results, "from_cache": True, "cached_at": cached_at_str}
        except Exception:
            return None

    def _store(self, company_name, results, cached_at):
        docs, ids, metas = [], [], []
        for r in results:
            content = r.get("content", "").strip()
            if not content:
                continue
            uid = hashlib.md5(r.get("url", content[:50]).encode()).hexdigest()
            docs.append(content)
            ids.append(uid)
            metas.append({
                "company":    company_name,
                "url":        r.get("url", ""),
                "title":      r.get("title", ""),
                "score":      float(r.get("score", 0)),
                "is_trusted": str(r.get("is_trusted", False)),
                "cached_at":  cached_at,
                "query_used": r.get("query_used", ""),
            })
        if docs:
            self.chroma.upsert(self.collection_id, ids, docs, metas)
