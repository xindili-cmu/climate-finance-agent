"""
guardrails.py
Evaluates research quality, source credibility, and flags potential issues.
This is the core "deploy-ability" module — demonstrating responsible AI.
"""

from typing import List, Dict, Any
from dataclasses import dataclass, field


TRUSTED_DOMAINS = [
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "sec.gov", "epa.gov", "iea.org", "msci.com",
    "sustainalytics.com", "cdp.net", "nature.com", "ipcc.ch",
]

# Fields we expect to be populated in a good memo
REQUIRED_FIELDS = [
    "company_overview.sector",
    "company_overview.description",
    "esg_profile.climate_rating",
    "financial_snapshot.revenue",
    "risk_assessment.risk_level",
    "investment_recommendation.rating",
    "investment_recommendation.thesis",
]


@dataclass
class GuardrailsReport:
    confidence_score: int               # 0-100
    source_count: int
    trusted_source_count: int
    avg_relevance_score: float
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    acceptable_for_use: bool = True
    eval_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "source_count": self.source_count,
            "trusted_source_count": self.trusted_source_count,
            "avg_relevance_score": round(self.avg_relevance_score, 3),
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "acceptable_for_use": self.acceptable_for_use,
            "eval_summary": self.eval_summary,
        }


class GuardrailsAssessor:
    """
    Evaluates whether a generated memo meets quality thresholds.

    Rubric (matches hackathon 'deploy-ability' theme):
    - Source volume & diversity
    - Source credibility (trusted domains)
    - Relevance scores from Tavily
    - Data completeness (missing fields)
    - Confidence floor before allowing downstream use
    """

    CONFIDENCE_FLOOR = 40   # Below this → not acceptable

    def assess(
        self,
        memo: Dict[str, Any],
        research_results: List[Dict[str, Any]],
    ) -> GuardrailsReport:
        confidence = 100
        warnings: List[str] = []

        # 1. Source volume
        n = len(research_results)
        if n < 5:
            confidence -= 25
            warnings.append(f"Only {n} sources found — consider manual verification.")
        elif n < 10:
            confidence -= 10

        # 2. Trusted domain ratio
        trusted = [r for r in research_results if r.get("is_trusted", False)]
        trust_ratio = len(trusted) / max(n, 1)
        if trust_ratio < 0.2:
            confidence -= 20
            warnings.append("Few results from authoritative sources (Reuters, Bloomberg, SEC, IEA, etc.).")
        elif trust_ratio < 0.4:
            confidence -= 10

        # 3. Average Tavily relevance score
        scores = [float(r.get("score", 0)) for r in research_results]
        avg_score = sum(scores) / max(len(scores), 1)
        if avg_score < 0.4:
            confidence -= 15
            warnings.append("Low average search relevance — results may be off-topic.")

        # 4. Missing / N/A fields in memo
        missing = self._check_missing(memo)
        confidence -= len(missing) * 5
        if missing:
            warnings.append(f"Missing data fields: {', '.join(missing)}")

        # 5. Risk level sanity
        risk_level = (
            memo.get("risk_assessment", {}).get("risk_level", "").lower()
        )
        if risk_level not in ("low", "medium", "high"):
            confidence -= 5
            warnings.append("Risk level could not be determined.")

        confidence = max(0, min(100, confidence))
        acceptable = confidence >= self.CONFIDENCE_FLOOR

        if not acceptable:
            warnings.append(
                "⚠️ Confidence below threshold — this memo should NOT be used for investment decisions without human expert review."
            )

        # Compose a plain-English eval summary
        summary = self._make_summary(confidence, n, len(trusted), avg_score, missing, acceptable)

        return GuardrailsReport(
            confidence_score=confidence,
            source_count=n,
            trusted_source_count=len(trusted),
            avg_relevance_score=avg_score,
            missing_fields=missing,
            warnings=warnings,
            acceptable_for_use=acceptable,
            eval_summary=summary,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_missing(self, memo: Dict[str, Any]) -> List[str]:
        missing = []
        for path in REQUIRED_FIELDS:
            keys = path.split(".")
            val = memo
            try:
                for k in keys:
                    val = val[k]
                if val in (None, "", "N/A", [], {}):
                    missing.append(path)
            except (KeyError, TypeError):
                missing.append(path)
        return missing

    def _make_summary(self, confidence, n, trusted, avg_score, missing, acceptable):
        lines = [
            f"Confidence: {confidence}/100 {'✅' if confidence >= 70 else '⚠️' if confidence >= 40 else '❌'}",
            f"Sources: {n} total, {trusted} from authoritative domains",
            f"Avg relevance: {avg_score:.2f}/1.0",
        ]
        if missing:
            lines.append(f"Missing fields: {len(missing)}")
        lines.append(
            "Acceptable for preliminary research." if acceptable
            else "NOT acceptable — requires human expert validation."
        )
        return " | ".join(lines)
