from tradingagents.graph.conditional_logic import ConditionalLogic


def _state(*, count, current_response):
    return {
        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "",
            "history": current_response,
            "current_response": current_response,
            "judge_decision": "",
            "count": count,
        }
    }


def test_debate_routing_after_korean_bull_response_goes_to_bear():
    logic = ConditionalLogic(max_debate_rounds=2)

    route = logic.should_continue_debate(
        _state(count=1, current_response="강세 분석가: 긍정적 논거")
    )

    assert route == "Bear Researcher"


def test_debate_routing_at_count_zero_starts_with_bull():
    logic = ConditionalLogic(max_debate_rounds=2)

    route = logic.should_continue_debate(_state(count=0, current_response=""))

    assert route == "Bull Researcher"


def test_debate_routing_after_bear_response_goes_to_bull_before_limit():
    logic = ConditionalLogic(max_debate_rounds=2)

    route = logic.should_continue_debate(
        _state(count=2, current_response="약세 분석가: 부정적 논거")
    )

    assert route == "Bull Researcher"


def test_debate_routing_goes_to_research_manager_at_limit():
    logic = ConditionalLogic(max_debate_rounds=1)

    route = logic.should_continue_debate(
        _state(count=2, current_response="약세 분석가: 부정적 논거")
    )

    assert route == "Research Manager"
