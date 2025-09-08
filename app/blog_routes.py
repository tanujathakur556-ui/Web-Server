# app/blog_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, or_, func
from typing import List, Optional
import logging
from datetime import datetime

from app.database import get_db
from app.models import Blog, User, Category, Tag, Comment, Like, blog_tags
from app.schemas import (
    BlogCreate, BlogUpdate, BlogResponse, BlogWithStats, BlogListResponse,
    PaginationResponse, PaginationParams, BlogFilter, BaseResponse,
    CommentCreate, CommentResponse, CommentUpdate, TagCreate, TagResponse,
    CategoryCreate, CategoryResponse, CategoryWithStats
)
from app.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# BLOG CRUD OPERATIONS

@router.post("/", response_model=BlogResponse, status_code=status.HTTP_201_CREATED)
async def create_blog(
    blog_data: BlogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new blog post
    
    - **title**: Blog title (5-200 characters)
    - **body**: Blog content (minimum 50 characters)
    - **excerpt**: Short description (optional, max 300 characters)
    - **category_id**: Category ID (optional)
    - **tag_names**: List of tag names (optional)
    - **is_published**: Publication status (default: false)
    - **is_featured**: Featured status (default: false)
    """
    try:
        # Validate category if provided
        if blog_data.category_id:
            category = db.query(Category).filter(Category.id == blog_data.category_id).first()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category not found"
                )
        
        # Create excerpt from body if not provided
        excerpt = blog_data.excerpt
        if not excerpt:
            excerpt = blog_data.body[:297] + "..." if len(blog_data.body) > 300 else blog_data.body
        
        # Create new blog
        new_blog = Blog(
            title=blog_data.title,
            body=blog_data.body,
            excerpt=excerpt,
            category_id=blog_data.category_id,
            is_published=blog_data.is_published,
            is_featured=blog_data.is_featured,
            user_id=current_user.id,
            published_at=datetime.utcnow() if blog_data.is_published else None
        )
        
        db.add(new_blog)
        db.flush()  # Get the ID without committing
        
        # Handle tags
        if blog_data.tag_names:
            for tag_name in blog_data.tag_names:
                tag_name = tag_name.strip().lower()
                if not tag_name:
                    continue
                    
                # Get or create tag
                tag = db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.add(tag)
                    db.flush()
                
                # Associate tag with blog
                new_blog.tags.append(tag)
        
        db.commit()
        db.refresh(new_blog)
        
        logger.info(f"Blog created: {new_blog.title} by {current_user.email}")
        
        # Return with relationships loaded
        blog_with_relations = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        ).filter(Blog.id == new_blog.id).first()
        
        return BlogResponse.from_orm(blog_with_relations)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Blog creation error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create blog"
        )


@router.get("/", response_model=BlogListResponse)
async def get_blogs(
    pagination: PaginationParams = Depends(),
    filters: BlogFilter = Depends(),
    sort_by: str = Query("created_at", description="Sort field: created_at, title, view_count"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get blogs with pagination, filtering, and sorting
    
    **Filters:**
    - **category_id**: Filter by category
    - **tag_names**: Filter by tag names
    - **is_published**: Filter by publication status
    - **is_featured**: Filter by featured status
    - **author_id**: Filter by author
    - **search**: Search in title and content
    
    **Pagination:**
    - **page**: Page number (default: 1)
    - **per_page**: Items per page (default: 10, max: 100)
    
    **Sorting:**
    - **sort_by**: created_at, title, view_count
    - **sort_order**: asc, desc
    """
    try:
        # Base query with relationships
        query = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        )
        
        # Apply filters
        if filters.category_id:
            query = query.filter(Blog.category_id == filters.category_id)
        
        if filters.is_published is not None:
            query = query.filter(Blog.is_published == filters.is_published)
        
        if filters.is_featured is not None:
            query = query.filter(Blog.is_featured == filters.is_featured)
        
        if filters.author_id:
            query = query.filter(Blog.user_id == filters.author_id)
        
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Blog.title.ilike(search_term),
                    Blog.body.ilike(search_term)
                )
            )
        
        if filters.tag_names:
            query = query.join(Blog.tags).filter(Tag.name.in_(filters.tag_names))
        
        # Apply sorting
        sort_column = getattr(Blog, sort_by, Blog.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (pagination.page - 1) * pagination.per_page
        blogs = query.offset(offset).limit(pagination.per_page).all()
        
        # Calculate pagination metadata
        pages = (total + pagination.per_page - 1) // pagination.per_page
        has_next = pagination.page < pages
        has_prev = pagination.page > 1
        
        # Get additional stats for each blog
        blog_stats = []
        for blog in blogs:
            # Get comment count
            comment_count = db.query(Comment).filter(
                Comment.blog_id == blog.id,
                Comment.is_approved == True
            ).count()
            
            # Get like count
            like_count = db.query(Like).filter(Like.blog_id == blog.id).count()
            
            # Check if current user liked this blog
            is_liked = False
            if current_user:
                like = db.query(Like).filter(
                    Like.blog_id == blog.id,
                    Like.user_id == current_user.id
                ).first()
                is_liked = like is not None
            
            blog_data = BlogResponse.from_orm(blog)
            blog_with_stats = BlogWithStats(
                **blog_data.dict(),
                comment_count=comment_count,
                like_count=like_count,
                is_liked=is_liked
            )
            blog_stats.append(blog_with_stats)
        
        pagination_info = PaginationResponse(
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return BlogListResponse(
            blogs=blog_stats,
            pagination=pagination_info
        )
        
    except Exception as e:
        logger.error(f"Blog retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve blogs"
        )


@router.get("/{blog_id}", response_model=BlogWithStats)
async def get_blog(
    blog_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get a specific blog by ID
    
    - **blog_id**: Blog ID
    
    Automatically increments view count
    """
    try:
        blog = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        ).filter(Blog.id == blog_id).first()
        
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Increment view count
        blog.view_count += 1
        db.commit()
        
        # Get additional stats
        comment_count = db.query(Comment).filter(
            Comment.blog_id == blog.id,
            Comment.is_approved == True
        ).count()
        
        like_count = db.query(Like).filter(Like.blog_id == blog.id).count()
        
        is_liked = False
        if current_user:
            like = db.query(Like).filter(
                Like.blog_id == blog.id,
                Like.user_id == current_user.id
            ).first()
            is_liked = like is not None
        
        blog_data = BlogResponse.from_orm(blog)
        return BlogWithStats(
            **blog_data.dict(),
            comment_count=comment_count,
            like_count=like_count,
            is_liked=is_liked
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Blog retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve blog"
        )


@router.put("/{blog_id}", response_model=BlogResponse)
async def update_blog(
    blog_id: int,
    blog_data: BlogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a blog post
    
    Only the blog author or admin can update a blog
    """
    try:
        blog = db.query(Blog).filter(Blog.id == blog_id).first()
        
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Check permissions
        if blog.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this blog"
            )
        
        # Update fields
        update_data = blog_data.dict(exclude_unset=True)
        
        # Handle category validation
        if "category_id" in update_data and update_data["category_id"]:
            category = db.query(Category).filter(Category.id == update_data["category_id"]).first()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category not found"
                )
        
        # Handle publication status change
        if "is_published" in update_data:
            if update_data["is_published"] and not blog.published_at:
                blog.published_at = datetime.utcnow()
            elif not update_data["is_published"]:
                blog.published_at = None
        
        # Update blog fields
        for field, value in update_data.items():
            if field != "tag_names":  # Handle tags separately
                setattr(blog, field, value)
        
        # Handle tags if provided
        if "tag_names" in update_data:
            # Clear existing tags
            blog.tags.clear()
            
            # Add new tags
            for tag_name in update_data["tag_names"]:
                tag_name = tag_name.strip().lower()
                if not tag_name:
                    continue
                    
                tag = db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.add(tag)
                    db.flush()
                
                blog.tags.append(tag)
        
        db.commit()
        db.refresh(blog)
        
        logger.info(f"Blog updated: {blog.title} by {current_user.email}")
        
        # Return with relationships loaded
        updated_blog = db.query(Blog).options(
            joinedload(Blog.creator),
            joinedload(Blog.category),
            joinedload(Blog.tags)
        ).filter(Blog.id == blog.id).first()
        
        return BlogResponse.from_orm(updated_blog)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Blog update error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update blog"
        )


