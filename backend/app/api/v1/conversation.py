from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
import asyncio
import copy
import json
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from app.models import get_db, SessionLocal as _SessionLocal
from app.schemas.user import User as UserSchema
from app.schemas.conversation import Conversation as ConversationSchema, ConversationCreate, ConversationUpdate
from app.schemas.message import Message as MessageSchema, MessageCreate, MessageFavorUpdate
from app.crud.conversation import (
    get_conversations_by_user_id,
    get_conversation_by_id,
    create_conversation,
    update_conversation_title,
    delete_conversation
)
from app.crud.message import (
    get_messages_by_conversation_id,
    get_message_by_id,
    create_message,
    delete_message,
    update_message_favor
)
from app.dependencies.auth import get_current_user
from app.utils.uuid import bytes_to_uuid_string, uuid_string_to_bytes
from app.services.llm_service import llm_service
from app.services.prompt_service import prompt_service
from app.services.context_compressor import get_compressor
from app.services.session_state import get_session_state
from app.services.model_router import get_router
from app.services.tool_retry import execute_with_retry
from app.services.task_planner import get_planner
from app.services.langgraph_multi_agent import (
    build_task_policy,
    judge_langgraph_chat_answer,
    prepare_langgraph_chat_context,
    rebuild_approved_langgraph_chat_context,
    resume_langgraph_chat_context,
)
from app.services.agent_code_policy import validate_single_generated_file

# Global registry for conversation interrupt events
# Key: conversation_id (str), Value: asyncio.Event
_interrupt_events: dict[str, asyncio.Event] = {}

router = APIRouter()


class HumanReviewDecision(BaseModel):
    approved: bool
    feedback: str = Field(default="", max_length=2000)


@router.get("/conversations", response_model=list[ConversationSchema])
def get_conversations(db: Session = Depends(get_db), current_user: UserSchema = Depends(get_current_user)):
    """Get all conversations for the current user"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    
    conversations = get_conversations_by_user_id(db, user_id_bytes)
    
    # Convert binary IDs to string for response
    result = []
    for conv in conversations:
        result.append(ConversationSchema(
            id=bytes_to_uuid_string(conv.id),
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at
        ))
    
    return result


@router.post("/conversations", response_model=ConversationSchema)
def create_new_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Create a new conversation"""
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    db_conversation = create_conversation(db, user_id_bytes, conversation.title)
    
    # Return with string ID
    return ConversationSchema(
        id=bytes_to_uuid_string(db_conversation.id),
        title=db_conversation.title,
        created_at=db_conversation.created_at,
        updated_at=db_conversation.updated_at
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationSchema)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get a specific conversation by ID"""
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check if conversation belongs to current user
    if conversation.user_id != user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation"
        )
    
    # Return with string ID
    return ConversationSchema(
        id=bytes_to_uuid_string(conversation.id),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at
    )


@router.put("/conversations/{conversation_id}", response_model=ConversationSchema)
def update_conversation(
    conversation_id: str,
    conversation_update: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update a conversation's title"""
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check if conversation belongs to current user
    if conversation.user_id != user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this conversation"
        )
    
    # Update title
    updated_conv = update_conversation_title(db, conv_id_bytes, conversation_update.title)
    
    # Return with string ID
    return ConversationSchema(
        id=bytes_to_uuid_string(updated_conv.id),
        title=updated_conv.title,
        created_at=updated_conv.created_at,
        updated_at=updated_conv.updated_at
    )


