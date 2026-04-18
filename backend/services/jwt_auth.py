# ==============================================================================
# File: backend/services/jwt_auth.py
# ==============================================================================
# PURPOSE: JWT-based authentication with Role-Based Access Control (RBAC)
#
# ARCHITECTURE:
#   Login  →  create_access_token(user)  →  returns {access_token, refresh_token}
#   Request →  decode_access_token(token) →  returns payload with user_id & role
#   RBAC   →  require_role("admin")      →  FastAPI dependency that checks role
#
# WHY JWT over Session Tokens?
#   1. STATELESS: No DB lookup required to validate tokens (just verify signature)
#   2. SCALABLE: Works across multiple server instances without shared session store
#   3. SELF-CONTAINED: Token carries user_id, role, and expiry — all encoded
#
# BACKWARD COMPATIBILITY:
#   The old session-token flow still works via get_current_user() in main.py.
#   JWT is the NEW preferred flow. Both coexist until migration is complete.
# ==============================================================================

import os
import jwt
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger("dataspark.jwt")

# Config — loaded from env or generated at startup
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(64))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "1440"))  # 24h
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))


def create_access_token(user_id: int, username: str, role: str = "user",
                        extra_claims: Optional[Dict] = None) -> str:
    """
    Creates a signed JWT access token.

    Payload:
        sub: user_id (string)
        username: username
        role: "admin" | "user"
        iat: issued-at timestamp
        exp: expiration timestamp
    """
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Creates a long-lived refresh token (7 days by default)."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT token.
    Returns the payload dict if valid, or None if expired/invalid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """Extracts user_id from a valid token. Returns None if invalid."""
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        try:
            return int(payload["sub"])
        except (ValueError, KeyError):
            return None
    return None


def get_role_from_token(token: str) -> Optional[str]:
    """Extracts role from a valid token. Returns None if invalid."""
    payload = decode_token(token)
    if payload:
        return payload.get("role", "user")
    return None


# ==============================================================================
# RBAC Dependency Factory
# ==============================================================================
# Usage in endpoints:
#   @app.get("/admin/users", dependencies=[Depends(require_role("admin"))])
#   async def list_all_users(...):
#       ...
# ==============================================================================

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_security = HTTPBearer()


def require_role(*allowed_roles: str):
    """
    FastAPI dependency that enforces RBAC.
    Returns a dependency function that checks the user's JWT role.

    Usage:
        @app.get("/admin/dashboard", dependencies=[Depends(require_role("admin"))])
    """
    async def _check_role(credentials: HTTPAuthorizationCredentials = Depends(_security)):
        token = credentials.credentials
        payload = decode_token(token)

        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_role = payload.get("role", "user")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {user_role}",
            )

        return payload  # Returns the full JWT payload for use in the endpoint

    return _check_role
