from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies.auth import get_current_user
from app.schemas.user import User as UserSchema
from app.services.llm_service import llm_service

router = APIRouter(prefix="/models", tags=["models"])


class ModelInfo(BaseModel):
    name: str
    provider: str
    description: str
    max_tokens: int = 4096


class ProviderInfo(BaseModel):
    name: str
    models: list
    has_api_key: bool


@router.get("/available", response_model=dict)
def get_available_models(current_user: UserSchema = Depends(get_current_user)):
    """Get all available models grouped by provider"""
    providers = llm_service.get_available_providers()

    # Get available models from prompt_service.config
    available_models = prompt_service.config.get("available_models", [])

    # Return as a simple structure for frontend
    all_models = []
    for p in providers:
        provider_name = p["name"]
        for model in p["models"]:
            # Get model description from config
            model_info = next((m for m in available_models if m.get("name") == model), None)

            all_models.append({
                "id": f"{provider_name}:{model}",
                "name": model,
                "provider": provider_name,
                "description": model_info.get("description", f"{provider_name} {model}") if model_info else f"{provider_name} {model}",
                "max_tokens": model_info.get("max_tokens", 4096) if model_info else 4096
            })

    return {
        "models": all_models,
        "default_model": llm_service.default_model_config.get("name", "deepseek-v4-pro"),
        "default_provider": llm_service.default_model_config.get("provider", "deepseek")
    }


# Import prompt_service here to avoid circular import
from app.services.prompt_service import prompt_service
