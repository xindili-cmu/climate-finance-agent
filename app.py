"""
app.py
Climate Finance Research Agent — Streamlit UI
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from researcher import ClimateResearcher
from memo_generator import MemoGenerator
from guardrails import GuardrailsAssessor

st.set_page_config(
    page_title="Climate Finance Agent",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
  h1, h2, h3 { font-family: 'DM Serif Display', serif; }
  .hero-title { font-family:'DM Serif Display',serif; font-size:2.8rem; line-height:1.15; color:#0f2e1a; margin-bottom:0.2rem; }
  .hero-sub   { font-size:1.05rem; color:#4a7c5a; margin-bottom:2rem; font-weight:300; }
  .kpi-card   { background:#f9fbf9; border:1px solid #d4e8da; border-radius:10px; padding:1rem 1.2rem; }
  .kpi-label  { font-size:0.78rem; color:#666; margin-bottom:4px; text-transform:uppercase; letter-spacing:.04em; }
  .kpi-value  { font-size:1rem; font-weight:700; color:#0f2e1a; line-height:1.4; word-break:break-word; }
  .info-row   { display:flex; gap:2rem; flex-wrap:wrap; margin:0.6rem 0; }
  .info-item  { min-width:160px; }
  .info-label { font-size:0.78rem; color:#888; }
  .info-val   { font-size:0.95rem; font-weight:600; color:#1a1a1a; }
  .badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; margin:2px; }
  .badge-green  { background:#d4edda; color:#155724; }
  .badge-yellow { background:#fff3cd; color:#856404; }
  .guardrail-box { border-left:4px solid; padding:0.8rem 1rem; border-radius:0 8px 8px 0; margin-bottom:0.8rem; font-size:0.88rem; }
  .guardrail-ok   { border-color:#28a745; background:#f0fff4; }
  .guardrail-fail { border-color:#dc3545; background:#fff5f5; }
  section[data-testid="stSidebar"] { background:#f0f7f2; }
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] small,
  section[data-testid="stSidebar"] span { color:#1a3a2a !important; font-size:0.9rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    anthropic_key = st.text_input("Anthropic API Key", value="", type="password")
    tavily_key    = st.text_input("Tavily API Key",    value=os.getenv("TAVILY_API_KEY",""),   type="password")
    if anthropic_key: os.environ["ANTHROPIC_API_KEY"] = anthropic_key
    if tavily_key:    os.environ["TAVILY_API_KEY"]    = tavily_key
    st.divider()
    st.markdown("### 🛡️ Guardrails Policy")
    confidence_threshold = st.slider("Min. confidence to accept", 0, 100, 40, 5,
        help="Memos below this score are flagged as NOT acceptable for use.")
    st.markdown("**Memos below this threshold will be flagged and must be verified by a human expert before any investment decision.**")
    st.divider()
    st.markdown("### ℹ️ Stack")
    st.markdown("**Search:** Tavily  \n**Storage:** ChromaDB  \n**LLM:** Claude Opus  \n**UI:** Streamlit")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">🌍 Climate Finance Research Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">AI-powered investment memo generator with built-in guardrails & source evaluation</div>', unsafe_allow_html=True)

col_input, col_btn, col_ref = st.columns([4, 1, 1])
with col_input:
    company = st.text_input("", placeholder="Enter company name, e.g.  Ørsted · NextEra Energy · Vestas · BYD", label_visibility="collapsed")
with col_btn:
    run = st.button("🔍 Research", type="primary", use_container_width=True)
with col_ref:
    force_refresh = st.button("🔄 Re-fetch", use_container_width=True, help="Ignore cache and re-fetch from Tavily")

# ── Session state ──────────────────────────────────────────────────────────────
for k in ("memo","guardrails","sources"):
    if k not in st.session_state:
        st.session_state[k] = None if k != "sources" else []
if "from_cache" not in st.session_state:
    st.session_state.from_cache = False
if "cached_at" not in st.session_state:
    st.session_state.cached_at = ""

# ── Run pipeline ───────────────────────────────────────────────────────────────
if run and company.strip():
    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("TAVILY_API_KEY"):
        st.error("Please enter your API keys in the sidebar first.")
        st.stop()

    st.divider()
    status = st.empty()
    bar    = st.progress(0)

    def cb(pct, msg):
        bar.progress(pct)
        status.markdown(f"**{msg}**")

    with st.spinner(""):
        researcher = ClimateResearcher()
        research   = researcher.research_company(company.strip(), progress_callback=cb, force_refresh=force_refresh)
        results    = research["results"]
        from_cache = research["from_cache"]
        cached_at  = research.get("cached_at","")
        generator  = MemoGenerator()
        memo       = generator.generate(company.strip(), results, progress_callback=cb)
        assessor   = GuardrailsAssessor()
        assessor.CONFIDENCE_FLOOR = confidence_threshold
        gr         = assessor.assess(memo, results)

    bar.progress(1.0)
    status.markdown("**✅ Done!**")
    st.session_state.from_cache = from_cache
    st.session_state.cached_at  = cached_at
    st.session_state.memo       = memo
    st.session_state.guardrails = gr
    st.session_state.sources    = results

# ── Display ────────────────────────────────────────────────────────────────────
memo = st.session_state.memo
gr   = st.session_state.guardrails

def kpi(label, value, color="#0f2e1a"):
    return f"""<div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color};">{value}</div>
    </div>"""

def info_grid(items):
    cells = "".join(
        f'<div class="info-item"><div class="info-label">{l}</div><div class="info-val">{v}</div></div>'
        for l, v in items
    )
    return f'<div class="info-row">{cells}</div>'

if memo and gr:
    st.divider()

    # Guardrails banner
    conf  = gr.confidence_score
    ok    = gr.acceptable_for_use
    cls   = "guardrail-ok" if ok else "guardrail-fail"
    emoji = "✅" if ok else "❌"
    st.markdown(f"""<div class="guardrail-box {cls}">
      <strong>{emoji} Guardrails Evaluation</strong> &nbsp;|&nbsp;
      Confidence: <strong>{conf}/100</strong> &nbsp;|&nbsp; {gr.eval_summary}
    </div>""", unsafe_allow_html=True)
    if not ok:
        st.warning("⚠️ Confidence below threshold — do NOT use for investment decisions without human expert review.")

    # Cache banner
    if st.session_state.from_cache:
        st.info(f"⚡ Results loaded from cache (saved {st.session_state.cached_at}) — click 🔄 Re-fetch to get fresh data.")
    else:
        st.success("🌐 Fresh data fetched from Tavily and saved to ChromaDB.")

    ov   = memo.get("company_overview", {})
    esg  = memo.get("esg_profile", {})
    rec  = memo.get("investment_recommendation", {})
    risk = memo.get("risk_assessment", {})
    fin  = memo.get("financial_snapshot", {})

    risk_color = "#c0392b" if risk.get("risk_level")=="High" else "#a06000" if risk.get("risk_level")=="Medium" else "#1a7a3c"
    rec_color  = "#1a7a3c" if "Buy" in rec.get("rating","") else "#c0392b" if rec.get("rating")=="Avoid" else "#a06000"

    # KPI row (pure HTML — no truncation)
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi("Sector",         ov.get("sector","N/A")), unsafe_allow_html=True)
    k2.markdown(kpi("ESG Rating",     esg.get("climate_rating","N/A")), unsafe_allow_html=True)
    k3.markdown(kpi("Risk Level",     risk.get("risk_level","N/A"), risk_color), unsafe_allow_html=True)
    k4.markdown(kpi("Recommendation", rec.get("rating","N/A"), rec_color), unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Overview", "🌱 ESG Profile", "📰 Developments",
        "💰 Financials", "⚠️ Risks", "🛡️ Guardrails Detail"
    ])

    # Tab 1 ── Overview (single HTML block)
    with tab1:
        rating   = rec.get("rating","Hold")
        cls_r    = "#1a7a3c" if "Buy" in rating else "#c0392b" if rating=="Avoid" else "#a06000"
        catalysts = "".join(f"<li>{c}</li>" for c in rec.get("key_catalysts",[]))
        comps     = ", ".join(rec.get("comparable_companies",[]))
        st.markdown(f"""
        <div style="background:#f9fbf9;border:1px solid #d4e8da;border-radius:12px;padding:1.4rem 1.6rem;margin-bottom:1rem;">
          <h3 style="margin-top:0;">{ov.get('name', company)}</h3>
          <p style="color:#333;line-height:1.6;">{ov.get('description','N/A')}</p>
          {info_grid([
            ("Headquarters", ov.get("headquarters","N/A")),
            ("Founded",      ov.get("founded","N/A")),
            ("Market Cap",   ov.get("market_cap","N/A")),
            ("Sector",       ov.get("sector","N/A")),
          ])}
          <div style="margin-top:1rem;">
            <span style="font-size:0.78rem;color:#888;text-transform:uppercase;letter-spacing:.04em;">Analyst Rating</span><br>
            <span style="font-size:1.3rem;font-weight:700;color:{cls_r};">{rating}</span>
          </div>
          <p style="margin-top:0.8rem;"><strong>Thesis:</strong> {rec.get('thesis','N/A')}</p>
          <p><strong>Time Horizon:</strong> {rec.get('time_horizon','N/A')}</p>
          {"<strong>Key Catalysts:</strong><ul style='margin-top:4px;'>"+catalysts+"</ul>" if catalysts else ""}
          {"<p><strong>Comparables:</strong> "+comps+"</p>" if comps else ""}
        </div>""", unsafe_allow_html=True)

    # Tab 2 ── ESG Profile
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(kpi("Overall ESG Score",   esg.get("overall_score","N/A")), unsafe_allow_html=True)
            st.markdown("")
            st.markdown(kpi("Climate Rating",      esg.get("climate_rating","N/A")), unsafe_allow_html=True)
            st.markdown("")
            st.markdown(kpi("Net Zero Commitment", esg.get("net_zero_commitment","N/A")), unsafe_allow_html=True)
        with col2:
            if esg.get("key_initiatives"):
                st.markdown("**Key Climate Initiatives**")
                for init in esg["key_initiatives"]:
                    st.markdown(f"- {init}")
            if esg.get("certifications"):
                st.markdown("**Certifications**")
                for cert in esg["certifications"]:
                    st.markdown(f'<span class="badge badge-green">{cert}</span>', unsafe_allow_html=True)

    # Tab 3 ── Recent Developments
    with tab3:
        devs = memo.get("recent_developments", [])
        if devs:
            for d in devs:
                with st.expander(f"📅 {d.get('date','N/A')} — {d.get('event','')}"):
                    st.markdown(f"**Significance:** {d.get('significance','N/A')}")
        else:
            st.info("No recent developments found.")

    # Tab 4 ── Financials (pure HTML cards)
    with tab4:
        f1, f2 = st.columns(2)
        with f1:
            st.markdown(kpi("Revenue",       fin.get("revenue","N/A")), unsafe_allow_html=True)
            st.markdown("")
            st.markdown(kpi("Growth Rate",   fin.get("growth_rate","N/A")), unsafe_allow_html=True)
        with f2:
            st.markdown(kpi("Profitability", fin.get("profitability","N/A")), unsafe_allow_html=True)
            st.markdown("")
            st.markdown(kpi("Climate R&D Investment", fin.get("climate_investment","N/A")), unsafe_allow_html=True)
        grs = fin.get("green_revenue_share","")
        if grs and grs != "N/A":
            st.info(f"🌱 Green revenue share: **{grs}**")

    # Tab 5 ── Risks
    with tab5:
        rl = risk.get("risk_level","N/A")
        rl_color = "#c0392b" if rl=="High" else "#a06000" if rl=="Medium" else "#1a7a3c"
        st.markdown(f'<p>Overall Risk Level: <strong style="color:{rl_color};font-size:1.1rem;">{rl}</strong></p>', unsafe_allow_html=True)
        st.markdown(risk.get("risk_summary",""))
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("**🌡️ Physical Risks**")
            for r in risk.get("physical_risks",[]): st.markdown(f"- {r}")
        with r2:
            st.markdown("**🔄 Transition Risks**")
            for r in risk.get("transition_risks",[]): st.markdown(f"- {r}")
        with r3:
            st.markdown("**⚖️ Regulatory Risks**")
            for r in risk.get("regulatory_risks",[]): st.markdown(f"- {r}")
        if rec.get("key_risks"):
            st.divider()
            st.markdown("**Analyst-Identified Key Risks**")
            for r in rec["key_risks"]: st.markdown(f"- {r}")

    # Tab 6 ── Guardrails Detail
    with tab6:
        st.markdown("### 🛡️ Responsible AI Evaluation")
        st.markdown("> *Per the deploy-ability theme: AI outputs must meet quality thresholds before informing decisions.*")
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown(kpi("Confidence Score",       f"{gr.confidence_score}/100"), unsafe_allow_html=True)
        g2.markdown(kpi("Total Sources",          str(gr.source_count)), unsafe_allow_html=True)
        g3.markdown(kpi("Authoritative Sources",  str(gr.trusted_source_count)), unsafe_allow_html=True)
        g4.markdown(kpi("Avg. Relevance",         f"{gr.avg_relevance_score:.2f}"), unsafe_allow_html=True)

        if gr.warnings:
            st.markdown("**⚠️ Warnings**")
            for w in gr.warnings: st.warning(w)

        if gr.missing_fields:
            st.markdown("**Missing Data Fields**")
            for f in gr.missing_fields:
                st.markdown(f'<span class="badge badge-yellow">{f}</span>', unsafe_allow_html=True)

        st.divider()
        st.markdown("**Acceptance Criteria**")
        st.markdown("""
