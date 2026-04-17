from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user, hash_password, require_admin, verify_password
from app.db import get_db
from app.schemas.users import (
    CreateUserRequest,
    UpdateMeRequest,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(tags=["users"])


def row_to_user_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.put("/api/auth/me", response_model=UserResponse)
def update_me(
    payload: UpdateMeRequest,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user = conn.execute(
        """
        SELECT id, name, email, password_hash, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (current_user["user_id"],),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_name = payload.name if payload.name is not None else user["name"]
    new_password_hash = user["password_hash"]

    if payload.new_password:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe a senha atual para alterar a senha",
            )

        if not verify_password(payload.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha atual incorreta",
            )

        new_password_hash = hash_password(payload.new_password)

    conn.execute(
        """
        UPDATE users
        SET name = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_name, new_password_hash, current_user["user_id"]),
    )
    conn.commit()

    updated = conn.execute(
        """
        SELECT id, name, email, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (current_user["user_id"],),
    ).fetchone()

    return row_to_user_dict(updated)


@router.get("/api/users", response_model=list[UserResponse])
def list_users(
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    users = conn.execute(
        """
        SELECT id, name, email, role, is_active, created_at, updated_at
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    return [row_to_user_dict(user) for user in users]


@router.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (payload.email,),
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado",
        )

    password_hash = hash_password(payload.password)

    cursor = conn.execute(
        """
        INSERT INTO users (name, email, password_hash, role, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (payload.name, payload.email, password_hash, payload.role),
    )
    conn.commit()

    user = conn.execute(
        """
        SELECT id, name, email, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()

    return row_to_user_dict(user)


@router.put("/api/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    user = conn.execute(
        """
        SELECT id, name, email, password_hash, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_name = payload.name if payload.name is not None else user["name"]
    new_email = payload.email if payload.email is not None else user["email"]
    new_role = payload.role if payload.role is not None else user["role"]
    new_is_active = int(payload.is_active) if payload.is_active is not None else user["is_active"]
    new_password_hash = user["password_hash"]

    if payload.email and payload.email != user["email"]:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? AND id <> ?",
            (payload.email, user_id),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado",
            )

    if payload.password:
        new_password_hash = hash_password(payload.password)

    if current_user["user_id"] == user_id and payload.role is not None and payload.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode remover seu próprio acesso de administrador",
        )

    conn.execute(
        """
        UPDATE users
        SET name = ?, email = ?, password_hash = ?, role = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_name, new_email, new_password_hash, new_role, new_is_active, user_id),
    )
    conn.commit()

    updated = conn.execute(
        """
        SELECT id, name, email, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    return row_to_user_dict(updated)


@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    if current_user["user_id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir sua própria conta",
        )

    user = conn.execute(
        "SELECT id, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    admin_count = conn.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role = 'admin' AND is_active = 1"
    ).fetchone()["total"]

    if user["role"] == "admin" and admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir o último administrador ativo",
        )

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

    return {"message": "Usuário excluído com sucesso"}