# ==============================================================================
# File: backend/services/oauth_sso.py
# ==============================================================================
# PURPOSE: OAuth2 / SSO Integration Stubs (Google & Microsoft Workspace)
#
# HOW IT WORKS (when implemented):
#   1. Frontend calls GET /auth/oauth/{provider}/login → gets redirect URL
#   2. User authenticates with Google/Microsoft
#   3. Provider redirects back to GET /auth/oauth/{provider}/callback with auth code
#   4. Backend exchanges code for user info → creates/links local user → issues JWT
#
# CURRENT STATE: STUBBED — Returns configuration endpoints and mock flows.
#   To activate: Set the OAUTH_GOOGLE_CLIENT_ID etc. env vars and install oauthlib.
# ==============================================================================

import os
import logging
from typing import Optional, Dict
import httpx

logger = logging.getLogger("dataspark.oauth")

# ==============================================================================
# OAuth2 Provider Configuration (from environment variables)
# ==============================================================================

OAUTH_CONFIG = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"],
        "redirect_uri": os.getenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/oauth/google/callback"),
    },
    "microsoft": {
        "client_id": os.getenv("OAUTH_MICROSOFT_CLIENT_ID", ""),
        "client_secret": os.getenv("OAUTH_MICROSOFT_CLIENT_SECRET", ""),
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["openid", "email", "profile", "User.Read"],
        "redirect_uri": os.getenv("OAUTH_MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/oauth/microsoft/callback"),
    },
}


def is_provider_configured(provider: str) -> bool:
    """Check if OAuth config is set for a provider."""
    config = OAUTH_CONFIG.get(provider, {})
    return bool(config.get("client_id") and config.get("client_secret"))


def get_available_providers() -> list:
    """Returns list of configured OAuth providers."""
    return [p for p in OAUTH_CONFIG if is_provider_configured(p)]


def get_authorization_url(provider: str, state: Optional[str] = None) -> Optional[str]:
    """
    Generates the OAuth2 authorization URL to redirect the user to.
    Returns None if provider is not configured.
    """
    if not is_provider_configured(provider):
        logger.warning(f"OAuth provider '{provider}' is not configured. Set env vars.")
        return None

    config = OAUTH_CONFIG[provider]
    scopes = "+".join(config["scopes"])

    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{config['authorize_url']}?{query}"
    return url


async def exchange_code_for_user_info(provider: str, code: str) -> Optional[Dict]:
    """
    Exchanges the OAuth authorization code for an access token,
    then fetches user info from the provider.
    """
    if not is_provider_configured(provider):
        logger.error(f"Provider {provider} not configured.")
        return None

    config = OAUTH_CONFIG[provider]

    async with httpx.AsyncClient() as client:
        # 1. Exchange code for token
        token_data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"]
        }

        try:
            token_res = await client.post(config["token_url"], data=token_data)
            token_res.raise_for_status()
            access_token = token_res.json().get("access_token")
            
            if not access_token:
                logger.error("OAuth token response did not contain access_token")
                return None
                
            # 2. Get User Info
            headers = {"Authorization": f"Bearer {access_token}"}
            user_res = await client.get(config["userinfo_url"], headers=headers)
            user_res.raise_for_status()
            user_info = user_res.json()
            
            # Format to unified response
            return {
                "provider": provider,
                "provider_id": str(user_info.get("id") or user_info.get("sub", "")),
                "email": user_info.get("email", ""),
                "name": user_info.get("name", ""),
                "verified": bool(user_info.get("email_verified", False))
            }
        except httpx.HTTPError as e:
            logger.error(f"OAuth HTTP Error: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"OAuth Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected OAuth Error: {e}")
            return None


def get_sso_status() -> Dict:
    """Returns SSO configuration status for the /health endpoint."""
    providers = {}
    for name in OAUTH_CONFIG:
        providers[name] = {
            "configured": is_provider_configured(name),
            "authorize_url": OAUTH_CONFIG[name]["authorize_url"],
        }
    return {
        "enabled": len(get_available_providers()) > 0,
        "providers": providers,
    }
