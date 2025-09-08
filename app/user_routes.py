# app/user_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy import desc, func
from typing import List, Optional
import logging

from app.database import get_db
from app.models import User, Blog, Comment, Like
from app.schemas import (
    UserResponse, UserWithStats, UserUpdate, BaseResponse,
    BlogResponse, PaginationParams, PaginationResponse
)
from app.auth import get_current_user, AuthService

logger = logging.getLogger(__name__)
router = APIRouter()



# USER PROFILE ENDPOINTS


@router.get("/profile", response_model=UserWithStats)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile with statistics
    
    Returns user information along with:
    - Total number of blogs created
    - Total number of comments made
    - Total number of likes received on blogs
    """
    try:
        # Get user statistics
        blog_count = db.query(Blog).filter(Blog.user_id == current_user.id).count()
        comment_count = db.query(Comment).filter(Comment.user_id == current_user.id).count()
        
        # Get total likes received on user's blogs
        like_count = db.query(Like).join(Blog).filter(Blog.user_id == current_user.id).count()
        
        user_data = UserResponse.from_orm(current_user)
        return UserWithStats(
            **user_data.dict(),
            blog_count=blog_count,
            comment_count=comment_count,
            like_count=like_count
        )
        
    except Exception as e:
        logger.error(f"Profile retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )


@router.put("/profile", response_model=UserResponse)
async def update_my_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile
    
    - **name**: User's full name (optional)
    - **email**: User's email address (optional)
    
    Note: Only the user can update their own profile
    """
    try:
        update_data = user_data.dict(exclude_unset=True)
        
        # Check if email is being updated and if it's already taken
        if "email" in update_data and update_data["email"] != current_user.email:
            existing_user = db.query(User).filter(User.email == update_data["email"]).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Update user fields
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Profile updated: {current_user.email}")
        
        return UserResponse.from_orm(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )





@router.get("/{user_id}", response_model=UserWithStats)
async def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get public user profile by ID
    
    Returns basic user information and public statistics
    """
    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user statistics (only for published content)
        blog_count = db.query(Blog).filter(
            Blog.user_id == user.id,
            Blog.is_published == True
        ).count()
        
        comment_count = db.query(Comment).join(Blog).filter(
            Comment.user_id == user.id,
            Blog.is_published == True,
            Comment.is_approved == True
        ).count()
        
        like_count = db.query(Like).join(Blog).filter(
            Blog.user_id == user.id,
            Blog.is_published == True
        ).count()
        
        user_data = UserResponse.from_orm(user)
        return UserWithStats(
            **user_data.dict(),
            blog_count=blog_count,
            comment_count=comment_count,
            like_count=like_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )




# USER'S OWN CONTENT MANAGEMENT

@router.get("/my/blogs", response_model=List[BlogResponse])
async def get_my_blogs(
    pagination: PaginationParams = Depends(),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's blogs
    
    - **is_published**: Filter by publication status (optional)
    - **page**: Page number
    - **per_page**: Items per page
    
    Returns all blogs created by the current user (published and unpublished)
    """
    try:
        query = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        ).filter(Blog.user_id == current_user.id)
        
        # Apply publication filter if specified
        if is_published is not None:
            query = query.filter(Blog.is_published == is_published)
        
        # Order by update date (most recently updated first)
        query = query.order_by(desc(Blog.updated_at))
        
        # Apply pagination
        offset = (pagination.page - 1) * pagination.per_page
        blogs = query.offset(offset).limit(pagination.per_page).all()
        
        return [BlogResponse.from_orm(blog) for blog in blogs]
        
    except Exception as e:
        logger.error(f"My blogs retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve your blogs"
        )





@router.get("/{user_id}/blogs", response_model=List[BlogResponse])
async def get_user_blogs(
    user_id: int,
    pagination: PaginationParams = Depends(),
    published_only: bool = Query(True, description="Show only published blogs"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get blogs by a specific user
    
    - **user_id**: User ID
    - **published_only**: Show only published blogs (default: true)
    - **page**: Page number
    - **per_page**: Items per page
    
    Note: Users can see their own unpublished blogs, others can only see published blogs
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Base query
        query = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        ).filter(Blog.user_id == user_id)
        
        # Apply publication filter
        if published_only or (current_user and current_user.id != user_id):
            query = query.filter(Blog.is_published == True)
        
        # Order by creation date (newest first)
        query = query.order_by(desc(Blog.created_at))
        
        # Apply pagination
        offset = (pagination.page - 1) * pagination.per_page
        blogs = query.offset(offset).limit(pagination.per_page).all()
        
        return [BlogResponse.from_orm(blog) for blog in blogs]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User blogs retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user blogs"
        )





