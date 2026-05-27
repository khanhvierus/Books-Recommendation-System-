import os
import bcrypt  # SỬ DỤNG TRỰC TIẾP BCRYPT (Thay cho passlib)
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import models

# Lấy khóa bí mật từ .env, nếu không có thì dùng khóa dự phòng
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "SUPER_SECRET_KEY_DONT_SHARE_THIS_123456")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 # Token có hiệu lực trong 24 giờ (1 ngày)

# Khai báo chuẩn OAuth2 để FastAPI biết đường dẫn đăng nhập
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_password_hash(password: str) -> str:
    """Băm mật khẩu thô thành chuỗi bảo mật bằng bcrypt"""
    pwd_bytes = password.encode('utf-8')
    # Cắt ngắn nếu vượt quá giới hạn 72 bytes của bcrypt
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    # Tạo muối (salt) ngẫu nhiên và băm
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu nhập vào có khớp với mã băm trong DB hay không"""
    pwd_bytes = plain_password.encode('utf-8')
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))
    except ValueError:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Tạo JWT Token chứa thông tin user"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(models.get_db)):
    """Chặn cửa: Đọc thẻ JWT, nếu hợp lệ thì cho qua và trả về thông tin User"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Mã xác thực không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Giải mã thẻ Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Truy vấn DB để lấy thông tin user thật
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user