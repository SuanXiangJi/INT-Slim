import asyncio
import time

import pytest

import app.services.autonomous_agent as autonomous_agent_module
from app.services.autonomous_agent import AgentInterrupted, AutonomousAgent
from app.services.langgraph_multi_agent import (
    TEXT,
    build_task_policy,
    judge_langgraph_chat_answer,
    make_initial_state,
    prepare_langgraph_chat_context,
    resume_langgraph_chat_context,
    run_single_agent,
)
from app.services.tool_service import tool_service


CASES = [
    ("我想学习agent方面的知识", "learning", True, ""),
    ("帮我制定一周 Python 学习计划", "learning", True, ""),
    ("用例子解释快速排序", "explanation", True, ""),
    ("讲一讲 Redis，我该如何一天快速上手", "general", True, ""),
    ("写一个 Python 快排代码并运行", "coding", False, ""),
]


def _run(query: str):
    state = make_initial_state(
        user_id=b"regression-user1",
        conversation_id="retrieval-regression",
        user_input=query,
    )
    return run_single_agent("full", state)


def test_user_visible_process_copy_does_not_use_developer_viewpoint():
    visible_keys = (
        "human_required", "human_not_required", "human_approved",
        "source_ready", "judge_with_evidence", "judge_without_evidence",
        "source_not_needed",
    )
    combined = "\n".join(TEXT[key] for key in visible_keys)

    assert "前端" not in combined
    assert "展示给用户" not in combined
    assert "建议用户" not in combined


def test_agent_events_explain_the_transition_to_the_next_stage():
    result = _run("我想学习 Python 的装饰器")
    visible_events = [
        event["data"] for event in result.get("events") or []
        if event.get("data", {}).get("agent") in {"diagnosis", "retrieval", "rules", "judge"}
    ]

    assert visible_events
    assert all(data.get("transition", "").strip() for data in visible_events)

    pre_answer_rules = next(data for data in visible_events if data.get("agent") == "rules")
    assert "已完成核对" not in pre_answer_rules.get("formatted", "")


def test_tool_transition_copy_distinguishes_first_followup_and_correction():
    first = autonomous_agent_module._tool_transition("web_search")
    followup = autonomous_agent_module._tool_transition("url_fetch", has_prior_results=True)
    correction = autonomous_agent_module._tool_transition("code_exec", corrective=True)

    assert "接下来" in first and "最新网页资料" in first
    assert "上一项结果" in followup and "网页的原文" in followup
    assert "审核发现" in correction and "运行简短代码" in correction


def test_capability_question_does_not_invent_reference_sources():
    query = "\u4f60\u80fd\u5e2e\u6211\u505a\u4e9b\u4ec0\u4e48\u4e8b"

    result = _run(query)

    assert result["diagnosis"]["intent"] == "capability"
    assert result.get("evidence_refs") == []
    assert AutonomousAgent.should_answer_directly(query) is True
    agents = [event.get("data", {}).get("agent") for event in result.get("events") or []]
    assert "retrieval" not in agents
    assert "rules" not in agents
    diagnosis = result["events"][0]["data"]
    assert diagnosis["agent_name"] == "\u4efb\u52a1\u8bc6\u522b Agent"
    assert diagnosis["intent_label"] == "\u80fd\u529b\u54a8\u8be2"


def test_capability_direct_run_reaches_final_answer(monkeypatch):
    async def fake_stream():
        yield {"type": "content", "content": "\u6211\u53ef\u4ee5\u5e2e\u4f60\u8bb2\u89e3\u77e5\u8bc6\u5e76\u68c0\u7d22\u8d44\u6599\u3002"}
        yield {"type": "done", "finish_reason": "stop"}

    def fake_call(**_kwargs):
        return fake_stream()

    monkeypatch.setattr(autonomous_agent_module.llm_service, "call_model_with_tools", fake_call)
    agent = AutonomousAgent(enable_reflection=False, tool_definitions=[])

    async def collect():
        return [event async for event in agent.run(
            [{"role": "system", "content": "test"}, {"role": "user", "content": "\u4f60\u80fd\u5e2e\u6211\u505a\u4ec0\u4e48"}],
            user_input="\u4f60\u80fd\u5e2e\u6211\u505a\u4ec0\u4e48",
        )]

    events = asyncio.run(collect())

    assert any(event.get("type") == "finish" for event in events)
    assert not any(event.get("type") == "error" for event in events)


