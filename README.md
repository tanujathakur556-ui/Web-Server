# Blog API

A modern, full-featured blog API built with FastAPI, SQLAlchemy, and PostgreSQL. This API provides comprehensive blog management functionality including user authentication, blog posts, comments, likes, categories, and tags.

## Features

### 🔐 Authentication & Authorization
- JWT-based authentication
- User registration and login
- Password hashing with bcrypt
- Role-based access control (Admin/User)
- Token refresh functionality

### 📝 Blog Management
- Create, read, update, delete blog posts
- Rich text content support
- Blog categorization and tagging
- Featured posts functionality
- Draft and published states
- View count tracking
- Blog search functionality

### 💬 Interactive Features
- Comment system with nested replies
- Like/unlike functionality
- User engagement tracking
- Comment moderation (approval system)

### 👥 User Management
- User profiles with statistics
- Admin user management
- User activity tracking
- Personal blog management

### 🏷️ Content Organization
- Categories with descriptions
- Tag system with color coding
- Content filtering and sorting
- Popular tags tracking

## Tech Stack

- **Backend Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT (JSON Web Tokens)
- **Password Hashing**: Passlib with bcrypt
- **Validation**: Pydantic
- **CORS**: FastAPI CORS middleware

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration settings
├── database.py          # Database connection and session management
├── models.py            # SQLAlchemy database models
├── schemas.py           # Pydantic data validation schemas
├── auth_routes.py       # Authentication endpoints
├── blog_routes.py       # Blog management endpoints
├── user_routes.py       # User management endpoints
└── auth.py              # Authentication utilities (not shown)
```

## Database Schema

### Core Models

**User**
- Personal information (name, email)
- Authentication (password hash)
- Status flags (active, admin)
- Relationships to blogs, comments, likes

**Blog**
- Content (title, body, excerpt)
- Metadata (view count, featured status)
- Publishing (draft/published, publication date)
- Relationships to author, category, tags, comments, likes

**Category**
- Name and description
- Active status
- Blog relationships

**Tag**
- Name and color
- Many-to-many relationship with blogs

**Comment**
- Content and approval status
- Nested structure (parent-child relationships)
- User and blog relationships

**Like**
- Simple user-blog relationship
- Unique constraint to prevent duplicate likes

## API Endpoints

### Authentication (`/auth`)
- `POST /auth/register` - User registration
- `POST /auth/login` - Login with form data
- `POST /auth/login-email` - Login with JSON
- `GET /auth/me` - Get current user info
- `POST /auth/logout` - Logout
- `POST /auth/change-password` - Change password
- `POST /auth/refresh-token` - Refresh access token
- `GET /auth/users` - Get all users (Admin)
- `PATCH /auth/users/{user_id}/toggle-status` - Toggle user status (Admin)

### Blog Management (`/blog`)
- `POST /blog/` - Create blog
- `GET /blog/` - Get blogs with filtering and pagination
- `GET /blog/{blog_id}` - Get specific blog
- `PUT /blog/{blog_id}` - Update blog
- `DELETE /blog/{blog_id}` - Delete blog
- `POST /blog/{blog_id}/like` - Toggle blog like
- `GET /blog/{blog_id}/comments` - Get blog comments
- `POST /blog/{blog_id}/comments` - Create comment
- `GET /blog/categories/` - Get categories
- `POST /blog/categories/` - Create category
- `GET /blog/tags/` - Get popular tags

### User Management (`/user`)
- `GET /user/profile` - Get my profile with stats
- `PUT /user/profile` - Update my profile
- `GET /user/{user_id}` - Get public user profile
- `GET /user/my/blogs` - Get my blogs
- `GET /user/{user_id}/blogs` - Get user's blogs
- `GET /user/my/stats` - Get detailed statistics
- `DELETE /user/my/blogs/{blog_id}` - Delete my blog
- `GET /user/my/liked-blogs` - Get liked blogs
- `GET /user/my/comments` - Get my comments
- `PATCH /user/{user_id}/update` -  Update user

## Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL
- pip or pipenv

### Environment Variables
Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql://username:password@localhost/blog_db
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd blog-api
   ```

2. **Install dependencies**
   ```bash
   pip install fastapi uvicorn sqlalchemy psycopg2-binary passlib python-jose python-multipart pydantic-settings
   ```

3. **Set up PostgreSQL database**
   ```sql
   CREATE DATABASE blog_db;
   CREATE USER blog_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE blog_db TO blog_user;
   ```

4. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## Usage Examples

### Authentication
```python
# Register a new user
POST /auth/register
{
    "name": "Your Name",
    "email": "test@example.com",
    "password": "SecurePass123"
}

# Login
POST /auth/login
{
    "username": "test@example.com",  # OAuth2 standard uses 'username'
    "password": "SecurePass123"
}
```

### Blog Operations
```python
# Create a blog post
POST /blog/
Authorization: Bearer <token>
{
    "title": "My First Blog Post",
    "body": "This is the content of my blog post...",
    "excerpt": "Short description",
    "category_id": 1,
    "tag_names": ["python", "fastapi"],
    "is_published": true
}

# Get blogs with filters
GET /blog/?category_id=1&tag_names=python&search=fastapi&page=1&per_page=10
```

## Features in Detail

### Authentication & Security
- JWT tokens with 30-minute expiration
- Secure password hashing with bcrypt
- Role-based access control
- CORS protection
- Input validation and sanitization

### Blog System
- Rich content support with title, body, and excerpt
- Automatic excerpt generation from content
- View tracking and analytics
- Publication workflow (draft → published)
- Featured posts system

### Engagement Features
- Nested comment system with approval workflow
- Like system with duplicate prevention
- User activity tracking
- Statistics and analytics

### Admin Features
- User management (activate/deactivate)
- Content moderation
- System-wide statistics
- Bulk operations support

### API Design
- RESTful architecture
- Comprehensive error handling
- Consistent response formats
- Pagination for large datasets
- Advanced filtering and searching
- OpenAPI/Swagger documentation

## Performance Features

- Database connection pooling
- Efficient query optimization with SQLAlchemy
- Pagination to handle large datasets
- Indexed database columns for fast searches
- Lazy loading of relationships

## Troubleshooting

### Common Issues

**Database Connection Error**
```bash
# Check if PostgreSQL is running
sudo service postgresql status

# Verify database credentials in .env file
# Ensure database exists and user has proper permissions
```

**Migration Errors**
```bash
# Reset migrations (development only)
alembic downgrade base
alembic upgrade head

# Check for model conflicts
alembic history --verbose
```

**Import Errors**
```bash
# Ensure virtual environment is activated
# Verify all dependencies are installed
pip install -r requirements.txt
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, email tanujathakur556@gmail.com or create an issue in the repository.