@router.delete("/{blog_id}", response_model=BaseResponse)
async def delete_blog(
    blog_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a blog post
    
    Only the blog author or admin can delete a blog
    """
    try:
        blog = db.query(Blog).filter(Blog.id == blog_id).first()
        
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Check permissions
        if blog.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this blog"
            )
        
        blog_title = blog.title
        db.delete(blog)
        db.commit()
        
        logger.info(f"Blog deleted: {blog_title} by {current_user.email}")
        
        return BaseResponse(
            success=True,
            message=f"Blog '{blog_title}' deleted successfully"
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



# BLOG INTERACTION ENDPOINTS


@router.post("/{blog_id}/like", response_model=BaseResponse)
async def toggle_blog_like(
    blog_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle like on a blog post
    
    If already liked, removes the like. If not liked, adds a like.
    """
    try:
        blog = db.query(Blog).filter(Blog.id == blog_id).first()
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Check if user already liked this blog
        existing_like = db.query(Like).filter(
            Like.blog_id == blog_id,
            Like.user_id == current_user.id
        ).first()
        
        if existing_like:
            # Remove like
            db.delete(existing_like)
            message = "Like removed"
            action = "unliked"
        else:
            # Add like
            new_like = Like(blog_id=blog_id, user_id=current_user.id)
            db.add(new_like)
            message = "Blog liked"
            action = "liked"
        
        db.commit()
        
        logger.info(f"Blog {action}: {blog.title} by {current_user.email}")
        
        return BaseResponse(
            success=True,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Blog like toggle error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle like"
        )



# COMMENT ENDPOINTS


@router.get("/{blog_id}/comments", response_model=List[CommentResponse])
async def get_blog_comments(
    blog_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all approved comments for a blog post
    """
    try:
        blog = db.query(Blog).filter(Blog.id == blog_id).first()
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        comments = db.query(Comment).options(
            joinedload(Comment.author)
        ).filter(
            Comment.blog_id == blog_id,
            Comment.is_approved == True,
            Comment.parent_id == None  # Only top-level comments
        ).order_by(desc(Comment.created_at)).all()
        
        # Get replies for each comment
        comment_responses = []
        for comment in comments:
            replies = db.query(Comment).options(
                joinedload(Comment.author)
            ).filter(
                Comment.parent_id == comment.id,
                Comment.is_approved == True
            ).order_by(asc(Comment.created_at)).all()
            
            comment_data = CommentResponse.from_orm(comment)
            comment_data.replies = [CommentResponse.from_orm(reply) for reply in replies]
            comment_responses.append(comment_data)
        
        return comment_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve comments"
        )


@router.post("/{blog_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    blog_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new comment on a blog post
    
    - **content**: Comment content (3-1000 characters)
    - **parent_id**: Parent comment ID for replies (optional)
    """
    try:
        blog = db.query(Blog).filter(Blog.id == blog_id).first()
        if not blog:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog not found"
            )
        
        # Validate parent comment if provided
        if comment_data.parent_id:
            parent_comment = db.query(Comment).filter(
                Comment.id == comment_data.parent_id,
                Comment.blog_id == blog_id
            ).first()
            if not parent_comment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent comment not found"
                )
        
        new_comment = Comment(
            content=comment_data.content,
            blog_id=blog_id,
            user_id=current_user.id,
            parent_id=comment_data.parent_id
        )
        
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        
        logger.info(f"Comment created on blog {blog.title} by {current_user.email}")
        
        # Return with author loaded
        comment_with_author = db.query(Comment).options(
            joinedload(Comment.author)
        ).filter(Comment.id == new_comment.id).first()
        
        return CommentResponse.from_orm(comment_with_author)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Comment creation error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comment"
        )



