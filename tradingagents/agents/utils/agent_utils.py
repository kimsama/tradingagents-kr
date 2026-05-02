import re

from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


_ENGLISH_REPORT_LABELS = {
    "complete_analysis_report": "Complete Analysis Report",
    "trading_analysis_report": "Trading Analysis Report",
    "generated": "Generated",
    "analyst_team_reports": "Analyst Team Reports",
    "market_analysis": "Market Analysis",
    "social_sentiment": "Social Sentiment",
    "news_analysis": "News Analysis",
    "fundamentals_analysis": "Fundamentals Analysis",
    "market_analyst": "Market Analyst",
    "social_analyst": "Social Analyst",
    "news_analyst": "News Analyst",
    "fundamentals_analyst": "Fundamentals Analyst",
    "research_team_decision": "Research Team Decision",
    "bull_researcher": "Bull Researcher",
    "bear_researcher": "Bear Researcher",
    "research_manager": "Research Manager",
    "bull_researcher_analysis": "Bull Researcher Analysis",
    "bear_researcher_analysis": "Bear Researcher Analysis",
    "research_manager_decision": "Research Manager Decision",
    "bull_analyst": "Bull Analyst",
    "bear_analyst": "Bear Analyst",
    "trading_team_plan": "Trading Team Plan",
    "trader": "Trader",
    "risk_management_team_decision": "Risk Management Team Decision",
    "aggressive_analyst": "Aggressive Analyst",
    "conservative_analyst": "Conservative Analyst",
    "neutral_analyst": "Neutral Analyst",
    "aggressive_analyst_analysis": "Aggressive Analyst Analysis",
    "conservative_analyst_analysis": "Conservative Analyst Analysis",
    "neutral_analyst_analysis": "Neutral Analyst Analysis",
    "portfolio_manager_decision": "Portfolio Manager Decision",
    "portfolio_manager": "Portfolio Manager",
}

_KOREAN_REPORT_LABELS = {
    "complete_analysis_report": "전체 분석 보고서",
    "trading_analysis_report": "트레이딩 분석 보고서",
    "generated": "생성일",
    "analyst_team_reports": "애널리스트 팀 보고서",
    "market_analysis": "시장 분석",
    "social_sentiment": "소셜 감성 분석",
    "news_analysis": "뉴스 분석",
    "fundamentals_analysis": "펀더멘털 분석",
    "market_analyst": "시장 분석가",
    "social_analyst": "소셜 분석가",
    "news_analyst": "뉴스 분석가",
    "fundamentals_analyst": "펀더멘털 분석가",
    "research_team_decision": "리서치 팀 결정",
    "bull_researcher": "강세 리서처",
    "bear_researcher": "약세 리서처",
    "research_manager": "리서치 매니저",
    "bull_researcher_analysis": "강세 리서처 분석",
    "bear_researcher_analysis": "약세 리서처 분석",
    "research_manager_decision": "리서치 매니저 결정",
    "bull_analyst": "강세 분석가",
    "bear_analyst": "약세 분석가",
    "trading_team_plan": "트레이딩 팀 계획",
    "trader": "트레이더",
    "risk_management_team_decision": "리스크 관리 팀 결정",
    "aggressive_analyst": "공격적 분석가",
    "conservative_analyst": "보수적 분석가",
    "neutral_analyst": "중립 분석가",
    "aggressive_analyst_analysis": "공격적 분석가 분석",
    "conservative_analyst_analysis": "보수적 분석가 분석",
    "neutral_analyst_analysis": "중립 분석가 분석",
    "portfolio_manager_decision": "포트폴리오 매니저 결정",
    "portfolio_manager": "포트폴리오 매니저",
}


def is_korean_output_language(lang: str | None = None) -> bool:
    """Return True when the configured report language is Korean."""
    if lang is None:
        from tradingagents.dataflows.config import get_config
        lang = get_config().get("output_language", "English")
    normalized = str(lang).strip().lower()
    return normalized in {"korean", "korean (한국어)", "한국어", "ko", "kr"}


def get_report_label(key: str, lang: str | None = None) -> str:
    """Return a static report/role label localized for the configured language."""
    english_label = _ENGLISH_REPORT_LABELS[key]
    if is_korean_output_language(lang):
        return _KOREAN_REPORT_LABELS.get(key, english_label)
    return english_label


