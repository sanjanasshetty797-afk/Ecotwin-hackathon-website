import hashlib, hmac, os
from datetime import timedelta
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db, utcnow
from .models import Bin, User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split("$")
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(dk.hex(), dk_hex)


def hash_device_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_token(username: str, role: str) -> str:
    exp = utcnow() + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": username, "role": role, "exp": exp}, settings.secret_key, algorithm="HS256")


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return db.scalar(select(User).where(User.username == data.get("sub")))


def current_user(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    user = _user_from_token(token, db)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing token",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def device_bin(x_device_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> Bin:
    """Authenticates an IoT device: each bin has its own secret key."""
    if not x_device_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Device-Key")
    b = db.scalar(select(Bin).where(Bin.device_key_hash == hash_device_key(x_device_key)))
    if not b:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device key")
    return b


def user_or_device(
    token: str | None = Depends(oauth2),
    x_device_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> str:
    if x_device_key:
        b = db.scalar(select(Bin).where(Bin.device_key_hash == hash_device_key(x_device_key)))
        if b:
            return f"device:{b.code}"
    u = _user_from_token(token, db)
    if u:
        return f"user:{u.username}"
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
