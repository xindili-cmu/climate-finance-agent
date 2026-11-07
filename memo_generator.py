import os
import json
import requests

MEMO_SCHEMA = {
    "company_overview": {"name": "", "sector": "", "description": "", "headquarters": "", "market_cap": "", "founded": ""},
    "esg_profile": {"overall_score": "", "climate_rating": "", "net_zero_commitment": "", "key_initiatives": [], "certifications": []},
    "recent_developments": [{"date": "", "event": "", "significance": ""}],
    "financial_snapshot": {"revenue": "", "growth_rate": "", "profitability": "", "climate_investment": "", "green_revenue_share": ""},
    "risk_assessment": {"physical_risks": [], "transition_risks": [], "regulatory_risks": [], "risk_level": "Low/Medium/High", "risk_summary": ""},
    "investment_recommendation": {"rating": "Strong Buy/Buy/Hold/Avoid", "thesis": "", "key_catalysts": [], "key_risks": [], "time_horizon": "", "comparable_companies": []},
}

SYSTEM_PROMPT = (
    "You are a senior climate finance analyst. Produce rigorous, evidence-based investment memos. "
    "Only include information supported by the provided research. Use N/A when data is unavailable. "
    "Return ONLY valid JSON — no preamble, no markdown fences. "
    "Rules: risk_level must be Low/Medium/High. "
    "rating must be exactly one of: Strong Buy, Buy, Hold, Avoid. "
    "If more than 3 financial fields are N/A, rating MUST be Hold and thesis must explain data insufficiency."
)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
CLAUDE_MODEL = "claude-sonnet-5-5"
_SKIP = ("lite", "image", "tts", "live", "audio", "embedding", "vision", "thinking", "exp")


def detect_provider(api_key):
    """Anthropic keys start with sk-ant-; anything else is tried as a Gemini key."""
    return "claude" if api_key.startswith("sk-ant-") else "gemini"


def _pick_gemini_model(api_key):
    """Ask Gemini which models this key can use and pick a Flash text model."""
    r = requests.get(GEMINI_BASE + "/models", headers={"x-goog-api-key": api_key},
                     params={"pageSize": 1000}, timeout=20)
    if not r.ok:
        raise RuntimeError(
            "This key (starts with '{}', {} chars) is not a Claude key and Gemini rejected it. "
            "Gemini API {}: {}".format(api_key[:4], len(api_key), r.status_code, r.text[:300]))
    names = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    if "gemini-flash-latest" in names:
        return "gemini-flash-latest"
    flash = [n for n in names if n.startswith("gemini") and "flash" in n
             and not any(k in n for k in _SKIP)]
    stable = [n for n in flash if "preview" not in n]
    pool = stable or flash
    if not pool:
        raise RuntimeError("No Gemini Flash model available for this key.")
    return sorted(pool)[-1]


class MemoGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.provider = detect_provider(api_key)
        self.model = CLAUDE_MODEL if self.provider == "claude" else _pick_gemini_model(api_key)

    def generate(self, company_name, research_results, progress_callback=None):
        if progress_callback:
            progress_callback(0.1, "Preparing research context...")

        context = "\n".join(
            "[{}] {} | {} | {}".format(i, r.get("title",""), r.get("url",""), r.get("content","")[:600])
            for i, r in enumerate(research_results, 1)
        )
        schema_str = json.dumps(MEMO_SCHEMA, indent=2)
        user_prompt = "Company: {}\n\nResearch:\n{}\n\nReturn ONLY valid JSON matching this schema:\n{}".format(
            company_name, context, schema_str
        )

        if progress_callback:
            progress_callback(0.3, "{} is generating the memo...".format(self.model))

        raw = self._call_claude(user_prompt) if self.provider == "claude" else self._call_gemini(user_prompt)

        if progress_callback:
            progress_callback(0.9, "Parsing memo...")

        raw = raw.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return self._error_memo(company_name)

    def _call_claude(self, user_prompt):
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=120,
        )
        if not response.ok:
            raise RuntimeError("Claude API {}: {}".format(response.status_code, response.text[:300]))
        return response.json()["content"][0]["text"]

    def _call_gemini(self, user_prompt):
        response = requests.post(
            "{}/models/{}:generateContent".format(GEMINI_BASE, self.model),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192},
            },
            timeout=120,
        )
        if not response.ok:
            raise RuntimeError("Gemini API {} ({}): {}".format(response.status_code, self.model, response.text[:300]))
        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            raise RuntimeError("Gemini returned no text: {}".format(json.dumps(data)[:300]))
        return "".join(p.get("text", "") for p in parts)

    def _error_memo(self, company_name):
        return {
            "company_overview": {"name": company_name, "sector": "N/A", "description": "Parse error.", "headquarters": "N/A", "market_cap": "N/A", "founded": "N/A"},
            "esg_profile": {"overall_score": "N/A", "climate_rating": "N/A", "net_zero_commitment": "N/A", "key_initiatives": [], "certifications": []},
            "recent_developments": [],
            "financial_snapshot": {"revenue": "N/A", "growth_rate": "N/A", "profitability": "N/A", "climate_investment": "N/A", "green_revenue_share": "N/A"},
            "risk_assessment": {"physical_risks": [], "transition_risks": ["Parse error"], "regulatory_risks": [], "risk_level": "High", "risk_summary": "Could not parse memo."},
            "investment_recommendation": {"rating": "Hold", "thesis": "Memo generation failed.", "key_catalysts": [], "key_risks": ["Parse error"], "time_horizon": "N/A", "comparable_companies": []},
        }
