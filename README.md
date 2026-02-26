# FastAPI Boilerplate

FastAPI boilerplate for building production-ready microservices with clean architecture, SQLAlchemy, async support, and best practices out of the box.

## Features

- Clean Architecture - Modular design by features (auth, user, health)
- JWT Authentication - Access + refresh tokens with rotation
- RBAC Authorization - Role-Based Access Control with granular permissions
- SQLAlchemy 2.x Async - Modern async ORM with full typing
- BaseRepository Pattern - Generic CRUD operations to reduce boilerplate
- Alembic Migrations - Database version control
- Argon2 Hashing - Secure password and token hashing
- Structured Logging - Structlog with JSON output for production
- Pre-commit Hooks - Ruff, mypy, and code quality checks
- Docker Ready - Docker Compose for local development
- Swagger UI - Interactive API documentation with auth

## Project Structure

```
app/
├── domain/              # Business logic organized by features
│   ├── auth/           # Authentication & authorization
│   │   ├── model.py    # User, Role, Permission, RefreshToken
│   │   ├── service.py  # AuthService, PermissionService
│   │   ├── dependencies.py  # get_current_user_id, require_permission
│   │   ├── api.py      # /auth endpoints
│   │   ├── schema.py   # Request/Response schemas
│   │   └── router.py
│   ├── user/           # User CRUD operations
│   │   ├── api.py      # /users endpoints
│   │   ├── service.py  # UserService (extends BaseRepository)
│   │   ├── schema.py
│   │   └── router.py
│   └── health/         # Health check
│       ├── api.py
│       └── router.py
├── core/               # Shared utilities
│   ├── config.py       # Settings with Pydantic
│   ├── jwt.py          # JWT token generation/validation
│   ├── security.py     # Password hashing with Argon2
│   ├── logging.py      # Structlog configuration
│   └── middleware.py   # Request logging middleware
├── infrastructure/     # External services
│   └── db/
│       ├── base.py     # SQLAlchemy Base
│       ├── session.py  # Async session factory
│       ├── dependencies.py  # get_db dependency
│       └── repository.py    # BaseRepository[T]
├── scripts/            # Utility scripts
│   ├── seed_permissions.py
│   └── create_admin.py
└── main.py            # FastAPI app initialization
```

## Quick Start

### 1. Install dependencies

```bash
poetry install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run migrations

```bash
poetry run alembic upgrade head
```

### 4. Seed initial data

```bash
# Create roles and permissions
poetry run python -m app.scripts.seed_permissions

# Create admin user
poetry run python -m app.scripts.create_admin
```

### 5. Run the application

```bash
poetry run uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs for Swagger UI.

## Authentication Flow

### 1. Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "abc123...",
  "token_type": "bearer"
}
```

- Access token expires in 15 minutes
- Refresh token expires in 7 days
- Refresh token is hashed with Argon2 before storage

### 2. Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "abc123..."
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "xyz789...",
  "token_type": "bearer"
}
```

- Old refresh token is revoked (rotation)
- New tokens are issued
- Prevents token reuse attacks

### 3. Logout
```http
POST /api/v1/auth/logout
Authorization: Bearer eyJ...
```

- Revokes all refresh tokens for the user
- Access tokens expire naturally

## Authorization (RBAC)

### Permission Format

Permissions follow the pattern: `resource:action`

Examples:
- `user:create` - Create users
- `user:read` - Read user information
- `user:update` - Update users
- `user:delete` - Delete users
- `role:manage` - Manage roles and permissions

### Protecting Endpoints

```python
from app.domain.auth.dependencies import require_permission

@router.post("/users", response_model=UserRead)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_permission("user:create")),
):
    # Only users with "user:create" permission can access
    return await user_service.create_user(db, ...)
```

### How It Works

1. **Request arrives** with JWT in `Authorization: Bearer <token>`
2. **`require_permission("user:create")`** dependency executes:
   - Extracts `user_id` from JWT
   - Queries database for user's roles and permissions
   - Checks if `"user:create"` is in user's permissions