# CATEGORY ENDPOINTS


@router.get("/categories/", response_model=List[CategoryWithStats])
async def get_categories(db: Session = Depends(get_db)):
    """
    Get all active categories with blog counts
    """
    try:
        categories = db.query(Category).filter(Category.is_active == True).all()
        
        category_stats = []
        for category in categories:
            blog_count = db.query(Blog).filter(
                Blog.category_id == category.id,
                Blog.is_published == True
            ).count()
            
            category_data = CategoryResponse.from_orm(category)
            category_with_stats = CategoryWithStats(
                **category_data.dict(),
                blog_count=blog_count
            )
            category_stats.append(category_with_stats)
        
        return category_stats
        
    except Exception as e:
        logger.error(f"Category retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories"
        )



# Category Endpoints


@router.post("/categories/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new category"""
    existing = db.query(Category).filter(Category.name == category_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    new_category = Category(
        name=category_data.name,
        description=category_data.description,
        is_active=True
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category




# TAG ENDPOINTS


@router.get("/tags/", response_model=List[TagResponse])
async def get_popular_tags(
    limit: int = Query(20, ge=1, le=100, description="Number of tags to return"),
    db: Session = Depends(get_db)
):
    """
    Get popular tags ordered by usage count
    """
    try:
        # Get tags with their usage count
        tags_with_count = db.query(
            Tag,
            func.count(blog_tags.c.blog_id).label('usage_count')
        ).join(
            blog_tags, Tag.id == blog_tags.c.tag_id, isouter=True
        ).join(
            Blog, blog_tags.c.blog_id == Blog.id, isouter=True
        ).filter(
            or_(Blog.is_published == True, Blog.id == None)
        ).group_by(Tag.id).order_by(
            desc('usage_count')
        ).limit(limit).all()
        
        return [TagResponse.from_orm(tag) for tag, count in tags_with_count]
        
    except Exception as e:
        logger.error(f"Tag retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tags"
        )
    







