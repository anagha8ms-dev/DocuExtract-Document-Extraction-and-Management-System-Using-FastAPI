from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import db_models
from database import SessionLocal


password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

SECRET_KEY = "f1794c55f55b7d4e0ef9e22d967dbdc94035323ff533535dbb299688770cb6e4"
ALGORITHM = "HS256"
TOKEN_EXPIRATION_TIME =30

def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password,hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRATION_TIME
    )

    
    to_encode.update({"exp": expire})

    token = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token

# Extract the bearer tokens from the request

oauth2_scheme =  OAuth2PasswordBearer(tokenUrl = "/users/login")

def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
    
):

    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )


        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    user = db.query(db_models.User).filter(
        db_models.User.username == username
    ).first()

    if user is None:
        raise credentials_exception

    return user
