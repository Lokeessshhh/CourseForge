# LearnAI Django Backend

A Django REST Framework backend for the LearnAI course generation platform. Features AI-powered course creation, RAG-based tutoring, quiz management, and certificate generation.

## Architecture Overview

- **Framework**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL with pgvector extension
- **Cache/Broker**: Redis
- **Async Tasks**: Celery
- **WebSockets**: Django Channels
- **AI Integration**: vLLM (Qwen 7B) for LLM, sentence-transformers for embeddings
- **Authentication**: Clerk JWT with Redis-cached JWKS
- **Security**: Rate limiting, security headers, webhook verification

## Project Structure

```
backend/
├── config/                 # Django project configuration
│   ├── settings/
│   │   ├── base.py        # Base settings
│   │   ├── development.py # Dev settings (debug, no rate limits)
│   │   └── production.py  # Production settings (security hardening)
│   ├── urls.py            # Root URL configuration + health check
│   ├── asgi.py            # ASGI application
│   └── wsgi.py            # WSGI application
├── apps/                   # Django applications
│   ├── users/             # User management & Clerk auth
│   ├── courses/           # Course, Week, Day models
│   ├── rag/               # Document & Chunk models for RAG
│   ├── conversations/     # Chat history with embeddings
│   ├── quizzes/           # Quiz questions & attempts
│   ├── certificates/      # Course completion certificates
│   ├── cache/             # Semantic query cache
│   └── websockets/        # WebSocket consumers
├── services/               # Business logic services
│   ├── auth/              # Clerk JWT authentication + webhook verification
│   ├── llm/               # LLM client & embeddings
│   ├── rag_pipeline/      # RAG components (retriever, reranker, etc.)
│   └── external/          # External API integrations
├── utils/                  # Utility functions
│   ├── middleware.py      # Security headers, rate limiting, request logging
│   ├── exceptions.py      # Custom exception handling
│   ├── pgvector.py        # Vector operations
│   └── streaming.py       # SSE/WebSocket streaming
├── manage.py
├── requirements.txt
└── .env.example
```

## Security Features

### Authentication
- **Clerk JWT Authentication**: Validates JWTs against Clerk's JWKS endpoint
- **Redis-cached JWKS**: 1-hour TTL to reduce external API calls
- **Auth Rate Limiting**: 10 failed attempts per minute per IP → 5-minute block

### API Security
- **Rate Limiting**: 1000 requests/hour per IP (production)
- **Security Headers**: CSP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy
- **CORS**: Strict origin validation in production
- **Request Logging**: Structured JSON logging for all API requests

### Webhook Verification
- **Svix Signature Validation**: HMAC-SHA256 timing-safe comparison
- **Replay Attack Prevention**: 5-minute timestamp window
- **Clerk Webhooks**: User creation, update, deletion events

### Data Protection
- **Ownership Checks**: All resources require user ownership
- **404 on Unauthorized**: Returns 404 instead of 403 to prevent enumeration
- **Structured Error Responses**: Consistent JSON format, no internal details exposed

## Prerequisites

- Python 3.10+
- PostgreSQL 15+ with pgvector extension
- Redis 7+
- (Optional) vLLM server for LLM inference

## Quick Start

### 1. Clone and Setup Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

Key environment variables:
- `DJANGO_SECRET_KEY`: Django secret key
- `DB_*`: PostgreSQL connection settings
- `REDIS_URL`: Redis connection URL
- `CLERK_*`: Clerk authentication settings
- `VLLM_*`: vLLM server configuration
- `RATE_LIMIT_*`: Rate limiting configuration

### 3. Setup Database

```bash
# Create PostgreSQL database
createdb learnai

# Enable pgvector extension
psql -d learnai -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
python manage.py migrate
```

### 4. Start Development Server

```bash
# Start Django development server
python manage.py runserver

# Start Celery worker (in another terminal)
celery -A config worker -l info --pool=solo -Q course_generation,quiz_generation,certificates

# Start Celery beat for periodic tasks (optional)
celery -A config beat -l info

# Start Daphne for WebSockets (optional, for ASGI)
daphne -b 0.0.0.0 -p 8001 config.asgi:application
```

## API Endpoints

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health/` | System health (DB, Redis, vLLM, Celery) |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/me/` | Get current user profile |
| `PUT` | `/api/users/me/` | Update user profile |
| `GET` | `/api/users/me/knowledge-state/` | Get user knowledge states |
| `GET` | `/api/users/me/quiz-history/` | Get user quiz history |
| `POST` | `/api/webhooks/clerk/` | Clerk webhook handler |

