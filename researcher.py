import os
import json
import hashlib
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

CACHE_FILE = "./research_cache.json"
CACHE_TTL_HOURS = 24

class ClimateResearcher:
    def __init__(self):
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self.cache = self._load_cache()

    def research_company(self, company_name, progress_callback=None, force_refresh=False):
        key = company_name.lower().strip()

        # Check cache
        if not force_refresh and key in self.cache:
            entry = self.cache[key]
            cached_dt = datetime.fromisoformat(entry["cached_at"])
            if datetime.now() - cached_dt < timedelta(hours=CACHE_TTL_HOURS):
                if progress_callback:
                    progress_callback(1.0, f"✅ Loaded from cache (saved {entry['cached_at'][:16]})")
                return {"results": entry["results"], "from_cache": True, "cached_at": entry["cached_at"]}

        # Fetch from Tavily
        all_results, seen_urls = [], set()
        total = len(SEARCH_QUERIES)
        for i, template in enumerate(SEARCH_QUERIES):
            query = template.format(company=company_name)
            if progress_callback:
                progress_callback(i / total, f"🔎 {query[:60]}…")
            try:
                response = self.tavily.search(query, max_results=4, search_depth="advanced")
                for r in response.get("results", []):
                    url = r.get("url", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        r["is_trusted"] = any(d in url for d in TRUSTED_DOMAINS)
                        all_results.append(r)
            except Exception as e:
                print(f"Query failed: {e}")

        now_str = datetime.now().isoformat()
        self.cache[key] = {"results": all_results, "cached_at": now_str}
        self._save_cache()

        if progress_callback:
            progress_callback(1.0, "✅ Research complete.")
        return {"results": all_results, "from_cache": False, "cached_at": now_str}

    def list_cached_companies(self):
        return list(self.cache.keys())

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f)
