from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cli.main import MessageBuffer, save_report_to_disk
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.schemas import PortfolioRating, ResearchPlan, TraderAction, TraderProposal
from tradingagents.agents.utils.agent_utils import localize_report_markdown
from tradingagents.agents.trader.trader import create_trader
from tradingagents.dataflows.config import set_config


@pytest.fixture()
def korean_output_language():
    set_config({"output_language": "Korean"})
    yield
    set_config({"output_language": "English"})


def _plain_llm(response_text="응답"):
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=response_text)
    return llm


def _structured_llm(captured: dict, response):
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or response
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


def _debate_state():
    return {
        "company_of_interest": "NVDA",
        "market_report": "시장 보고서",
        "sentiment_report": "감성 보고서",
        "news_report": "뉴스 보고서",
        "fundamentals_report": "펀더멘털 보고서",
        "investment_plan": "리서치 계획",
        "trader_investment_plan": "트레이더 계획",
        "investment_debate_state": {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
        "risk_debate_state": {
            "history": "",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "latest_speaker": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }


@pytest.mark.unit
def test_research_trader_and_risk_prompts_include_selected_output_language(
    korean_output_language,
):
    captured = {}

    bull_llm = _plain_llm()
    create_bull_researcher(bull_llm)(_debate_state())
    assert "Write your entire response in Korean." in bull_llm.invoke.call_args[0][0]

    bear_llm = _plain_llm()
    create_bear_researcher(bear_llm)(_debate_state())
    assert "Write your entire response in Korean." in bear_llm.invoke.call_args[0][0]

    rm_llm = _structured_llm(
        captured,
        ResearchPlan(
            recommendation=PortfolioRating.HOLD,
            rationale="균형적입니다.",
            strategic_actions="유지합니다.",
        ),
    )
    create_research_manager(rm_llm)(_debate_state())
    assert "Write your entire response in Korean." in captured["prompt"]

    captured.clear()
    trader_llm = _structured_llm(
        captured,
        TraderProposal(
            action=TraderAction.HOLD,
            reasoning="관망합니다.",
        ),
    )
    create_trader(trader_llm)(_debate_state())
    assert any(
        "Write your entire response in Korean." in message["content"]
        for message in captured["prompt"]
    )

    for factory in (
        create_aggressive_debator,
        create_conservative_debator,
        create_neutral_debator,
    ):
        llm = _plain_llm()
        factory(llm)(_debate_state())
        assert "Write your entire response in Korean." in llm.invoke.call_args[0][0]


@pytest.mark.unit
def test_korean_complete_report_uses_korean_section_and_agent_labels(
    tmp_path: Path,
    korean_output_language,
):
    final_state = {
        "market_report": "시장 분석",
        "investment_debate_state": {
            "bull_history": "강세 논리",
            "bear_history": "약세 논리",
            "judge_decision": "리서치 결정",
        },
        "trader_investment_plan": "거래 계획",
        "risk_debate_state": {
            "aggressive_history": "공격적 관점",
            "conservative_history": "보수적 관점",
            "neutral_history": "중립 관점",
            "judge_decision": "최종 결정",
        },
    }

    report = save_report_to_disk(final_state, "NVDA", tmp_path)
    text = report.read_text(encoding="utf-8")

    assert "## II. 리서치 팀 결정" in text
    assert "### 강세 리서처" in text
    assert "### 약세 리서처" in text
    assert "### 리서치 매니저" in text
    assert "### 공격적 분석가" in text
    assert "### 보수적 분석가" in text
    assert "### 중립 분석가" in text
    assert "## V. 포트폴리오 매니저 결정" in text
    assert "Research Team Decision" not in text
    assert "Bull Researcher" not in text


@pytest.mark.unit
def test_korean_complete_report_localizes_structured_markdown_labels(
    tmp_path: Path,
    korean_output_language,
):
    final_state = {
        "market_report": "FINAL TRANSACTION PROPOSAL: **HOLD**",
        "investment_debate_state": {
            "bull_history": "Bull Analyst: English bull body.",
            "bear_history": "Bear Analyst: English bear body.",
            "judge_decision": (
                "**Recommendation**: Overweight\n\n"
                "**Rationale**: English rationale.\n\n"
                "**Strategic Actions**: English actions."
            ),
        },
        "trader_investment_plan": (
            "**Action**: Buy\n\n"
            "**Reasoning**: English reasoning.\n\n"
            "**Entry Price**: 396.0\n\n"
            "**Stop Loss**: 384.0\n\n"
            "**Position Sizing**: 1% to 3%\n\n"
            "FINAL TRANSACTION PROPOSAL: **BUY**"
        ),
        "risk_debate_state": {
            "aggressive_history": "Aggressive Analyst: English aggressive body.",
            "conservative_history": "Conservative Analyst: English conservative body.",
            "neutral_history": "Neutral Analyst: English neutral body.",
            "judge_decision": (
                "**Rating**: Overweight\n\n"
                "**Executive Summary**: Korean summary.\n\n"
                "**Investment Thesis**: Korean thesis.\n\n"
                "**Price Target**: 433.0\n\n"
                "**Time Horizon**: 3-6 months"
            ),
        },
    }

    report = save_report_to_disk(final_state, "MSFT", tmp_path)
    text = report.read_text(encoding="utf-8")

    expected_korean_markers = (
        "최종 거래 제안: **보유**",
        "강세 분석가:",
        "약세 분석가:",
        "**추천 의견**: 비중 확대",
        "**근거**:",
        "**전략적 조치**:",
        "**거래 행동**: 매수",
        "**판단 근거**:",
        "**진입가**:",
        "**손절가**:",
        "**포지션 크기**:",
        "최종 거래 제안: **매수**",
        "공격적 분석가:",
        "보수적 분석가:",
        "중립 분석가:",
        "**등급**: 비중 확대",
        "**핵심 요약**:",
        "**투자 논지**:",
        "**목표가**:",
        "**투자 기간**:",
    )
    for marker in expected_korean_markers:
        assert marker in text

    forbidden_english_markers = (
        "FINAL TRANSACTION PROPOSAL",
        "Bull Analyst:",
        "Bear Analyst:",
        "**Recommendation**",
        "**Rationale**",
        "**Strategic Actions**",
        "**Action**",
        "**Reasoning**",
        "**Entry Price**",
        "**Stop Loss**",
        "**Position Sizing**",
        "Aggressive Analyst:",
        "Conservative Analyst:",
        "Neutral Analyst:",
        "**Rating**",
        "**Executive Summary**",
        "**Investment Thesis**",
        "**Price Target**",
        "**Time Horizon**",
    )
    for marker in forbidden_english_markers:
        assert marker not in text


@pytest.mark.unit
def test_korean_markdown_localizer_handles_legacy_complete_report_labels():
    legacy = (
        "# Trading Analysis Report: MSFT\n\n"
        "Generated: 2026-05-02 07:53:08\n\n"
        "## I. Analyst Team Reports\n\n"
        "### Market Analyst\nbody\n\n"
        "### Fundamentals Analyst\nbody\n\n"
        "## II. Research Team Decision\n\n"
        "### Bull Researcher\nbody\n\n"
        "### Bear Researcher\nbody\n\n"
        "### Research Manager\nbody\n\n"
        "## III. Trading Team Plan\n\n"
        "### Trader\nbody\n\n"
        "## IV. Risk Management Team Decision\n\n"
        "### Aggressive Analyst\nbody\n\n"
        "### Conservative Analyst\nbody\n\n"
        "### Neutral Analyst\nbody\n\n"
        "## V. Portfolio Manager Decision\n\n"
        "### Portfolio Manager\nbody\n"
    )

    localized = localize_report_markdown(legacy, "Korean")

    for marker in (
        "# 트레이딩 분석 보고서: MSFT",
        "생성일: 2026-05-02 07:53:08",
        "## I. 애널리스트 팀 보고서",
        "### 시장 분석가",
        "### 펀더멘털 분석가",
        "## II. 리서치 팀 결정",
        "### 강세 리서처",
        "### 약세 리서처",
        "### 리서치 매니저",
        "## III. 트레이딩 팀 계획",
        "### 트레이더",
        "## IV. 리스크 관리 팀 결정",
        "### 공격적 분석가",
        "### 보수적 분석가",
        "### 중립 분석가",
        "## V. 포트폴리오 매니저 결정",
        "### 포트폴리오 매니저",
    ):
        assert marker in localized

    assert "Trading Analysis Report" not in localized
    assert "Research Team Decision" not in localized


@pytest.mark.unit
def test_korean_live_report_buffer_uses_korean_headings(korean_output_language):
    buffer = MessageBuffer()
    buffer.init_for_analysis(["market"])

    buffer.update_report_section("investment_plan", "리서치 결정")

    assert "### 리서치 팀 결정" in buffer.current_report
    assert "## 리서치 팀 결정" in buffer.final_report
    assert "Research Team Decision" not in buffer.final_report


@pytest.mark.unit
def test_korean_live_report_buffer_localizes_structured_labels(korean_output_language):
    buffer = MessageBuffer()
    buffer.init_for_analysis(["market"])

    buffer.update_report_section(
        "investment_plan",
        "**Recommendation**: Hold\n\nBull Analyst: English body.",
    )

    assert "**추천 의견**: 보유" in buffer.current_report
    assert "강세 분석가:" in buffer.final_report
    assert "**Recommendation**" not in buffer.final_report