3. **Returns 401** if token is invalid
4. **Returns 403** if user lacks permission
5. **Continues** to endpoint if authorized

### Why Permissions Are NOT in JWT

Bad approach: Store permissions in JWT claims
- Requires token reissue when permissions change
- Tokens become large with many permissions
- Security risk if tokens are long-lived

Good approach: Query permissions on each request
- Permissions can be changed instantly
- JWT only contains `user_id`
- Minimal token size
- Better security

### Default Roles

After running `seed_permissions`:

- **admin**: All permissions
- **user**: Only `user:read`

### Programmatic Permission Checks

```python
from app.domain.auth.service import PermissionService

# Get all user permissions
permissions = await PermissionService.get_user_permissions(db, user_id)
# Returns: {"user:create", "user:read", "user:update", ...}

# Check specific permission
has_perm = await PermissionService.has_permission(db, user_id, "user:delete")
# Returns: True or False
```

## BaseRepository Pattern

All services can extend `BaseRepository[T]` to get common CRUD operations for free.

### Example

```python
from app.infrastructure.db.repository import BaseRepository
from app.domain.auth.model import User

class UserService(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    # Inherited methods (no need to implement):
    # - get_by_id(db, id) -> User | None
    # - list(db, skip, limit) -> list[User]
    # - create(db, entity) -> User
    # - delete(db, id) -> bool

    # Only implement custom business logic:
    async def create_user(self, db, first_name, last_name, email, password):
        # Custom validation and password hashing
        ...
```

### Benefits

- Eliminates repetitive CRUD code
- Consistent API across all services
- Type-safe with generics
- Easy to extend with custom methods

## User Abstraction

When working with users in your code, always import from `app.domain.auth.model`:

```python
# Correct
from app.domain.auth.model import User

# Wrong - this module doesn't exist
from app.domain.user.model import User
```

**Why?**
- `User` model lives in `auth` domain (identity, authentication, authorization)
- `user` domain only handles CRUD operations on the User resource
- This separation keeps authentication/authorization logic centralized

### When to Use Each Domain

**`app.domain.auth/`** - Use for:
- User model definition
- Authentication (login, logout, refresh)
- Authorization (roles, permissions)
- Token management
- Security-related operations

**`app.domain.user/`** - Use for:
- User CRUD endpoints (`GET /users`, `POST /users`, etc.)
- User management operations
- User-specific business logic (not auth-related)

## Code Quality

### Pre-commit Hooks

Automatically runs on every commit:

```bash
# Install hooks
poetry run pre-commit install

# Run manually
poetry run pre-commit run --all-files
```

Includes:
- **Ruff** - Fast Python linter and formatter
- **MyPy** - Static type checking
- **General hooks** - Trailing whitespace, EOF, YAML/JSON validation, secret detection

### Manual Commands

```bash
# Linting
poetry run ruff check app/ --fix

# Formatting
poetry run ruff format app/

# Type checking
poetry run mypy app/
```

## Database Migrations

### Create Migration

```bash
poetry run alembic revision --autogenerate -m "description"
```

### Apply Migrations

```bash
poetry run alembic upgrade head
```

### Rollback

```bash
poetry run alembic downgrade -1
```

## Docker

```bash
# Start services
docker compose up -d

# Run migrations
docker compose exec api poetry run alembic upgrade head

# Seed data
docker compose exec api poetry run python -m app.scripts.seed_permissions
docker compose exec api poetry run python -m app.scripts.create_admin

# View logs
docker compose logs -f api
```

## Testing with Swagger UI

1. Go to http://localhost:8000/docs
2. Click **"Authorize"** button (top right)
3. Login via `POST /api/v1/auth/login`
4. Copy the `access_token` from response
5. Paste token in the authorization modal
6. Click **"Authorize"**
7. Now all requests will include the token automatically

## Extending the System

### Add New Permission

```python
# In seed script or admin endpoint
permission = Permission(
    code="invoice:create",
    description="Create invoices"
)
db.add(permission)
await db.commit()
```

### Create Custom Role