def test_max_iteration_recovery_produces_final_answer(monkeypatch):
    calls = 0

    async def tool_stream():
        yield {
            "type": "tool_call",
            "index": 0,
            "tool_call_id": "call_1",
            "function": {"name": "web_search", "arguments": '{"query":"test"}'},
        }
        yield {"type": "done", "finish_reason": "tool_calls"}

    async def answer_stream():
        yield {"type": "content", "content": "基于已有检索结果生成的最终回答。"}
        yield {"type": "done", "finish_reason": "stop"}

    def fake_call(**_kwargs):
        nonlocal calls
        calls += 1
        return tool_stream() if calls == 1 else answer_stream()

    async def executor(_name, _params):
        return {"success": True, "results": [{"title": "test"}]}

    monkeypatch.setattr(autonomous_agent_module.llm_service, "call_model_with_tools", fake_call)
    agent = AutonomousAgent(
        enable_reflection=False,
        max_iterations=1,
        tool_definitions=[{
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "search",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }],
        tool_executor=executor,
    )

    async def collect():
        return [event async for event in agent.run(
            [{"role": "system", "content": "test"}, {"role": "user", "content": "最新消息"}],
            user_input="最新消息",
        )]

    events = asyncio.run(collect())
    finish = [event for event in events if event.get("type") == "finish"]
    done = [event for event in events if event.get("type") == "done"]

    assert finish[0]["content"] == "基于已有检索结果生成的最终回答。"
    assert done[-1]["data"]["recovered_after_max_iterations"] is True


@pytest.mark.parametrize("query", [
    "\u660e\u5929\u5929\u6c14\u600e\u4e48\u6837",
    "\u73b0\u5728\u7f8e\u5143\u5151\u4eba\u6c11\u5e01\u6c47\u7387\u662f\u591a\u5c11",
    "\u6700\u65b0 AI \u65b0\u95fb",
    "\u4eca\u5929\u80a1\u5e02\u5982\u4f55",
])
def test_live_queries_skip_course_retrieval_and_keep_search_policy(query):
    result = _run(query)

    assert result["diagnosis"]["intent"] == "live_info"
    assert result.get("evidence_refs") == []
    assert result["task_policy"]["requires_live_search"] is True
    assert AutonomousAgent.should_answer_directly(query) is False


def test_deep_research_uses_web_research_path_instead_of_course_fallback():
    query = "帮我深度调研一下金融 Agent 方面的论文"
    result = _run(query)

    assert result["diagnosis"]["intent"] == "research"
    assert result["task_policy"]["requires_live_search"] is True
    assert result.get("evidence_refs") == []
    assert AutonomousAgent.should_answer_directly(query) is False
    retrieval_events = [
        event["data"] for event in result.get("events") or []
        if event.get("data", {}).get("agent") == "retrieval"
    ]
    assert retrieval_events
    assert "论文来源" in retrieval_events[0]["formatted"]


def test_research_agent_architecture_question_is_not_misclassified_as_deep_research():
    query = "我想开发一个金融调研agent，怎么做"
    result = _run(query)

    assert result["diagnosis"]["intent"] == "general"
    assert result["task_policy"]["requires_live_search"] is False


@pytest.mark.parametrize("query, expected_intent", [
    ("\u4f60\u597d", "smalltalk"),
    ("\u5982\u4f55\u505a\u86cb\u7092\u996d", "general"),
])
def test_non_course_queries_do_not_receive_unrelated_course_sources(query, expected_intent):
    result = _run(query)

    assert result["diagnosis"]["intent"] == expected_intent
    assert result.get("evidence_refs") == []
    if expected_intent == "smalltalk":
        assert AutonomousAgent.should_answer_directly(query) is True


def test_learning_today_is_not_misclassified_as_live_data():
    result = _run("\u4eca\u5929\u5f00\u59cb\u5b66\u4e60 Python")

    assert result["diagnosis"]["intent"] == "learning"
    assert result["task_policy"]["requires_live_search"] is False
    assert result.get("evidence_refs")


def test_live_answer_without_search_evidence_fails_judge():
    context = _run("\u660e\u5929\u5929\u6c14\u600e\u4e48\u6837")

    result = judge_langgraph_chat_answer(
        "\u62b1\u6b49\uff0c\u6211\u65e0\u6cd5\u67e5\u8be2\u5929\u6c14\u3002",
        context,
    )

    assert result["risk_level"] == "high"
    assert result["confidence"] == "low"


def test_placeholder_answer_fails_judge_even_when_sources_exist():
    context = _run("Redis 是什么")
    context["evidence_refs"] = [{"title": "Redis docs", "source_url": "https://redis.io/docs"}]

    result = judge_langgraph_chat_answer(
        "抱歉，本次没有生成有效回答。请重新提问。",
        context,
    )

    assert result["risk_level"] == "high"
    assert result["confidence"] == "low"
    assert "未生成可用回答" in result["proposed_action"]


def test_internal_tool_protocol_cannot_pass_judge():
    context = _run("帮我深度调研一下金融 Agent 方面的论文")
    context["evidence_refs"] = [{"title": "paper", "source_url": "https://example.com"}]

    result = judge_langgraph_chat_answer(
        '<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="web_search">',
        context,
    )

    assert result["risk_level"] == "high"
    assert result["confidence"] == "low"


