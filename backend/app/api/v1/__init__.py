from fastapi import APIRouter
from app.api.v1 import auth, conversation, models, agent, user_profile, knowledge_base, learning, agent_runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(conversation.router, prefix="", tags=["conversation"])
api_router.include_router(models.router, prefix="", tags=["models"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(agent_runs.router, prefix="", tags=["agent-runs"])
api_router.include_router(user_profile.router, prefix="/user", tags=["user_profile"])
api_router.include_router(knowledge_base.router, prefix="", tags=["knowledge_base"])
api_router.include_router(learning.router, prefix="", tags=["learning"])
