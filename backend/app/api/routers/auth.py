from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse
from app.services.auth_service import authenticate_user, create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DBSession):
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, payload.email, payload.password, payload.full_name)
    return Token(access_token=authenticate_user(db, payload.email, payload.password))


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: DBSession):
    auth = authenticate_user(db, payload.email, payload.password)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=auth)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser):
    return current_user
