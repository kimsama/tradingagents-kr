import logging

import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph


@pytest.mark.unit
def test_anthropic_effort_config_logs_warning_when_ignored(caplog):
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.config = {
        "llm_provider": "anthropic",
        "anthropic_effort": "high",
    }
    caplog.set_level(logging.WARNING, logger="tradingagents.graph.trading_graph")

    kwargs = graph._get_provider_kwargs()

    assert kwargs == {}
    assert "anthropic_effort is currently ignored" in caplog.text
