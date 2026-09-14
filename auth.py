import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Header
import os
from dotenv import load_dotenv
load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

def create_token(mobile: str):
    """Create JWT token for the authenticated user."""
    payload = {
        "mobile": mobile,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user(authorization: str = Header(...)) -> str:
    """
    Validate JWT from Authorization header
    and return the user's mobile number.
    """
    try:
        # Expected:
        # Authorization: Bearer <token>
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = parts[1]
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

        mobile = payload.get("mobile")
        if not mobile:
            raise HTTPException(status_code=401, detail="Invalid token")
        return mobile

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")