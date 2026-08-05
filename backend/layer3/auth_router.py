from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
import datetime
import os
from layer3.db import get_db, User
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/brain/auth", tags=["Authentication"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
if not GOOGLE_CLIENT_ID:
    raise ValueError("GOOGLE_CLIENT_ID must be set in the environment")
    
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_for_prism_development")
JWT_ALGORITHM = "HS256"

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)), db: Session = Depends(get_db)):
    if not credentials:
        return None
    return get_current_user(credentials, db)

class GoogleLoginRequest(BaseModel):
    token: str

@router.post("/google")
def google_login(request: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(request.token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo.get("email")
        google_id = idinfo.get("sub")
        name = idinfo.get("name")
        
        if not email or not google_id:
            raise HTTPException(status_code=400, detail="Invalid Google token missing email or sub")
            
        # Check if user exists
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            # Create new user
            user = User(email=email, google_id=google_id, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)
            
        # Generate JWT
        token_payload = {
            "sub": user.id,
            "email": user.email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        access_token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name
            }
        }
        
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
