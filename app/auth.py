# app/auth.py
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.config import settings
from app.database import get_db
from app import models

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class AuthService:
    """
    Authentication service class containing all auth-related operations
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create JWT access token
        
        Args:
            data: Data to encode in token (typically {"sub": user_email})
            expires_delta: Custom expiration time (optional)
            
        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, credentials_exception: HTTPException) -> str:
        """
        Verify JWT token and extract email
        
        Args:
            token: JWT token string
            credentials_exception: Exception to raise if verification fails
            
        Returns:
            User email from token
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            return email
        except JWTError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise credentials_exception
    
    @staticmethod
    def authenticate_user(email: str, password: str, db: Session) -> Optional[models.User]:
        """
        Authenticate user with email and password
        
        Args:
            email: User's email
            password: Plain text password
            db: Database session
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return None
        if not AuthService.verify_password(password, user.password):
            return None
        if not user.is_active:
            return None
        return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """
    Dependency to get current authenticated user from JWT token
    
    Args:
        token: JWT token from Authorization header
        db: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        email = AuthService.verify_token(token, credentials_exception)
        user = db.query(models.User).filter(models.User.email == email).first()
        
        if user is None:
            logger.warning(f"User not found for email: {email}")
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        raise credentials_exception


def get_current_active_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Dependency to get current active user (additional check for active status)
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_current_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Dependency to get current admin user
    
    Args:
        current_user: Current user from get_current_user dependency
        
    Returns:
        Current admin user
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Optional dependency to get current user (doesn't raise exception if no token)
    
    Useful for endpoints that work differently for authenticated vs anonymous users
    
    Args:
        token: JWT token from Authorization header (optional)
        db: Database session
        
    Returns:
        User object if authenticated, None if anonymous
    """
    if token is None:
        return None
    
    try:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        email = AuthService.verify_token(token, credentials_exception)
        user = db.query(models.User).filter(models.User.email == email).first()
        
        if user and user.is_active:
            return user
        return None
        
    except HTTPException:
        return None
    except Exception as e:
        logger.error(f"Error in get_optional_current_user: {str(e)}")
        return None


# Create auth service instance for easy access
auth_service = AuthService()


# Utility functions for password validation
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    
    Args:
        password: Plain text password
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"


def create_user_with_validation(user_data: dict, db: Session) -> models.User:
    """
    Create user with password validation
    
    Args:
        user_data: Dictionary containing user data
        db: Database session
        
    Returns:
        Created user object
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate password strength
    is_valid, message = validate_password_strength(user_data.get("password", ""))
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Check if user already exists
    existing_user = db.query(models.User).filter(
        models.User.email == user_data["email"]
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    
    try:
        # Create user
        hashed_password = auth_service.hash_password(user_data["password"])
        new_user = models.User(
            name=user_data["name"],
            email=user_data["email"],
            password=hashed_password
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"New user created: {new_user.email}")
        return new_user

    except Exception as e:
        import traceback
        logger.error(f"Error creating user: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )