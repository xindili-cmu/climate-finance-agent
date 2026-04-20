import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from tavily import TavilyClient
import chromadb
from chromadb.utils import embedding_functions

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


class ClimateResearcher:
    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

        self.chroma_client = chromadb.CloudClient(
            api_key=os.getenv("CHROMA_API_KEY"),
            tenant=os.getenv("CHROMA_TENANT"),
            database=os.getenv("CHROMA_DATABASE"),
        )
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name="climate_research",
            embedding_function=self.ef,
        )

    def research_company(self, company_name, progress_callback=None, force_refresh=False):
        if not force_refresh:
            cached = self._load_from_cache(company_name)
            if cached:
                if progress_callback:
                    progress_callback(1.0, "✅ Loaded from cache ({})".format(cached["cached_at"][:16]))
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
        self._store_in_chroma(company_name, all_results, now_str)

        if progress_callback:
            progress_callback(1.0, "✅ Research complete.")

        return {"results": all_results, "from_cache": False, "cached_at": now_str}

    def list_cached_companies(self):
        try:
            all_meta = self.collection.get()["metadatas"]
            return sorted(set(m.get("company", "") for m in all_meta if m.get("company")))
        except Exception:
            return []

    def _load_from_cache(self, company_name):
        try:
            res = self.collection.get(where={"company": company_name})
            if not res["documents"]:
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

    def _store_in_chroma(self, company_name, results, cached_at):
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
            self.collection.upsert(documents=docs, ids=ids, metadatas=metas)
