"""
Disabled Billing API - All users have maximum privileges by default.
No Stripe integration, no payment required.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
from utils.logger import logger
from utils.config import config, EnvMode
from services.supabase import DBConnection
from utils.auth_utils import get_current_user_id_from_jwt
from pydantic import BaseModel
from utils.constants import MODEL_ACCESS_TIERS, MODEL_NAME_ALIASES, HARDCODED_MODEL_PRICES
from litellm.cost_calculator import cost_per_token
import time

# Token price multiplier (kept for compatibility)
TOKEN_PRICE_MULTIPLIER = 1.5

# Initialize router
router = APIRouter(prefix="/billing", tags=["billing"])

def get_model_pricing(model: str) -> tuple[float, float] | None:
    """
    Get pricing for a model. Returns (input_cost_per_million, output_cost_per_million) or None.
    
    Args:
        model: The model name to get pricing for
        
    Returns:
        Tuple of (input_cost_per_million_tokens, output_cost_per_million_tokens) or None if not found
    """
    if model in HARDCODED_MODEL_PRICES:
        pricing = HARDCODED_MODEL_PRICES[model]
        return pricing["input_cost_per_million_tokens"], pricing["output_cost_per_million_tokens"]
    return None

# Pydantic models for request/response validation (kept for compatibility)
class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    tolt_referral: Optional[str] = None

class CreatePortalSessionRequest(BaseModel):
    return_url: str

class SubscriptionStatus(BaseModel):
    status: str 
    plan_name: Optional[str] = None
    price_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_end: Optional[datetime] = None
    minutes_limit: Optional[int] = None
    cost_limit: Optional[float] = None
    current_usage: Optional[float] = None
    has_schedule: bool = False
    scheduled_plan_name: Optional[str] = None
    scheduled_price_id: Optional[str] = None
    scheduled_change_date: Optional[datetime] = None

# Helper functions - all disabled/simplified

async def get_stripe_customer_id(client, user_id: str) -> Optional[str]:
    """Disabled - always return None."""
    return None

async def create_stripe_customer(client, user_id: str, email: str) -> str:
    """Disabled - return fake customer ID."""
    return f"fake_customer_{user_id}"

async def get_user_subscription(user_id: str) -> Optional[Dict]:
    """Return maximum tier subscription for all users."""
    return {
        'id': f'fake_sub_{user_id}',
        'status': 'active',
        'plan': {'nickname': 'Maximum Tier'},
        'price_id': 'maximum_tier',
        'cancel_at_period_end': False,
        'current_period_start': int(datetime.now(timezone.utc).timestamp()),
        'current_period_end': int((datetime.now(timezone.utc).replace(year=datetime.now().year + 1)).timestamp()),
        'items': {
            'data': [{
                'price': {'id': 'maximum_tier'},
                'current_period_end': int((datetime.now(timezone.utc).replace(year=datetime.now().year + 1)).timestamp())
            }]
        }
    }

async def calculate_monthly_usage(client, user_id: str) -> float:
    """Return 0 usage for all users."""
    logger.info("Billing disabled - returning 0 usage")
    return 0.0

async def get_usage_logs(client, user_id: str, page: int = 0, items_per_page: int = 1000) -> Dict:
    """Return empty usage logs."""
    return {"logs": [], "has_more": False}

def calculate_token_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculate the cost for tokens using the same logic as the monthly usage calculation."""
    try:
        # Ensure tokens are valid integers
        prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else 0
        completion_tokens = int(completion_tokens) if completion_tokens is not None else 0
        
        # Try to resolve the model name using MODEL_NAME_ALIASES first
        resolved_model = MODEL_NAME_ALIASES.get(model, model)

        # Check if we have hardcoded pricing for this model (try both original and resolved)
        hardcoded_pricing = get_model_pricing(model) or get_model_pricing(resolved_model)
        if hardcoded_pricing:
            input_cost_per_million, output_cost_per_million = hardcoded_pricing
            input_cost = (prompt_tokens / 1_000_000) * input_cost_per_million
            output_cost = (completion_tokens / 1_000_000) * output_cost_per_million
            message_cost = input_cost + output_cost
        else:
            # Use litellm pricing as fallback - try multiple variations
            try:
                models_to_try = [model]
                
                # Add resolved model if different
                if resolved_model != model:
                    models_to_try.append(resolved_model)
                
                # Try without provider prefix if it has one
                if '/' in model:
                    models_to_try.append(model.split('/', 1)[1])
                if '/' in resolved_model and resolved_model != model:
                    models_to_try.append(resolved_model.split('/', 1)[1])
                    
                # Special handling for Google models accessed via OpenRouter
                if model.startswith('openrouter/google/'):
                    google_model_name = model.replace('openrouter/', '')
                    models_to_try.append(google_model_name)
                if resolved_model.startswith('openrouter/google/'):
                    google_model_name = resolved_model.replace('openrouter/', '')
                    models_to_try.append(google_model_name)
                
                # Try each model name variation until we find one that works
                message_cost = None
                for model_name in models_to_try:
                    try:
                        prompt_token_cost, completion_token_cost = cost_per_token(model_name, prompt_tokens, completion_tokens)
                        if prompt_token_cost is not None and completion_token_cost is not None:
                            message_cost = prompt_token_cost + completion_token_cost
                            break
                    except Exception as e:
                        logger.debug(f"Failed to get pricing for model variation {model_name}: {str(e)}")
                        continue
                
                if message_cost is None:
                    logger.warning(f"Could not get pricing for model {model} (resolved: {resolved_model}), returning 0 cost")
                    return 0.0
                    
            except Exception as e:
                logger.warning(f"Could not get pricing for model {model} (resolved: {resolved_model}): {str(e)}, returning 0 cost")
                return 0.0
        
        # Apply the TOKEN_PRICE_MULTIPLIER
        return message_cost * TOKEN_PRICE_MULTIPLIER
    except Exception as e:
        logger.error(f"Error calculating token cost for model {model}: {str(e)}")
        return 0.0