```python
role = Role(name="accountant", description="Financial access")
db.add(role)
await db.flush()

# Assign permissions
await db.execute(
    role_permissions.insert().values([
        {"role_id": role.id, "permission_id": invoice_create.id},
        {"role_id": role.id, "permission_id": invoice_read.id},
    ])
)
await db.commit()
```

### Add New Feature Module

```bash
mkdir -p app/domain/invoice
touch app/domain/invoice/{__init__.py,model.py,schema.py,service.py,api.py,router.py}
```

Follow the same pattern as `user` or `auth` modules.

## Observability & Logging

### Structured Logging with Structlog

The application uses **structlog** for structured, production-ready logging.

**Features:**
- JSON output in production for log aggregation (ELK, Datadog, CloudWatch)
- Human-readable console output in development
- Automatic request logging with unique `request_id`
- Context binding (user_id, request_id, etc.)

### Configuration

Logging is configured in `app/core/logging.py` and initialized on app startup:

```python
from app.core.logging import configure_logging

configure_logging()  # Called in main.py
```

**Environment-based behavior:**
- `debug=True` (development): Console renderer with colors
- `debug=False` (production): JSON renderer for log aggregation

### Request Logging Middleware

All HTTP requests are automatically logged with:
- `request_id` - Unique identifier for request tracing
- `method` - HTTP method (GET, POST, etc.)
- `path` - Request path
- `client_ip` - Client IP address
- `status_code` - Response status code
- `duration_ms` - Request duration in milliseconds

The `request_id` is also added to response headers as `X-Request-ID`.

### Usage in Code

```python
import structlog

logger = structlog.get_logger(__name__)

# Simple log
logger.info("user_created", user_id=123, email="user@example.com")

# Warning
logger.warning("rate_limit_exceeded", user_id=123, attempts=5)

# Error with exception
try:
    ...
except Exception as exc:
    logger.exception("operation_failed", operation="create_user", error=str(exc))
```

### Log Output Examples

**Development (console):**
```
2024-02-01 10:30:45 [info     ] request_started method=POST path=/api/v1/users request_id=abc-123
2024-02-01 10:30:45 [info     ] user_created user_id=42 email=user@example.com
2024-02-01 10:30:45 [info     ] request_completed status_code=201 duration_ms=45.2
```

**Production (JSON):**
```json
{
  "event": "request_started",
  "level": "info",
  "timestamp": "2024-02-01T10:30:45.123Z",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/api/v1/users",
  "client_ip": "192.168.1.1"
}
```

### Context Binding

Bind context that persists across multiple log calls:

```python
import structlog

# Bind context for current request
structlog.contextvars.bind_contextvars(
    user_id=user_id,
    organization_id=org_id,
)

# All subsequent logs will include this context
logger.info("action_performed")  # Includes user_id and organization_id
```

### Best Practices

1. **Use structured fields** instead of string formatting:
   ```python
   # Good
   logger.info("user_login", user_id=123, email="user@example.com")

   # Bad
   logger.info(f"User {user_id} logged in with {email}")
   ```

2. **Use consistent event names**: `resource_action` format
   - `user_created`, `user_updated`, `user_deleted`
   - `token_refreshed`, `authentication_failed`

3. **Never log sensitive data**: passwords, tokens, credit cards

4. **Use appropriate log levels**:
   - `debug` - Detailed diagnostic information
   - `info` - General informational messages
   - `warning` - Warning messages (recoverable issues)
   - `error` - Error messages (failures)
   - `exception` - Errors with stack traces

### Integration with Monitoring

JSON logs can be easily integrated with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Datadog**
- **AWS CloudWatch**
- **Google Cloud Logging**
- **Grafana Loki**

Filter and search by any field:
```
request_id:"abc-123"
user_id:42 AND level:"error"
path:"/api/v1/users" AND status_code:500
```

## Security Best Practices

- Passwords hashed with Argon2
- Refresh tokens hashed before storage
- Token rotation on refresh
- JWT only contains minimal data (user_id)
- Permissions checked on every request
- No sensitive data in logs
- HTTPS recommended for production
- Secret key from environment variables

## License

MIT
