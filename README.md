# 🌍 Climate Finance Research Agent

AI-powered investment memo generator with built-in guardrails & source evaluation.

## Stack
| Layer | Tool |
|-------|------|
| Search | Tavily |
| Vector Storage | ChromaDB (persistent) |
| LLM | Claude claude-opus-4-5 (Anthropic) |
| UI | Streamlit |

## Setup

```bash
# 1. Clone / unzip the project
cd climate-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set API keys
cp .env.example .env
# Edit .env and fill in your keys:
#   ANTHROPIC_API_KEY=...
#   TAVILY_API_KEY=...

# 4. Run
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## How it works

1. **Research** — Tavily searches 6 targeted queries (ESG, news, financials, climate risk, regulation, green strategy)
2. **Store** — Results are embedded and stored in ChromaDB for persistence and semantic retrieval
3. **Synthesize** — Claude generates a structured JSON investment memo grounded only in retrieved sources
4. **Evaluate** — Guardrails module scores confidence (0-100) based on source count, credibility, relevance, and data completeness
5. **Display** — Streamlit renders the memo in tabbed sections with a guardrails dashboard

## Guardrails (deploy-ability theme)

The guardrails module evaluates every memo against:
- Source volume & diversity
- % from authoritative domains (Reuters, Bloomberg, SEC, IEA, MSCI, etc.)
- Average Tavily relevance score
- Missing data fields
- Minimum confidence floor (configurable in sidebar)

Memos below the threshold are flagged as NOT acceptable for use without human expert validation.

## Project Structure

```
climate-agent/
├── app.py              # Streamlit UI
├── researcher.py       # Tavily search + ChromaDB storage
├── memo_generator.py   # Claude memo synthesis
├── guardrails.py       # Source credibility + confidence scoring
├── requirements.txt
└── .env.example
```