@router.delete("/conversations/{conversation_id}", response_model=dict)
def delete_user_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Delete a conversation (soft delete)"""
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check if conversation belongs to current user
    if conversation.user_id != user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this conversation"
        )
    
    # Delete conversation
    success = delete_conversation(db, conv_id_bytes)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
    
    return {"message": "Conversation deleted successfully"}


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageSchema])
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Get all messages for a conversation"""
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check if conversation belongs to current user
    if conversation.user_id != user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation's messages"
        )
    
    # Get messages
    messages = get_messages_by_conversation_id(db, conv_id_bytes)
    
    # Convert binary IDs to string for response
    result = []
    for msg in messages:
        result.append(MessageSchema(
            id=bytes_to_uuid_string(msg.id),
            conversation_id=bytes_to_uuid_string(msg.conversation_id),
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            is_favored=msg.is_favored,
            metadata=msg.msg_metadata
        ))
    
    return result


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    message: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Send a message to a conversation and get streaming assistant response"""
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Check if conversation belongs to current user
    if conversation.user_id != user_id_bytes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages to this conversation"
        )

    session_state = get_session_state(conversation_id)
    if session_state.is_waiting_for_human():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This conversation is waiting for your confirmation.",
        )

    history_messages = get_messages_by_conversation_id(db, conv_id_bytes)

    if message.reconnect:
        user_message = next((m for m in reversed(history_messages) if m.role == "user"), None)
        if not user_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user message found to reconnect"
            )
        message.content = user_message.content
    else:
        user_message = create_message(
            db=db,
            conversation_id=conv_id_bytes,
            role="user",
            content=message.content
        )

    # Generate user message schema for streaming response
    user_message_schema = {
        "id": bytes_to_uuid_string(user_message.id),
        "conversation_id": bytes_to_uuid_string(user_message.conversation_id),
        "role": user_message.role,
        "content": user_message.content,
        "created_at": user_message.created_at.isoformat() if user_message.created_at else None,
        "is_favored": user_message.is_favored,
        "metadata": user_message.msg_metadata
    }

    # Choose mode based on enable_agent flag
    if message.enable_agent:
        # Agent mode with tool calling
        return StreamingResponse(
            _agent_event_generator(
                db, conv_id_bytes, user_id_bytes, message, user_message_schema,
                conversation_id=conversation_id, request=request,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )
    else:
        # Original QA mode
        return StreamingResponse(
            _qa_event_generator(db, conv_id_bytes, message, user_message_schema),
            media_type="text/event-stream"
        )


async def _agent_event_generator(
    db, conv_id_bytes, user_id_bytes, message, user_message_schema,
    conversation_id: str = None, request: Request | None = None,
    human_decision: dict | None = None, pending_human: dict | None = None,
):
    """Agent event generator powered by app.services.autonomous_agent.

    Wires autonomous-agent events to SSE:

        thinking / action / observation / reflection -> typed SSE events
        finish                                        -> also streamed as
                                                       assistant_chunk so the
                                                       existing UI gets the answer
        ask                                           -> ask event with content
        done                                          -> run_done statistics meta event
        error                                         -> assistant_chunk with error msg
    """
    # Send an immediate event so a slow retrieval/model request never looks
    # like a frozen chat window to the user.
    yield f"data: {json.dumps({'type': 'thinking', 'data': {'step': 0, 'agent_name': '任务准备', 'transition': '收到问题后，先整理本轮所需的上下文和可用能力。', 'content': '正在准备回答'}})}\n\n"
    if request is not None and await request.is_disconnected():
        return

    from app.services.autonomous_agent import AutonomousAgent
    from app.services.context_compressor import get_compressor
    from app.services.session_state import get_session_state
    from app.services.tool_service import tool_service
    from app.services.sandbox_service import sandbox_service
    from app.tools import url_fetch_tool

    model_to_use = message.model or "deepseek:deepseek-v4-flash"

    # Keep url_fetch's internal LLM in sync with this conversation's model
    try:
        url_fetch_tool.set_tool_llm_model(model_to_use)
    except Exception:
        pass

    # Sandbox: 鑾峰彇浼氳瘽绾ф矙鐩掕矾寰勶紙鍚屼竴浼氳瘽鍐呮墍鏈夊伐鍏峰叡浜級
    session_sandbox_path = sandbox_service.ensure_sandbox_exists(user_id_bytes)
    # 濡傛灉鏈変細璇滻D锛屼娇鐢ㄤ細璇濈骇娌欑洅瀛愮洰褰曚繚璇侀殧绂绘€?
    if conv_id_bytes:
        import binascii
        session_id = binascii.hexlify(conv_id_bytes).decode('ascii')
        session_sandbox_path = sandbox_service.ensure_session_sandbox(user_id_bytes, session_id)

    # Tool definitions from user's enabled tools
    direct_answer_mode = AutonomousAgent.should_answer_directly(message.content)
    tool_definitions = [] if direct_answer_mode else tool_service.get_user_enabled_tools(db, user_id_bytes)
    task_policy = build_task_policy(message.content)
    blocked_tools = set(task_policy.get("blocked_tools") or [])
    tool_definitions = [
        definition for definition in tool_definitions
        if definition.get("function", {}).get("name") not in blocked_tools
    ]

    # Tool executor -> tool_service (浣跨敤鍥哄畾鐨勪細璇濇矙鐩掕矾寰?
    written_code_file: str | None = None
    tool_call_signatures: set[str] = set()
    tool_call_counts: dict[str, int] = {}

    async def tool_executor(name: str, params: dict) -> dict:
        if direct_answer_mode:
            return {
                "success": False,
                "error": "Tools are disabled for this explanatory request.",
                "tool": name,
            }
        if name in blocked_tools:
            return {
                "success": False,
                "error": "该能力已由其他 Agent 完成，或本轮没有得到用户的写入授权。",
                "tool": name,
            }
        signature = f"{name}:{json.dumps(params or {}, ensure_ascii=False, sort_keys=True)}"
        if signature in tool_call_signatures:
            return {
                "success": False,
                "error": "相同工具和参数已经执行过，本轮不再重复调用。",
                "tool": name,
            }
        if tool_call_counts.get(name, 0) >= 2:
            return {
                "success": False,
                "error": "该工具本轮已达到调用上限，请基于已有结果完成回答。",
                "tool": name,
            }
        tool_call_signatures.add(signature)
        tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

        nonlocal written_code_file
        if name == "file_write":
            allowed, error, normalized_path = validate_single_generated_file(
                written_code_file, params.get("path", "")
            )
            if not allowed:
                return {
                    "success": False,
                    "error": error,
                    "tool": name,
                }
            written_code_file = normalized_path

        async def _exec():
            return await tool_service.execute_tool(
                tool_id=name, params=params, sandbox_path=session_sandbox_path,
            )
        try:
            return await execute_with_retry(_exec)
        except Exception as e:
            return {"success": False, "error": str(e), "tool": name}

    # Check both the local event and persistent state so an interrupt request
    # handled by another Uvicorn worker still stops this run.
    class PersistentInterruptEvent(asyncio.Event):
        def is_set(self):
            if super().is_set():
                return True
            return get_session_state(conv_id_str).get("status") == "interrupt_requested"

    interrupt_event = PersistentInterruptEvent()
    conv_id_str = conversation_id or bytes_to_uuid_string(conv_id_bytes)
    run_state = get_session_state(conv_id_str)
    if not run_state.is_interrupted():
        run_state.set("status", "running")
    _interrupt_events[conv_id_str] = interrupt_event
    
    agent = AutonomousAgent(
        model=model_to_use,
        enable_reflection=True,
        max_reflections=2,
        min_tool_calls_before_answer=2,
        tool_definitions=tool_definitions,
        tool_executor=tool_executor,
        interrupt_event=interrupt_event,
    )
    
    # Attach reflection store for persistent self-reflection memory
    try:
        from app.services.reflection_store import get_reflection_store
        agent._reflection_store = get_reflection_store(user_id_bytes, conv_id_str)
    except Exception as _re:
        logger.warning(f"Could not init reflection store: {_re}")

    # messages: system + history + new user message
    history_rows = get_messages_by_conversation_id(db, conv_id_bytes)
    # Load user profile and inject into system prompt (per-user portrait)
    profile_ctx = ""
    profile_service = None
    try:
        from app.services.user_profile_db_store import DBProfileStore
        from app.services.user_profile import UserProfileService
        _profile_store = DBProfileStore(db, user_id_bytes)
        profile_service = UserProfileService(
            _profile_store, llm_service=llm_service, model=model_to_use,
        )
        _profile = profile_service.get_or_create()
        profile_ctx = _profile.to_context_string()
    except Exception as _e:
        logger.warning(f"profile load failed (non-fatal): {_e}")

    # Check for resume state (interrupt/resume flow)
    session_state = get_session_state(bytes_to_uuid_string(conv_id_bytes))
    resume_state = session_state.get_resume_state()
    is_resuming = False
    if resume_state:
        is_resuming = True
        session_state.set_resumed()

    if human_decision and pending_human:
        try:
            multi_agent_context = resume_langgraph_chat_context(
                trace_id=pending_human["trace_id"], decision=human_decision,
            )
        except Exception as exc:
            logger.info("Native LangGraph resume unavailable; rebuilding checkpoint: %s", exc)
            multi_agent_context = rebuild_approved_langgraph_chat_context(
                user_id=user_id_bytes,
                conversation_id=conv_id_str,
                user_input=message.content,
                profile_context=profile_ctx,
                direct_answer_mode=direct_answer_mode,
                decision=human_decision,
            )
    else:
        multi_agent_context = prepare_langgraph_chat_context(
            user_id=user_id_bytes,
            conversation_id=conv_id_str,
            user_input=message.content,
            profile_context=profile_ctx,
            direct_answer_mode=direct_answer_mode,
        )
    agent.preloaded_evidence = list(multi_agent_context.get("evidence_refs") or [])
    agent.profile_context = profile_ctx
    if multi_agent_context.get("evidence_refs"):
        # The retrieval Agent already supplied evidence; do not ask the
        # generation loop to run another retrieval path for the same request.
        blocked_tools.update({"knowledge_search", "knowledge_graph", "skill_graph"})
        agent.tool_definitions = [
            definition for definition in agent.tool_definitions
            if definition.get("function", {}).get("name") not in blocked_tools
        ]
        agent._tool_name_set = {
            definition.get("function", {}).get("name")
            for definition in agent.tool_definitions
            if definition.get("function", {}).get("name")
        }
        context_policy = multi_agent_context.get("task_policy") or {}
        if not context_policy.get("requires_execution") and not context_policy.get("requires_live_search"):
            removed_names = {
                definition.get("function", {}).get("name")
                for definition in agent.tool_definitions
            }
            blocked_tools.update(name for name in removed_names if name)
            agent.tool_definitions = []
            agent._tool_name_set = set()

    base_system = agent.system_prompt()
    if profile_ctx:
        system_content = (base_system + "\n\n## User profile (use this to personalise responses)\n"
                         + profile_ctx)
    else:
        system_content = base_system
    if is_resuming and resume_state:
        # Restore from saved state and append new user message
        msgs = resume_state["messages"] + [{"role": "user", "content": message.content}]
    else:
        msgs = [{"role": "system", "content": system_content}]
        for m in history_rows:
            if m.role in ("user", "assistant"):
                msgs.append({"role": m.role, "content": m.content})
        if not getattr(message, "reconnect", False):
            msgs.append({"role": "user", "content": message.content})

    if multi_agent_context.get("context"):
        msgs.insert(1, {"role": "system", "content": multi_agent_context["context"]})
        logger.info(
            "chat multi-agent context injected trace=%s evidence=%d",
            multi_agent_context.get("trace_id"),
            len(multi_agent_context.get("evidence_refs") or []),
        )

    # Compress context if too long for the model
    try:
        compressor = get_compressor(llm_service=llm_service)
        msgs = compressor.compress(msgs, model=model_to_use)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Context compression skipped: {e}")

    assistant_content = ""
    transcript = list((pending_human or {}).get("transcript") or [])
    asked_user = False  # True when the agent asked a clarifying question
    answer_started_at = None  # for timing

    def merge_tool_evidence(data: dict) -> list[dict]:
        """Promote retrieval-tool results into the shared evidence state."""
        if data.get("tool") != "web_search" or data.get("success") is False:
            return []
        raw = data.get("raw") or {}
        results = raw.get("results") if isinstance(raw, dict) else None
        if not isinstance(results, list):
            return []
        evidence_refs = multi_agent_context.setdefault("evidence_refs", [])
        known_urls = {str(ref.get("source_url") or "") for ref in evidence_refs}
        domain_counts: dict[str, int] = {}
        for ref in evidence_refs:
            domain = urlparse(str(ref.get("source_url") or "")).netloc.lower().removeprefix("www.")
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        added = []
        for item in results[:5]:
            url = str(item.get("url") or "").strip()
            if not url or url in known_urls:
                continue
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            domain_limit = 1 if domain.endswith("runoob.com") else 2
            if domain and domain_counts.get(domain, 0) >= domain_limit:
                continue
            ref = {
                "index": len(evidence_refs) + 1,
                "title": str(item.get("title") or "互联网参考资料"),
                "doc_id": f"web:{len(evidence_refs) + 1}",
                "chunk_id": 0,
                "score": float(item.get("score") or 0.5),
                "snippet": str(item.get("content") or "")[:220],
                "category": "web",
                "source_url": url,
            }
            evidence_refs.append(ref)
            added.append(ref)
            known_urls.add(url)
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        return added

    graph_events = list(multi_agent_context.get("events") or [])
    if pending_human:
        graph_events = graph_events[len(transcript):]
    for process_event in graph_events:
        event_type = process_event.get("type")
        data = process_event.get("data") or {}
        if event_type not in {"thinking", "observation", "reflection"}:
            continue
        transcript.append(copy.deepcopy({"kind": event_type, **data}))
        yield f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"
        await asyncio.sleep(0.015)

    if multi_agent_context.get("human_status") == "needs_human":
        interrupt_payload = dict(multi_agent_context.get("human_interrupt") or {})
        interrupt_payload.setdefault("title", "需要你的确认")
        interrupt_payload.setdefault("message", "这一步可能产生外部影响，请确认是否继续。")
        session_state.set_human_waiting({
            "trace_id": multi_agent_context.get("trace_id"),
            "user_input": message.content,
            "model": model_to_use,
            "direct_answer_mode": direct_answer_mode,
            "transcript": transcript,
            "interrupt": interrupt_payload,
        })
        yield f"data: {json.dumps({'type': 'human_required', 'data': interrupt_payload})}\n\n"
        yield "data: [DONE]\n\n"
        return

    if human_decision and not human_decision.get("approved"):
        cancelled = "已取消本次执行，系统没有继续进行后续操作。"
        create_message(
            db=db, conversation_id=conv_id_bytes, role="assistant", content=cancelled,
            metadata={"transcript": transcript, "human_review": human_decision},
        )
        session_state.finish_human_review(False, human_decision.get("feedback", ""))
        yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': cancelled})}\n\n"
        yield "data: [DONE]\n\n"
        return

    if human_decision:
        session_state.finish_human_review(True, human_decision.get("feedback", ""))

    # Prepare initial state for resume
    initial_state = None
    if is_resuming and resume_state:
        initial_state = {
            "tool_history": resume_state.get("tool_history", []),
            "step": resume_state.get("step", 0),
            "reflections": resume_state.get("reflections", []),
        }

    try:
        async for event in agent.run(msgs, user_input=message.content, initial_state=initial_state):
            kind = event.get("type")
            data = event.get("data", {}) or {}

            if kind == "thinking":
                data.setdefault("agent", "generation")
                data.setdefault("agent_name", "生成 Agent")
                data.setdefault("transition", "任务信息已经准备，接下来由生成 Agent 组织回答。")
                transcript.append(copy.deepcopy({"kind": "thinking", **data}))
                yield f"data: {json.dumps({'type': 'thinking', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
            elif kind == "action":
                data.setdefault("agent", "generation")
                data.setdefault("agent_name", "生成 Agent")
                data.setdefault("transition", "为完成当前任务，接下来调用所需工具。")
                transcript.append(copy.deepcopy({"kind": "action", **data}))
                yield f"data: {json.dumps({'type': 'action', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
            elif kind == "observation":
                data.setdefault("agent", "generation")
                data.setdefault("agent_name", "生成 Agent")
                added_evidence = merge_tool_evidence(data)
                if added_evidence:
                    data["evidence_refs"] = multi_agent_context.get("evidence_refs") or []
                transcript.append(copy.deepcopy({"kind": "observation", **data}))
                yield f"data: {json.dumps({'type': 'observation', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
            elif kind == "reflection":
                data.setdefault("agent", "review")
                data.setdefault("agent_name", "审核 Agent")
                data.setdefault("transition", "回答草稿已经形成，接下来检查是否需要补充或修正。")
                multi_agent_context["review"] = copy.deepcopy(data)
                transcript.append(copy.deepcopy({"kind": "reflection", **data}))
                yield f"data: {json.dumps({'type': 'reflection', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
            elif kind == "finish":
                content = event.get("content", "") or ""
                assistant_content = content
                if content:
                    # Stream chunks FIRST for typewriter effect
                    step = 6
                    for ci in range(0, len(content), step):
                        chunk = content[ci:ci + step]
                        yield "data: " + json.dumps({"type": "assistant_chunk", "content": chunk}) + "\n\n"
                        await asyncio.sleep(0.015)
                # Send finish AFTER all chunks
                yield "data: " + json.dumps({"type": "finish", "content": ""}) + chr(10) + chr(10)
                await asyncio.sleep(0.015)
            elif kind == "ask":
                content = event.get("content", "") or ""
                asked_user = True
                # Keep assistant_content as the question so the renderer can show it,
                # but we will skip persistence/title/profile-analysis for this run.
                assistant_content = content
                yield f"data: {json.dumps({'type': 'ask', 'data': {'content': content}})}\n\n"
                await asyncio.sleep(0.015)
            elif kind == "interrupted":
                # Save state for resume
                session_state.set_interrupted(
                    messages=msgs,
                    tool_history=[{"tool": t["tool"], "params": t["params"]} for t in getattr(agent, 'tool_history', [])] if hasattr(agent, 'tool_history') else [],
                    step=data.get("step", 0),
                    reflections=getattr(agent, 'reflections', []) if hasattr(agent, 'reflections') else [],
                )
                yield f"data: {json.dumps({'type': 'interrupted', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
                return
            elif kind == "done":
                yield f"data: {json.dumps({'type': 'run_done', 'data': data})}\n\n"
                await asyncio.sleep(0.015)
                break
            elif kind == "error":
                err = data.get("message", "unknown error")
                logger.error("Agent model/tool error: %s", err)
                assistant_content = "模型服务暂时不可用，请稍后重试。"
                yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': assistant_content})}\n\n"
                await asyncio.sleep(0.015)
                break

    except Exception as e:
        logger.error(f"Error in agent mode: {e}", exc_info=True)
        assistant_content = "模型服务暂时不可用，请稍后重试。"
        yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': assistant_content})}\n\n"
        await asyncio.sleep(0.015)

    if not assistant_content.strip():
        assistant_content = "抱歉，本次没有生成有效回答。请重新提问。"
        yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': assistant_content})}\n\n"
        await asyncio.sleep(0.015)

    judge_result = judge_langgraph_chat_answer(assistant_content, multi_agent_context)
    judge_event = {
        "step": 0,
        "agent": "judge",
        "agent_name": "裁判 Agent",
        "transition": "回答已经生成并完成必要检查，最后由裁判 Agent 核对可信度和风险。",
        "overall": (
            "PASS" if judge_result.get("risk_level") == "low"
            else ("CHECK" if judge_result.get("risk_level") == "medium" else "FAIL")
        ),
        "content": judge_result.get("proposed_action") or "已完成最终检查。",
        "risk_level": judge_result.get("risk_level"),
        "confidence": judge_result.get("confidence"),
        "proposed_action": judge_result.get("proposed_action"),
        "cited_sources": judge_result.get("cited_sources"),
        "trace_id": judge_result.get("trace_id"),
    }
    transcript.append(copy.deepcopy({"kind": "reflection", **judge_event}))
    yield f"data: {json.dumps({'type': 'reflection', 'data': judge_event})}\n\n"
    await asyncio.sleep(0.015)

    # Trigger async profile analysis (fire-and-forget, non-blocking)
    if (profile_service is not None
            and assistant_content and assistant_content.strip()
            and not assistant_content.startswith("Error:")
            and not assistant_content.startswith("鎶辨瓑")):
        try:
            recent = [
                {"role": "user", "content": message.content},
                {"role": "assistant", "content": assistant_content},
            ]
            asyncio.create_task(profile_service.analyze_and_update(recent))
        except Exception as _pe:
            logger.warning(f"profile analysis kick-off failed: {_pe}")

    # Persist assistant message with transcript metadata.
    # Skip if the agent asked a clarifying question (we don't want to store the
    # question itself as the assistant's final answer) OR if the content is empty
    # / only an error message.
    skip_persist = (
        asked_user
        or not assistant_content.strip()
        or assistant_content.startswith("Error:")
        or assistant_content.startswith("鎶辨瓑")  # "鎶辨瓑"
    )
    if not skip_persist:
        try:
            existing_rows = get_messages_by_conversation_id(db, conv_id_bytes)
            last_user_index = -1
            for i, row in enumerate(existing_rows):
                if row.role == "user" and (row.content or "").strip() == (message.content or "").strip():
                    last_user_index = i
            duplicate_assistant_exists = (
                last_user_index >= 0
                and any(
                    row.role == "assistant" and (row.content or "").strip()
                    for row in existing_rows[last_user_index + 1:]
                )
            )
            if duplicate_assistant_exists:
                logger.info("Skipping duplicate assistant persistence for conversation %s", bytes_to_uuid_string(conv_id_bytes))
                skip_persist = True
        except Exception as e:
            logger.warning(f"Duplicate assistant check failed: {e}")

    if not skip_persist:
        try:
            metadata = {}
            if transcript:
                metadata["transcript"] = transcript
                metadata["run_meta"] = {
                    "steps": len([t for t in transcript if t.get("kind") in ("thinking", "action", "observation")]),
                    "tools": len([t for t in transcript if t.get("kind") == "action"]),
                    "reflections": len([t for t in transcript if t.get("kind") == "reflection"]),
                }
            metadata["multi_agent"] = {
                "engine": "langgraph",
                "trace_id": multi_agent_context.get("trace_id"),
                "diagnosis": multi_agent_context.get("diagnosis") or {},
                "task_policy": multi_agent_context.get("task_policy") or {},
                "evidence_refs": multi_agent_context.get("evidence_refs") or [],
                "rule_hits": multi_agent_context.get("rule_hits") or [],
                "human_review_required": bool(multi_agent_context.get("human_review_required")),
                "human_status": multi_agent_context.get("human_status") or "not_required",
                "judge": judge_result,
                "review": multi_agent_context.get("review") or {},
            }
            metadata["evidence_refs"] = multi_agent_context.get("evidence_refs") or []
            create_message(
                db=db,
                conversation_id=conv_id_bytes,
                role="assistant",
                content=assistant_content,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error persisting assistant message: {e}")
    else:
        logger.info("Skipping assistant message persistence (asked_user=%s, content_len=%d)",
                    asked_user, len(assistant_content or ""))

    # Auto-generate title for new conversations
    # Skip when the agent asked a question, errored, or answered with the placeholder.
    skip_title = (
        asked_user
        or not (assistant_content or "").strip()
        or assistant_content.startswith("Error:")
        or assistant_content.startswith("鎶辨瓑")
    )
    if not skip_title:
        try:
            conversation = get_conversation_by_id(db, conv_id_bytes)
            is_new = (conversation is not None
                      and conversation.title in ["New Chat", "新对话", "鏂板璇?"])
            if is_new and assistant_content:
                title_prompt = prompt_service.get_prompt_content(
                    "conversation.title_generator",
                    conversation_content=("鐢ㄦ埛: " + (message.content or "") + "\n鍔╂墜: " + assistant_content[:100] + "..."),
                )
                if title_prompt:
                    generated_title = llm_service.call_model(
                        [{"role": "system", "content": "你是一个对话标题生成器。"},
                         {"role": "user", "content": title_prompt}],
                        temperature=0.3, top_p=0.5,
                    )
                    if generated_title:
                        generated_title = generated_title.strip()
                        update_conversation_title(db, conv_id_bytes, generated_title)
                        yield f"data: {json.dumps({'type': 'title_update', 'data': {'conversation_id': bytes_to_uuid_string(conv_id_bytes), 'title': generated_title}})}\n\n"
                        await asyncio.sleep(0.015)
        except Exception as e:
            logger.error(f"Error generating conversation title: {e}")

    yield "data: [DONE]\n\n"
    await asyncio.sleep(0.015)

async def _qa_event_generator(db, conv_id_bytes, message, user_message_schema):
    """Original QA mode event generator"""
    logger.info(f"Starting QA event generator for conversation {conv_id_bytes.hex()}")

    # Note: user_message is NOT sent here - frontend already created it in handleSend()

    # Get conversation history for LLM
    messages = get_messages_by_conversation_id(db, conv_id_bytes)

    # Format messages for LLM input
    llm_messages = []
    for msg in messages:
        llm_messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # Add the new user message to the history
    llm_messages.append({
        "role": "user",
        "content": message.content
    })

    # Initialize assistant response content
    assistant_content = ""

    # Call streaming LLM service 鈥?run sync generator in a thread and
    # pump chunks through an async queue for true real-time SSE streaming.
    try:
        logger.info(f"Calling LLM service with messages: {llm_messages}")
        model_to_use = message.model if message.model else None

        q: asyncio.Queue = asyncio.Queue()

        def sync_worker():
            try:
                for chunk in llm_service.call_model(llm_messages, model=model_to_use, stream=True):
                    q.put_nowait(chunk)
                q.put_nowait(None)  # sentinel: end of stream
            except Exception as e:
                logger.error(f"sync LLM stream error: {e}")
                q.put_nowait(None)
            finally:
                try:
                    q.put_nowait(None)
                except Exception:
                    pass

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, sync_worker)

        while True:
            chunk = await q.get()
            if chunk is None:
                break
            logger.info(f"Got LLM chunk: '{chunk}'")
            assistant_content += chunk
            yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': chunk})}\n\n"
    except Exception as e:
        logger.error(f"Error calling LLM service: {e}")
        assistant_content = f"Error: {str(e)}"
        yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': assistant_content})}\n\n"

    # Ensure assistant content is not empty
    if not assistant_content.strip():
        logger.warning("Assistant content is empty, using default message")
        assistant_content = "抱歉，本次没有生成有效回复。请重新提问。"
        yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': assistant_content})}\n\n"

    # Create assistant message in database (only save, don't send to frontend)
    logger.info(f"Creating assistant message with content: '%s'", assistant_content[:80])
    # Skip persistence when there is nothing meaningful to save
    if (not assistant_content.strip()
            or assistant_content.startswith("Error:")
            or assistant_content.startswith("鎶辨瓑")):
        logger.warning("Skipping persistence in QA mode: empty/error/placeholder content")
        yield "data: [DONE]\n\n"
        return
    assistant_message = create_message(
        db=db,
        conversation_id=conv_id_bytes,
        role="assistant",
        content=assistant_content
    )

    # Check if this is a new conversation
    conversation = get_conversation_by_id(db, conv_id_bytes)
    is_new_conversation = len(messages) == 0 or (conversation and conversation.title in ["New Chat", "新对话", "鏂板璇?"])

    if is_new_conversation:
        try:
            title_prompt = prompt_service.get_prompt_content(
                "conversation.title_generator",
                conversation_content=f"鐢ㄦ埛: {message.content}\n鍔╂墜: {assistant_content[:100]}..."
            )
            if title_prompt:
                generated_title = llm_service.call_model(
                    [{"role": "system", "content": "你是一个对话标题生成器。"}, {"role": "user", "content": title_prompt}],
                    temperature=0.3, top_p=0.5
                )
                if generated_title:
                    generated_title = generated_title.strip()
                    update_conversation_title(db, conv_id_bytes, generated_title)
                    yield f"data: {json.dumps({'type': 'title_update', 'data': {'conversation_id': bytes_to_uuid_string(conv_id_bytes), 'title': generated_title}})}\n\n"
        except Exception as e:
            logger.error(f"Error generating conversation title: {e}")

    yield "data: [DONE]\n\n"


@router.get("/conversations/{conversation_id}/human-review")
def get_human_review(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    if not conversation or conversation.user_id != user_id_bytes:
        raise HTTPException(status_code=404, detail="Conversation not found")

    pending = get_session_state(conversation_id).get_human_waiting()
    if not pending:
        return {"status": "idle"}
    return {
        "status": "waiting",
        "user_input": pending.get("user_input", ""),
        "transcript": pending.get("transcript", []),
        "review": pending.get("interrupt", {}),
    }


@router.post("/conversations/{conversation_id}/human-review")
def decide_human_review(
    conversation_id: str,
    decision: HumanReviewDecision,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    conversation = get_conversation_by_id(db, conv_id_bytes)
    if not conversation or conversation.user_id != user_id_bytes:
        raise HTTPException(status_code=404, detail="Conversation not found")

    pending = get_session_state(conversation_id).get_human_waiting()
    if not pending:
        raise HTTPException(status_code=409, detail="No pending confirmation for this conversation")
    user_message = next(
        (row for row in reversed(get_messages_by_conversation_id(db, conv_id_bytes)) if row.role == "user"),
        None,
    )
    if not user_message:
        raise HTTPException(status_code=404, detail="Original user message not found")

    message = MessageCreate(
        content=pending.get("user_input") or user_message.content,
        model=pending.get("model"),
        enable_agent=True,
        reconnect=True,
    )
    user_message_schema = {
        "id": bytes_to_uuid_string(user_message.id),
        "conversation_id": conversation_id,
        "role": "user",
        "content": user_message.content,
        "created_at": user_message.created_at.isoformat() if user_message.created_at else None,
    }
    return StreamingResponse(
        _agent_event_generator(
            db, conv_id_bytes, user_id_bytes, message, user_message_schema,
            conversation_id=conversation_id,
            request=request,
            human_decision=decision.model_dump(),
            pending_human=pending,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations/{conversation_id}/agent-status")
def get_agent_status(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Check if the last assistant message was interrupted (incomplete).

    Frontend uses this to decide whether to auto-continue generation.
    """
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    user_id_bytes = uuid_string_to_bytes(current_user.id)

    msgs = get_messages_by_conversation_id(db, conv_id_bytes)
    last_msg = msgs[-1] if msgs else None

    if last_msg and last_msg.role == "assistant":
        meta = last_msg.msg_metadata or {}
        if meta.get("interrupted"):
            return {"status": "interrupted", "content": last_msg.content, "can_continue": True}

    return {"status": "idle", "can_continue": False}