@router.get("/my/stats", response_model=dict)
async def get_my_detailed_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed statistics for current user
    
    Returns comprehensive statistics including:
    - Blog statistics (total, published, drafts, featured)
    - Engagement statistics (total views, likes, comments)
    - Recent activity summary
    """
    try:
        # Blog statistics
        total_blogs = db.query(Blog).filter(Blog.user_id == current_user.id).count()
        published_blogs = db.query(Blog).filter(
            Blog.user_id == current_user.id,
            Blog.is_published == True
        ).count()
        draft_blogs = total_blogs - published_blogs
        featured_blogs = db.query(Blog).filter(
            Blog.user_id == current_user.id,
            Blog.is_featured == True
        ).count()
        
        # Engagement statistics
        total_views = db.query(func.sum(Blog.view_count)).filter(
            Blog.user_id == current_user.id
        ).scalar() or 0
        
        total_likes = db.query(Like).join(Blog).filter(
            Blog.user_id == current_user.id
        ).count()
        
        total_comments = db.query(Comment).join(Blog).filter(
            Blog.user_id == current_user.id,
            Comment.is_approved == True
        ).count()
        
        # Comments made by user
        comments_made = db.query(Comment).filter(
            Comment.user_id == current_user.id
        ).count()
        
        # Most popular blog
        most_popular_blog = db.query(Blog).filter(
            Blog.user_id == current_user.id,
            Blog.is_published == True
        ).order_by(desc(Blog.view_count)).first()
        
        return {
            "blog_stats": {
                "total_blogs": total_blogs,
                "published_blogs": published_blogs,
                "draft_blogs": draft_blogs,
                "featured_blogs": featured_blogs
            },
            "engagement_stats": {
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments_received": total_comments,
                "total_comments_made": comments_made
            },
            "most_popular_blog": {
                "id": most_popular_blog.id if most_popular_blog else None,
                "title": most_popular_blog.title if most_popular_blog else None,
                "view_count": most_popular_blog.view_count if most_popular_blog else 0
            }
        }
        
    except Exception as e:
        logger.error(f"User stats retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.delete("/my/blogs/{blog_id}", response_model=BaseResponse)
async def delete_my_blog(
    blog_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete current user's blog
    
    - **blog_id**: Blog ID to delete
    
    Only the blog author can delete their own blog
    """
    try:
        blog = db.query(Blog).filter(
            Blog.id == blog_id,
            Blog.user_id == current_user.id
        ).first()
        
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found or you don't have permission to delete it"
            )
        
        blog_title = blog.title
        db.delete(blog)
        db.commit()
        
        logger.info(f"Blog deleted by owner: {blog_title} by {current_user.email}")
        
        return BaseResponse(
            success=True,
            message=f"Your blog '{blog_title}' has been deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Blog deletion error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete blog"
        )



# USER ACTIVITY ENDPOINT

@router.get("/my/liked-blogs", response_model=List[BlogResponse])
async def get_my_liked_blogs(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get blogs liked by current user
    
    Returns list of published blogs that the current user has liked
    """
    try:
        # Get blogs liked by the user
        liked_blogs_query = db.query(Blog).filter(
            Blog.is_published == True,
            Blog.likes.any(Like.user_id == current_user.id)
        ).order_by(desc(Blog.updated_at)).distinct()
       
       
        # Apply pagination
        offset = (pagination.page - 1) * pagination.per_page
        liked_blogs = liked_blogs_query.offset(offset).limit(pagination.per_page).all()
        
        return [BlogResponse.from_orm(blog) for blog in liked_blogs]
        
    except Exception as e:
        logger.error(f"Liked blogs retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve liked blogs"
        )


@router.get("/my/comments", response_model=List[dict])
async def get_my_comments(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comments made by current user
    
    Returns list of comments made by the current user on published blogs
    """
    try:
        comments_query = db.query(Comment).options(
            joinedload(Comment.blog).joinedload(Blog.creator)
        ).join(Blog).filter(
            Comment.user_id == current_user.id,
            Blog.is_published == True,
            Comment.is_approved == True
        ).order_by(desc(Comment.created_at))
        
        # Apply pagination
        offset = (pagination.page - 1) * pagination.per_page
        comments = comments_query.offset(offset).limit(pagination.per_page).all()
        
        # Format response with blog information
        comment_list = []
        for comment in comments:
            comment_list.append({
                "id": comment.id,
                "content": comment.content,
                "created_at": comment.created_at,
                "blog": {
                    "id": comment.blog.id,
                    "title": comment.blog.title,
                    "author": comment.blog.creator.name
                }
            })
        
        return comment_list
        
    except Exception as e:
        logger.error(f"User comments retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve your comments"
        )








@router.patch("/{user_id}/update", response_model=UserResponse)
async def admin_update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user (Admin only)
    
    Allows admin to update any user's information including active status
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
        
        update_data = user_data.dict(exclude_unset=True)
        
        # Check email uniqueness if email is being updated
        if "email" in update_data and update_data["email"] != user.email:
            existing_user = db.query(User).filter(User.email == update_data["email"]).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Update user fields
        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"User updated by admin: {user.email} by {current_user.email}")
        
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin user update error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )