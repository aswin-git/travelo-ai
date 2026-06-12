"""
JWT token verification for Supabase Auth.
Verifies tokens via the Supabase Auth API to support asymmetric keys (ES256, RS256).
"""
import httpx
import jwt
from fastapi import HTTPException, status
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


def decode_token(token: str) -> dict:
    """
    Verify a Supabase JWT token by calling the Supabase Auth API.
    This handles both symmetric (HS256) and asymmetric (ES256/RS256) tokens automatically.
    Returns the decoded payload containing 'sub' (supabase_uid), 'email', etc.
    Raises HTTPException(401) on invalid/expired tokens.
    """
    try:
        # First, quickly decode without verification just to extract payload structure if needed
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError as e:
        logger.warning(f"Malformed JWT token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
        )

    # Call Supabase Auth API to verify the token
    auth_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}"
    }

    try:
        # We use a synchronous request here because this runs inside a FastAPI Depends
        # which runs in a threadpool anyway.
        with httpx.Client() as client:
            response = client.get(auth_url, headers=headers, timeout=5.0)
            
        if response.status_code == 200:
            user_data = response.json()
            # Construct a payload compatible with our existing logic
            return {
                "sub": user_data.get("id"),
                "email": user_data.get("email"),
                "user_metadata": user_data.get("user_metadata", {})
            }
        else:
            logger.warning(f"Token validation failed at Supabase API. Status: {response.status_code}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            )
    except httpx.RequestError as e:
        logger.error(f"Network error communicating with Supabase Auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable",
        )