_KOREAN_RATING_LABELS = {
    "buy": "매수",
    "overweight": "비중 확대",
    "hold": "보유",
    "underweight": "비중 축소",
    "sell": "매도",
}


def _localize_rating_value(value: str) -> str:
    return _KOREAN_RATING_LABELS.get(value.strip().lower(), value)


def _localize_bold_label_value(text: str, english_label: str, korean_label: str) -> str:
    pattern = re.compile(
        rf"\*\*{re.escape(english_label)}\*\*:\s*"
        r"(Buy|Overweight|Hold|Underweight|Sell)\b",
        re.IGNORECASE,
    )
    text = pattern.sub(
        lambda match: f"**{korean_label}**: {_localize_rating_value(match.group(1))}",
        text,
    )
    return text.replace(f"**{english_label}**:", f"**{korean_label}**:")


def localize_report_markdown(text: str, lang: str | None = None) -> str:
    """Localize deterministic report labels in user-facing markdown output.

    The raw agent state remains unchanged because parsers and memory logs
    depend on stable English schema labels. This function is only for final
    display/export markdown.
    """
    if not text or not is_korean_output_language(lang):
        return text

    localized = re.sub(
        r"FINAL TRANSACTION PROPOSAL:\s*\*\*(BUY|SELL|HOLD)\*\*",
        lambda match: f"최종 거래 제안: **{_localize_rating_value(match.group(1))}**",
        text,
        flags=re.IGNORECASE,
    )

    for english_label, korean_label in (
        ("Recommendation", "추천 의견"),
        ("Action", "거래 행동"),
        ("Rating", "등급"),
    ):
        localized = _localize_bold_label_value(
            localized, english_label, korean_label
        )

    for english_label, korean_label in (
        ("Rationale", "근거"),
        ("Strategic Actions", "전략적 조치"),
        ("Reasoning", "판단 근거"),
        ("Entry Price", "진입가"),
        ("Stop Loss", "손절가"),
        ("Position Sizing", "포지션 크기"),
        ("Executive Summary", "핵심 요약"),
        ("Investment Thesis", "투자 논지"),
        ("Price Target", "목표가"),
        ("Time Horizon", "투자 기간"),
    ):
        localized = localized.replace(f"**{english_label}**:", f"**{korean_label}**:")

    for english_role, korean_role in (
        ("Bull Analyst", "강세 분석가"),
        ("Bear Analyst", "약세 분석가"),
        ("Aggressive Analyst", "공격적 분석가"),
        ("Conservative Analyst", "보수적 분석가"),
        ("Neutral Analyst", "중립 분석가"),
    ):
        localized = localized.replace(f"{english_role}:", f"{korean_role}:")

    for english_text, korean_text in (
        ("# Trading Analysis Report:", "# 트레이딩 분석 보고서:"),
        ("Generated:", "생성일:"),
        ("## I. Analyst Team Reports", "## I. 애널리스트 팀 보고서"),
        ("## II. Research Team Decision", "## II. 리서치 팀 결정"),
        ("## III. Trading Team Plan", "## III. 트레이딩 팀 계획"),
        ("## IV. Risk Management Team Decision", "## IV. 리스크 관리 팀 결정"),
        ("## V. Portfolio Manager Decision", "## V. 포트폴리오 매니저 결정"),
        ("### Market Analyst", "### 시장 분석가"),
        ("### Social Analyst", "### 소셜 분석가"),
        ("### News Analyst", "### 뉴스 분석가"),
        ("### Fundamentals Analyst", "### 펀더멘털 분석가"),
        ("### Bull Researcher", "### 강세 리서처"),
        ("### Bear Researcher", "### 약세 리서처"),
        ("### Research Manager", "### 리서치 매니저"),
        ("### Trader", "### 트레이더"),
        ("### Aggressive Analyst", "### 공격적 분석가"),
        ("### Conservative Analyst", "### 보수적 분석가"),
        ("### Neutral Analyst", "### 중립 분석가"),
        ("### Portfolio Manager", "### 포트폴리오 매니저"),
    ):
        localized = localized.replace(english_text, korean_text)

    return localized


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to user-facing reports and decisions so saved outputs follow the
    language selected in the CLI.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
