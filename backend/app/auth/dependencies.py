"""
FastAPI dependencies for authentication.
Provides get_current_user() and get_optional_user() for route injection.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.user_model import User
from .jwt_handler import decode_token
from ..utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Required auth dependency.
    Extracts JWT from Authorization header, verifies it,
    and returns the User (auto-creates on first login).
    """
    payload = decode_token(credentials.credentials)
    supabase_uid = payload.get("sub")
    email = payload.get("email")

    if not supabase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Look up existing user or auto-create on first login
    user = db.query(User).filter(User.supabase_uid == supabase_uid).first()
    if not user:
        logger.info(f"First login — creating user record for {email}")
        user = User(
            supabase_uid=supabase_uid,
            email=email,
            display_name=email.split("@")[0] if email else "Traveler",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional auth dependency — returns None for unauthenticated requests.
    Used for endpoints that work for both logged-in and anonymous users.
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        supabase_uid = payload.get("sub")
        email = payload.get("email")

        if not supabase_uid:
            return None

        user = db.query(User).filter(User.supabase_uid == supabase_uid).first()
        if not user:
            user = User(
                supabase_uid=supabase_uid,
                email=email,
                display_name=email.split("@")[0] if email else "Traveler",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
    except HTTPException:
        return None