### Courses
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/courses/generate/` | Create course (AI generation) |
| `GET` | `/api/courses/` | List user's courses |
| `GET` | `/api/courses/{id}/` | Get course details |
| `GET` | `/api/courses/{id}/status/` | Get generation status |
| `DELETE` | `/api/courses/{id}/` | Delete course |
| `GET` | `/api/courses/{id}/progress/` | Get course progress |
| `GET` | `/api/courses/{id}/weeks/` | Get all weeks |
| `GET` | `/api/courses/{id}/weeks/{w}/` | Get week details |
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/` | Get day content |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/complete/` | Mark day complete |

### Quizzes
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/` | Get quiz questions |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/submit/` | Submit quiz answers |
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/results/` | Get quiz results |

### Certificates
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/certificates/` | List user's certificates |
| `GET` | `/api/courses/{id}/certificate/` | Get course certificate |

### RAG (Retrieval Augmented Generation)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/rag/upload/` | Upload document |
| `GET` | `/api/rag/documents/` | List documents |
| `DELETE` | `/api/rag/documents/{id}/` | Delete document |
| `POST` | `/api/rag/search/` | Semantic search |

### Conversations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/conversations/` | List conversations |
| `POST` | `/api/conversations/` | Create conversation |
| `GET` | `/api/conversations/{id}/` | Get conversation history |
| `DELETE` | `/api/conversations/{id}/` | Delete conversation |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws/chat/{session_id}/?token=<jwt>` | Real-time RAG chat |

## Services

### RAG Pipeline Components

1. **Hybrid Retriever** (`services/rag_pipeline/retriever.py`)
   - Combines pgvector dense retrieval with BM25 sparse retrieval
   - Uses Reciprocal Rank Fusion (RRF) for result ranking

2. **Reranker** (`services/rag_pipeline/reranker.py`)
   - BGE-reranker-v2-m3 for cross-encoder reranking
   - Improves retrieval precision

3. **HyDE** (`services/rag_pipeline/hyde.py`)
   - Hypothetical Document Embeddings
   - Generates hypothetical answers for better retrieval

4. **Query Decomposer** (`services/rag_pipeline/query_decompose.py`)
   - Breaks complex queries into sub-queries
   - LLM-powered or rule-based decomposition

5. **Conversation Memory** (`services/rag_pipeline/memory.py`)
   - 4-Tier memory: session, course, user, global
   - Semantic long-term memory with pgvector

6. **RAPTOR** (`services/rag_pipeline/raptor.py`)
   - Recursive Abstractive Processing
   - Tree-organized retrieval for multi-scale summarization

7. **Semantic Cache** (`services/rag_pipeline/cache.py`)
   - Redis exact-match cache
   - pgvector similarity-based cache (>0.97 cosine)

### External Services

1. **Tavily Search** (`services/external/tavily_search.py`)
   - Real-time web search for up-to-date information

2. **Judge0** (`services/external/judge0.py`)
   - Code execution and evaluation
   - Supports multiple programming languages

3. **WeasyPrint Certificates** (`services/external/weasyprint_cert.py`)
   - PDF certificate generation
   - Customizable templates

## Development

### Running Tests

```bash
python manage.py test
```

### Code Quality

```bash
# Install dev dependencies
pip install ruff black isort

# Format code
black .
isort .

# Lint
ruff check .
```

### Database Migrations

```bash
# Create migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

## Production Deployment

### Environment Setup

1. Set `DJANGO_SETTINGS_MODULE=config.settings.production`
2. Configure all security environment variables
3. Set up proper `ALLOWED_HOSTS` and `CORS_EXTRA_ORIGINS`
4. Use strong `DJANGO_SECRET_KEY` and `CLERK_WEBHOOK_SECRET`

### Security Checklist

- [ ] `DEBUG=False`
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SECURE_HSTS_SECONDS=31536000`
- [ ] `SESSION_COOKIE_SECURE=True`
- [ ] `CSRF_COOKIE_SECURE=True`
- [ ] `RATE_LIMIT_ENABLED=True`
- [ ] `CORS_EXTRA_ORIGINS` set to production domains
- [ ] All secrets stored in environment variables

### WSGI/ASGI Servers

```bash
# Gunicorn (WSGI)
gunicorn config.wsgi:application -b 0.0.0.0:8000

# Uvicorn (ASGI for WebSockets)
uvicorn config.asgi:application -b 0.0.0.0:8000
```

### Celery Workers

```bash
# Worker for course generation
celery -A config worker -l info --pool=solo -Q course_generation

# Worker for quiz generation
celery -A config worker -l info --pool=solo -Q quiz_generation

# Worker for certificates
celery -A config worker -l info --pool=solo -Q certificates

# Beat (periodic tasks)
celery -A config beat -l info
```

### Docker Deployment

```dockerfile
# Example Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "config.wsgi:application", "-b", "0.0.0.0:8000"]
```

## API Documentation

Access Swagger UI at `/api/docs/` when running the development server.

## Error Response Format

All errors return a consistent JSON format:

```json
{
  "success": false,
  "error": "Human readable error message",
  "code": 400,
  "details": {
    "field": ["Specific error for this field"]
  }
}
```

## License

MIT License