async def get_allowed_models_for_user(client, user_id: str):
    """
    Return ALL models for all users - no restrictions.
    """
    # Return all unique models from MODEL_NAME_ALIASES
    all_models = set()
    for short_name, full_name in MODEL_NAME_ALIASES.items():
        all_models.add(full_name)
    
    return list(all_models)

async def can_use_model(client, user_id: str, model_name: str):
    """Always allow any model for any user."""
    logger.info("Billing disabled - all models allowed for all users")
    return True, "All models available - billing disabled", []

async def check_billing_status(client, user_id: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Always return that user can run agents with maximum privileges.
    """
    logger.info("Billing disabled - maximum privileges for all users")
    return True, "Maximum privileges - billing disabled", {
        "price_id": "maximum_tier",
        "plan_name": "Maximum Tier (Billing Disabled)",
        "minutes_limit": "unlimited"
    }

# API endpoints - all simplified

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Disabled - return success without actually creating anything."""
    logger.info("Billing disabled - checkout session creation skipped")
    return {
        "session_id": "fake_session_id", 
        "url": request.success_url,  # Redirect to success URL directly
        "status": "billing_disabled",
        "message": "Billing is disabled - all users have maximum privileges"
    }

@router.post("/create-portal-session")
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Disabled - redirect to return URL."""
    logger.info("Billing disabled - portal session creation skipped")
    return {
        "url": request.return_url,
        "message": "Billing is disabled - no portal needed"
    }

@router.get("/subscription")
async def get_subscription(
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Return maximum tier subscription status for all users."""
    logger.info("Billing disabled - returning maximum tier for all users")
    
    return SubscriptionStatus(
        status="active",
        plan_name="Maximum Tier (Billing Disabled)",
        price_id="maximum_tier",
        current_period_end=datetime.now(timezone.utc).replace(year=datetime.now().year + 1),
        cancel_at_period_end=False,
        trial_end=None,
        minutes_limit=999999,  # Unlimited
        cost_limit=999999.0,   # Unlimited
        current_usage=0.0,
        has_schedule=False
    )

@router.get("/check-status")
async def check_status(
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Always return that user can run agents."""
    logger.info("Billing disabled - maximum privileges for all users")
    
    return {
        "can_run": True,
        "message": "Maximum privileges - billing disabled",
        "subscription": {
            "price_id": "maximum_tier",
            "plan_name": "Maximum Tier (Billing Disabled)",
            "minutes_limit": "unlimited"
        }
    }

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Disabled webhook - always return success."""
    logger.info("Billing disabled - webhook ignored")
    return {"status": "success", "message": "Billing disabled - webhook ignored"}

@router.get("/available-models")
async def get_available_models(
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Return ALL models with no restrictions."""
    try:
        logger.info("Billing disabled - returning all models for all users")
        
        # Get all unique full model names from MODEL_NAME_ALIASES
        all_models = set()
        model_aliases = {}
        
        for short_name, full_name in MODEL_NAME_ALIASES.items():
            # Add all unique full model names
            all_models.add(full_name)
            
            # Only include short names that don't match their full names for aliases
            if short_name != full_name and not short_name.startswith("openai/") and not short_name.startswith("anthropic/") and not short_name.startswith("openrouter/") and not short_name.startswith("xai/"):
                if full_name not in model_aliases:
                    model_aliases[full_name] = short_name
        
        # Create model info with display names for ALL models
        model_info = []
        for model in all_models:
            display_name = model_aliases.get(model, model.split('/')[-1] if '/' in model else model)
            
            # Get pricing information - check hardcoded prices first, then litellm
            pricing_info = {}
            
            # Check if we have hardcoded pricing for this model
            hardcoded_pricing = get_model_pricing(model)
            if hardcoded_pricing:
                input_cost_per_million, output_cost_per_million = hardcoded_pricing
                pricing_info = {
                    "input_cost_per_million_tokens": input_cost_per_million * TOKEN_PRICE_MULTIPLIER,
                    "output_cost_per_million_tokens": output_cost_per_million * TOKEN_PRICE_MULTIPLIER,
                    "max_tokens": None
                }
            else:
                try:
                    # Try to get pricing using cost_per_token function
                    models_to_try = []
                    
                    # Add the original model name
                    models_to_try.append(model)
                    
                    # Try to resolve the model name using MODEL_NAME_ALIASES
                    if model in MODEL_NAME_ALIASES:
                        resolved_model = MODEL_NAME_ALIASES[model]
                        models_to_try.append(resolved_model)
                        # Also try without provider prefix if it has one
                        if '/' in resolved_model:
                            models_to_try.append(resolved_model.split('/', 1)[1])
                    
                    # If model is a value in aliases, try to find a matching key
                    for alias_key, alias_value in MODEL_NAME_ALIASES.items():
                        if alias_value == model:
                            models_to_try.append(alias_key)
                            break
                    
                    # Also try without provider prefix for the original model
                    if '/' in model:
                        models_to_try.append(model.split('/', 1)[1])
                    
                    # Special handling for Google models accessed via OpenRouter
                    if model.startswith('openrouter/google/'):
                        google_model_name = model.replace('openrouter/', '')
                        models_to_try.append(google_model_name)
                    
                    # Try each model name variation until we find one that works
                    input_cost_per_token = None
                    output_cost_per_token = None
                    
                    for model_name in models_to_try:
                        try:
                            # Use cost_per_token with sample token counts to get the per-token costs
                            input_cost, output_cost = cost_per_token(model_name, 1000000, 1000000)
                            if input_cost is not None and output_cost is not None:
                                input_cost_per_token = input_cost
                                output_cost_per_token = output_cost
                                break
                        except Exception:
                            continue
                    
                    if input_cost_per_token is not None and output_cost_per_token is not None:
                        pricing_info = {
                            "input_cost_per_million_tokens": input_cost_per_token * TOKEN_PRICE_MULTIPLIER,
                            "output_cost_per_million_tokens": output_cost_per_token * TOKEN_PRICE_MULTIPLIER,
                            "max_tokens": None  # cost_per_token doesn't provide max_tokens info
                        }
                    else:
                        pricing_info = {
                            "input_cost_per_million_tokens": None,
                            "output_cost_per_million_tokens": None,
                            "max_tokens": None
                        }
                except Exception as e:
                    logger.warning(f"Could not get pricing for model {model}: {str(e)}")
                    pricing_info = {
                        "input_cost_per_million_tokens": None,
                        "output_cost_per_million_tokens": None,
                        "max_tokens": None
                    }

            model_info.append({
                "id": model,
                "display_name": display_name,
                "short_name": model_aliases.get(model),
                "requires_subscription": False,  # No subscription required
                "is_available": True,  # All models available
                **pricing_info
            })
        
        return {
            "models": model_info,
            "subscription_tier": "Maximum Tier (Billing Disabled)",
            "total_models": len(model_info)
        }
        
    except Exception as e:
        logger.error(f"Error getting available models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting available models: {str(e)}")

@router.get("/usage-logs")
async def get_usage_logs_endpoint(
    page: int = 0,
    items_per_page: int = 1000,
    current_user_id: str = Depends(get_current_user_id_from_jwt)
):
    """Return empty usage logs since billing is disabled."""
    try:
        logger.info("Billing disabled - returning empty usage logs")
        
        # Validate pagination parameters
        if page < 0:
            raise HTTPException(status_code=400, detail="Page must be non-negative")
        if items_per_page < 1 or items_per_page > 1000:
            raise HTTPException(status_code=400, detail="Items per page must be between 1 and 1000")
        
        return {
            "logs": [], 
            "has_more": False,
            "message": "Billing disabled - no usage tracking"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting usage logs: {str(e)}")