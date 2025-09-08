# app/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserResponse, UserLogin, Token, 
    BaseResponse, ErrorResponse
)
from app.auth import AuthService, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user
    
    - **name**: User's full name (2-100 characters)
    - **email**: Valid email address
    - **password**: Strong password (min 6 chars, must contain uppercase, lowercase, digit)
    """
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = AuthService.hash_password(user_data.password)
        new_user = User(
            name=user_data.name,
            email=user_data.email,
            password=hashed_password
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"New user registered: {new_user.email}")
        
        return BaseResponse(
            success=True,
            message=f"User '{user_data.name}' registered successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login with email and password to get access token
    
    - **username**: User's email address (OAuth2 standard uses 'username' field)
    - **password**: User's password
    
    Returns JWT access token for authenticated requests
    """
    try:
        # Find user by email (OAuth2 uses 'username' field for email)
        user = db.query(User).filter(User.email == form_data.username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not AuthService.verify_password(form_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token = AuthService.create_access_token(data={"sub": user.email})
        
        logger.info(f"User logged in: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60,  # 30 minutes in seconds
            user=UserResponse.from_orm(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/login-email", response_model=Token)
async def login_with_email(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Alternative login endpoint using JSON body instead of form data
    
    - **email**: User's email address
    - **password**: User's password
    """
    try:
        # Find user by email
        user = db.query(User).filter(User.email == login_data.email).first()
        
        if not user or not AuthService.verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token = AuthService.create_access_token(data={"sub": user.email})
        
        logger.info(f"User logged in via email: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60,
            user=UserResponse.from_orm(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information
    
    Requires: Bearer token in Authorization header
    """
    return UserResponse.from_orm(current_user)


@router.post("/logout", response_model=BaseResponse)
async def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logout current user
    
    Note: With JWT tokens, logout is mainly handled on the client side
    by removing the token. This endpoint is here for consistency and
    can be extended for token blacklisting if needed.
    """
    logger.info(f"User logged out: {current_user.email}")
    
    return BaseResponse(
        success=True,
        message="Successfully logged out"
    )


@router.post("/change-password", response_model=BaseResponse)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user's password
    
    - **old_password**: Current password for verification
    - **new_password**: New password (must meet strength requirements)
    
    Requires: Bearer token in Authorization header
    """
    try:
        # Verify old password
        if not AuthService.verify_password(old_password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password (basic validation)
        if len(new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 6 characters long"
            )
        
        if new_password == old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Update password
        current_user.password = AuthService.hash_password(new_password)
        db.commit()
        
        logger.info(f"Password changed for user: {current_user.email}")
        
        return BaseResponse(
            success=True,
            message="Password changed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post("/refresh-token", response_model=Token)
async def refresh_access_token(current_user: User = Depends(get_current_user)):
    """
    Refresh access token
    
    Use this endpoint to get a new access token before the current one expires
    
    Requires: Valid Bearer token in Authorization header
    """
    try:
        # Create new access token
        access_token = AuthService.create_access_token(data={"sub": current_user.email})
        
        logger.info(f"Token refreshed for user: {current_user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60,
            user=UserResponse.from_orm(current_user)
        )
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )


# Admin only endpoints
@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (Admin only)
    
    Requires: Admin user with Bearer token
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    users = db.query(User).all()
    return [UserResponse.from_orm(user) for user in users]


@router.patch("/users/{user_id}/toggle-status", response_model=BaseResponse)
async def toggle_user_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle user active status (Admin only)
    
    - **user_id**: ID of user to toggle status
    
    Requires: Admin user with Bearer token
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Don't allow admin to deactivate themselves
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify your own status"
            )
        
        user.is_active = not user.is_active
        db.commit()
        
        action = "activated" if user.is_active else "deactivated"
        logger.info(f"User {user.email} {action} by admin {current_user.email}")
        
        return BaseResponse(
            success=True,
            message=f"User {user.name} has been {action}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User status toggle error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )