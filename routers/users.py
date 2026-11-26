from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


import db_models
import schemas

from database import get_db

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(
    prefix="/users",
    tags=["User Authentication"]
)

@router.post("/register")
def register_user(
    user: schemas.Usercreate,
    db: Session = Depends(get_db)
):


    existing_user = db.query(db_models.User).filter(
        db_models.User.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )


    existing_email = db.query(db_models.User).filter(
        db_models.User.email == user.email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    hashed_password = hash_password(user.password)

    new_user = db_models.User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)


    return {
        "message": "User registered successfully",
        "username": new_user.username
    }



# USER LOGIN
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = db.query(db_models.User).filter(
        db_models.User.username == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        form_data.password,
        user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = create_access_token(
        {"sub": user.username}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

# GET LOGGED-IN USER
@router.get("/me", response_model=schemas.UserResponse)
def get_my_profile(
    current_user: db_models.User = Depends(get_current_user)
):

    return current_user