def test_failed_review_prevents_high_confidence_judgement():
    context = _run("Redis \u662f\u4ec0\u4e48")
    context["review"] = {
        "overall": "FAIL",
        "scores": {"factual_grounding": 0.6},
        "content": "\u5173\u952e\u4e8b\u5b9e\u672a\u5145\u5206\u9a8c\u8bc1\u3002",
    }

    result = judge_langgraph_chat_answer("Redis \u662f\u5185\u5b58\u6570\u636e\u5e93\u3002", context)

    assert result["risk_level"] == "medium"
    assert result["confidence"] == "medium"


def test_general_technical_question_uses_shared_public_knowledge():
    result = _run("Redis \u662f\u4ec0\u4e48")

    assert result["diagnosis"]["intent"] == "general"
    assert result.get("evidence_refs")
    assert build_task_policy("Redis \u662f\u4ec0\u4e48")["requires_live_search"] is False


def test_explicit_course_catalog_request_uses_at_most_one_runoob_source():
    result = _run("请从系统课程库查找 Redis 教程")
    refs = result.get("evidence_refs") or []
    runoob_refs = [ref for ref in refs if "runoob.com" in ref.get("source_url", "")]

    assert refs
    assert len(runoob_refs) <= 1
    assert all(ref["title"] != "N/A" for ref in refs)


def test_retrieval_regression_cases():
    for query, expected_intent, expect_evidence, expected_title in CASES:
        result = _run(query)
        refs = result.get("evidence_refs") or []

        assert result["diagnosis"]["intent"] == expected_intent
        assert result.get("human_status") == "not_required"
        assert not any(
            event["data"].get("agent") == "human_gate"
            for event in result.get("events") or []
        )

        if expect_evidence:
            assert refs
            assert any(expected_title in ref["title"] for ref in refs)
            assert all(ref["title"] != "N/A" for ref in refs)
            assert all(ref["source_url"].startswith("http") for ref in refs)
        else:
            assert refs == []


def test_high_risk_request_pauses_and_resumes_with_human_decision():
    context = prepare_langgraph_chat_context(
        user_id=b"human-review-id1",
        conversation_id="human-review-regression",
        user_input="请修改数据库并删除数据",
    )

    assert context["human_status"] == "needs_human"
    assert context["human_interrupt"]["type"] == "human_review"

    resumed = resume_langgraph_chat_context(
        trace_id=context["trace_id"],
        decision={"approved": True, "feedback": "已确认"},
    )
    assert resumed["human_status"] == "approved"
    assert resumed["human_approved"] is True
    assert resumed["human_feedback"] == "已确认"


def test_agent_interrupt_preempts_waiting_for_model_chunk():
    async def scenario():
        event = asyncio.Event()
        agent = AutonomousAgent(interrupt_event=event)

        async def delayed_stream():
            await asyncio.sleep(10)
            yield {"type": "content", "content": "too late"}

        async def request_stop():
            await asyncio.sleep(0.15)
            event.set()

        asyncio.create_task(request_stop())
        started = time.perf_counter()
        with pytest.raises(AgentInterrupted):
            async for _ in agent._iterate_interruptibly(delayed_stream()):
                pass
        return time.perf_counter() - started

    assert asyncio.run(scenario()) < 0.8


def test_knowledge_graph_is_a_tool_not_an_agent_skill():
    tool_ids = [tool.id for tool in tool_service.get_all_tools()]

    assert "knowledge_graph" in tool_ids
    assert "skill_graph" not in tool_ids
    assert len(tool_ids) == len(set(tool_ids))

    graph_tool = tool_service.get_tool("knowledge_graph")
    operations = graph_tool.parameters_schema["properties"]["operation"]["enum"]
    assert "list_knowledge_points" in operations
    assert "list_skills" not in operations


def test_structured_reflection_keeps_scores_and_feedback():
    agent = AutonomousAgent(enable_reflection=False, tool_definitions=[])
    raw = (
        '{"overall":"PASS","scores":{"factual_grounding":0.9,'
        '"verification_depth":0.8,"completeness":0.95,"directness":0.9},'
        '"feedback":"checked","action_plan":"","strategy_hint":""}'
    )

    result = agent._parse_reflection_response(raw)

    assert result["overall"] == "PASS"
    assert result["scores"]["completeness"] == 0.95
    assert result["feedback"] == "checked"


def test_unavailable_tool_cannot_execute_from_reflection_plan():
    calls = []

    async def executor(name, params):
        calls.append((name, params))
        return {"success": True}

    agent = AutonomousAgent(tool_definitions=[], tool_executor=executor)
    agent.tool_definitions = []
    agent._tool_name_set = set()

    result = asyncio.run(agent._execute_tool("knowledge_graph", {"operation": "search"}))

    assert result["success"] is False
    assert "unknown tool" in result["error"]
    assert calls == []