@router.put("/messages/{message_id}/favor")
def update_message_favor_status(
    message_id: str,
    favor_update: MessageFavorUpdate,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Update message favor status"""
    try:
        # Convert message ID from string to bytes
        message_id_bytes = uuid_string_to_bytes(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message_id format")
    
    message = update_message_favor(db, message_id_bytes, favor_update.is_favored)
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Return updated message
    return {
        "id": bytes_to_uuid_string(message.id),
        "conversation_id": bytes_to_uuid_string(message.conversation_id),
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "is_favored": message.is_favored,
        "metadata": message.msg_metadata
    }


@router.post("/conversations/{conversation_id}/interrupt")
def interrupt_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user),
):
    """Interrupt the current agent execution.
    
    The agent will stop at the next checkpoint and save its state.
    The user can then send a new message to continue with additional context.
    """
    try:
        conv_id_bytes = uuid_string_to_bytes(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format")
    
    user_id_bytes = uuid_string_to_bytes(current_user.id)
    
    # Verify conversation belongs to user
    conversation = get_conversation_by_id(db, conv_id_bytes)
    if not conversation or conversation.user_id != user_id_bytes:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Set interrupt flag in session state
    state = get_session_state(conversation_id)
    state.set("status", "interrupt_requested")
    interrupt_event = _interrupt_events.get(conversation_id)
    if interrupt_event is not None:
        interrupt_event.set()
    
    return {"interrupted": True, "conversation_id": conversation_id}


@router.delete("/messages/{message_id}")
def delete_message_endpoint(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: UserSchema = Depends(get_current_user)
):
    """Delete a message"""
    try:
        message_id_bytes = uuid_string_to_bytes(message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message_id format")
    
    message = get_message_by_id(db, message_id_bytes)
    
    # Check if message exists
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Delete the message
    try:
        success = delete_message(db, message_id_bytes)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete message"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete message: {str(e)}"
        )
    
    return {"message": "Message deleted successfully"}




