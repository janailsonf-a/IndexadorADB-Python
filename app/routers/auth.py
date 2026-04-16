import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

DB_PATH = Path("/app/data/file_index.db")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        user = conn.execute(
            """
            SELECT id, name, email, password_hash, role, is_active
            FROM users
            WHERE email = ?
            """,
            (payload.email,),
        ).fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    if int(user["is_active"]) != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    token = create_access_token(
        {
            "sub": user["email"],
            "role": user["role"],
            "user_id": user["id"],
            "name": user["name"],
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user.get("sub"),
        "role": current_user.get("role"),
        "id": current_user.get("user_id"),
        "name": current_user.get("name"),
    }