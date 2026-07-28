from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "troque-essa-chave-por-uma-bem-forte"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# auto_error=False: permite cair pro fallback via query string quando não há
# header Authorization (caso de <img>/<a>/<iframe>, que o navegador nunca
# manda com header customizado)
bearer_scheme = HTTPBearer(auto_error=False)


def get_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token: Optional[str] = Query(default=None),
) -> str:
    """
    Extrai o JWT do header Authorization (uso normal via axios) ou do query
    param ?token= (uso em <img src>, <a href>, <iframe>, <audio src> — esses
    elementos HTML não têm como mandar header customizado).
    """
    if credentials:
        return credentials.credentials
    if token:
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )


def get_current_user(token: str = Depends(get_token)) -> dict:
    payload = decode_token(token)

    email = payload.get("sub")
    role = payload.get("role")
    user_id = payload.get("user_id")

    if not email or not role or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    return payload


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem executar esta ação",
        )
    return user


def require_editor(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas editores ou administradores podem executar esta ação",
        )
    return user