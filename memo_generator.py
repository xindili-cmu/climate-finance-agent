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

class MemoGenerator:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.url = "https://api.anthropic.com/v1/messages"

    def generate(self, company_name, research_results, progress_callback=None):
        if progress_callback:
            progress_callback(0.1, "Preparing context for Claude...")

        context = "\n".join(
            "[{}] {} | {} | {}".format(i, r.get("title",""), r.get("url",""), r.get("content","")[:600])
            for i, r in enumerate(research_results, 1)
        )

        schema_str = json.dumps(MEMO_SCHEMA, indent=2)
        user_prompt = "Company: {}\n\nResearch:\n{}\n\nReturn ONLY valid JSON matching this schema:\n{}".format(
            company_name, context, schema_str
        )

        if progress_callback:
            progress_callback(0.3, "Claude is generating the memo...")

        response = requests.post(
            self.url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()

        if progress_callback:
            progress_callback(0.9, "Parsing memo...")

        raw = response.json()["content"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "company_overview": {"name": company_name, "sector": "N/A", "description": "Parse error.", "headquarters": "N/A", "market_cap": "N/A", "founded": "N/A"},
                "esg_profile": {"overall_score": "N/A", "climate_rating": "N/A", "net_zero_commitment": "N/A", "key_initiatives": [], "certifications": []},
                "recent_developments": [],
                "financial_snapshot": {"revenue": "N/A", "growth_rate": "N/A", "profitability": "N/A", "climate_investment": "N/A", "green_revenue_share": "N/A"},
                "risk_assessment": {"physical_risks": [], "transition_risks": ["Parse error"], "regulatory_risks": [], "risk_level": "High", "risk_summary": "Could not parse memo."},
                "investment_recommendation": {"rating": "Hold", "thesis": "Memo generation failed.", "key_catalysts": [], "key_risks": ["Parse error"], "time_horizon": "N/A", "comparable_companies": []},
            }
