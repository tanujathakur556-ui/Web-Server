# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ===============================
# BASE SCHEMAS
# ===============================

class BaseResponse(BaseModel):
    """Base response schema"""
    success: bool = True
    message: str = "Operation successful"
    
    class Config:
        from_attributes = True


class PaginationResponse(BaseModel):
    """Pagination metadata"""
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


# ===============================
# USER SCHEMAS
# ===============================

class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty or just whitespace')
        return v.strip()


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100, description="User's password")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserWithStats(UserResponse):
    """User response with additional statistics"""
    blog_count: int = 0
    comment_count: int = 0
    like_count: int = 0


# ===============================
# AUTHENTICATION SCHEMAS
# ===============================

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


# ===============================
# CATEGORY SCHEMAS
# ===============================

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CategoryWithStats(CategoryResponse):
    """Category response with blog count"""
    blog_count: int = 0


# ===============================
# TAG SCHEMAS
# ===============================

class TagBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="Tag name")
    color: str = Field(
        default="#007bff",
        pattern="^#[0-9a-fA-F]{6}$",
        description="Hex color code"
    )


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===============================
# BLOG SCHEMAS
# ===============================

class BlogBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=200, description="Blog title")
    body: str = Field(..., min_length=50, description="Blog content")
    excerpt: Optional[str] = Field(None, max_length=300, description="Short description")
    category_id: Optional[int] = Field(None, description="Category ID")
    is_published: bool = Field(False, description="Publication status")
    is_featured: bool = Field(False, description="Featured status")


class BlogCreate(BlogBase):
    tag_names: Optional[List[str]] = Field([], description="List of tag names")


class BlogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    body: Optional[str] = Field(None, min_length=50)
    excerpt: Optional[str] = Field(None, max_length=300)
    category_id: Optional[int] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None
    tag_names: Optional[List[str]] = None


class BlogResponse(BlogBase):
    id: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    
    # Related objects
    creator: UserResponse
    category: Optional[CategoryResponse] = None
    tags: List[TagResponse] = []
    
    class Config:
        from_attributes = True


class BlogWithStats(BlogResponse):
    """Blog response with additional statistics"""
    comment_count: int = 0
    like_count: int = 0
    is_liked: bool = False  # Whether current user liked this blog


class BlogListResponse(BaseModel):
    """Response for blog list with pagination"""
    blogs: List[BlogWithStats]
    pagination: PaginationResponse


# ===============================
# COMMENT SCHEMAS
# ===============================

class CommentBase(BaseModel):
    content: str = Field(..., min_length=3, max_length=1000, description="Comment content")


class CommentCreate(CommentBase):
    parent_id: Optional[int] = Field(None, description="Parent comment ID for replies")


class CommentUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=3, max_length=1000)
    is_approved: Optional[bool] = None


class CommentResponse(CommentBase):
    id: int
    blog_id: int
    parent_id: Optional[int]
    is_approved: bool
    created_at: datetime
    updated_at: datetime
    
    # Related objects
    author: UserResponse
    replies: List["CommentResponse"] = []  # For nested comments
    
    class Config:
        from_attributes = True


# Fix forward reference for nested comments
CommentResponse.model_rebuild()


# ===============================
# LIKE SCHEMAS
# ===============================

class LikeResponse(BaseModel):
    id: int
    blog_id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===============================
# FILTER AND SEARCH SCHEMAS
# ===============================

class BlogFilter(BaseModel):
    """Blog filtering parameters"""
    category_id: Optional[int] = None
    tag_names: Optional[List[str]] = []
    is_published: Optional[bool] = True
    is_featured: Optional[bool] = None
    author_id: Optional[int] = None
    search: Optional[str] = Field(None, min_length=3, description="Search in title and content")


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(10, ge=1, le=100, description="Items per page")


# ===============================
# BULK OPERATION SCHEMAS
# ===============================

class BulkDeleteRequest(BaseModel):
    """Bulk delete request"""
    ids: List[int] = Field(..., min_items=1, description="List of IDs to delete")


class BulkUpdateRequest(BaseModel):
    """Bulk update request"""
    ids: List[int] = Field(..., min_items=1, description="List of IDs to update")
    data: dict = Field(..., description="Update data")



# API RESPONSE WRAPPERS


class SingleResponse(BaseResponse):
    """Single item response wrapper"""
    data: Optional[dict] = None


class ListResponse(BaseResponse):
    """List response wrapper"""
    data: List = []
    pagination: Optional[PaginationResponse] = None


class CountResponse(BaseResponse):
    """Count response"""
    count: int = 0



# ERROR SCHEMAS


class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    message: str
    details: Optional[dict] = None
    error_code: Optional[str] = None