| Criterion | Threshold | Why |
|-----------|-----------|-----|
| Source count | ≥ 10 ideal | More sources = less hallucination risk |
| Trusted domains | ≥ 40% | Bloomberg, Reuters, SEC = higher credibility |
| Avg. relevance | ≥ 0.4 | Low score = results may be off-topic |
| Missing fields | < 4 | Gaps indicate data unavailability |
| Overall confidence | ≥ threshold | Configurable minimum floor |
        """)

        with st.expander("📚 All Sources"):
            for i, s in enumerate(st.session_state.sources, 1):
                badge = "✅" if s.get("is_trusted") else "○"
                st.markdown(f"**{i}.** {badge} [{s.get('title','N/A')}]({s.get('url','#')}) — relevance: `{s.get('score',0):.3f}`")

elif not run:
    st.markdown("""
    <br>
    <div style="text-align:center;padding:3rem 0;">
      <div style="font-size:4rem;">🌱</div>
      <div style="font-family:'DM Serif Display',serif;font-size:1.4rem;color:#2d5a3d;">
        Enter a company name above to generate an AI-powered investment memo
      </div>
      <div style="font-size:0.9rem;color:#7aab8a;margin-top:0.5rem;">
        Built with Tavily · ChromaDB · Claude · Streamlit
      </div>
    </div>
    """, unsafe_allow_html=True)
