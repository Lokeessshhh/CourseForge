# LearnAI Backend - Technical Overview

A Django REST Framework backend powering an AI-powered course generation platform. This document explains the tech stack, architecture, and implementation details.

---

## Tech Stack

### Core Framework
- **Django 4.2** - Web framework
- **Django REST Framework** - API layer
- **PostgreSQL 15+** - Primary database with pgvector extension for vector operations
- **Redis 7+** - Caching, session storage, and message broker

### Async & Real-time
- **Celery** - Distributed task queue for background processing
- **Django Channels** - WebSocket support for real-time features
- **Daphne** - ASGI server for WebSockets

### AI/ML Integration
- **vLLM Server** - Self-hosted LLM inference (Qwen 7B model)
- **OpenAI SDK** - Client library for vLLM API compatibility
- **Sentence Transformers** - Text embeddings for semantic operations

### Authentication & Security
- **Clerk** - Third-party authentication provider (JWT-based)
- **python-jose** - JWT verification
- **Svix** - Webhook signature verification

### External Services
- **Tavily** - Web search API
- **Judge0** - Code execution engine
- **WeasyPrint** - PDF certificate generation

### Development Tools
- **drf-spectacular** - OpenAPI/Swagger documentation
- **django-cors-headers** - CORS handling
- **django-extensions** - Development utilities

---

## Architecture

### Project Structure

```
backend/
├── config/                    # Django project configuration
│   ├── settings/
│   │   ├── base.py           # Base settings (shared)
│   │   ├── development.py    # Dev settings (DEBUG=True)
│   │   └── production.py    # Production settings (security hardening)
│   ├── urls.py               # Root URL routing
│   ├── asgi.py               # ASGI application (WebSockets)
│   ├── wsgi.py               # WSGI application
│   └── celery.py             # Celery app configuration
│
├── apps/                      # Django applications (domain modules)
│   ├── users/                # User management
│   ├── courses/              # Course, Week, Day models
│   ├── quizzes/              # Quiz questions & attempts
│   ├── certificates/         # Completion certificates
│   ├── conversations/        # Chat history
│   ├── cache/                # Semantic caching
│   └── websockets/           # WebSocket consumers
│
├── services/                  # Business logic layer
│   ├── auth/                 # Clerk JWT authentication
│   ├── llm/                  # LLM client & embeddings
│   ├── course/               # Course generation logic
│   ├── certificate/          # Certificate generation
│   ├── progress/             # Progress tracking
│   └── external/             # External API integrations
│       ├── tavily_search.py
│       ├── judge0.py
│       └── weasyprint_cert.py
│
├── utils/                     # Shared utilities
│   ├── middleware.py         # Security headers, rate limiting
│   ├── exceptions.py         # Custom exception handling
│   ├── pgvector.py           # Vector database operations
│   └── streaming.py          # SSE/WebSocket streaming
│
├── manage.py
├── requirements.txt
└── .env.example
```

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (DRF)                         │
│    Views, Serializers, URL Routing, Permissions              │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                              │
│    Business logic, LLM integration, External services        │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                                │
│    Django ORM, PostgreSQL, Redis, Celery tasks               │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features & Implementation

### 1. Authentication System (Clerk JWT)

We use **Clerk** as our authentication provider, implementing a stateless JWT authentication system.

#### How It Works

1. **Frontend** authenticates with Clerk and receives a JWT token
2. **Backend** validates the JWT against Clerk's JWKS (JSON Web Key Set) endpoint
3. **User Sync** - Users are automatically created/updated in our database from JWT claims

#### Implementation Details

```python
# services/auth/clerk.py

class ClerkAuthentication(BaseAuthentication):
    """
    DRF authentication backend that validates Clerk JWTs.
    """
    
    def authenticate(self, request):
        # 1. Extract Bearer token from Authorization header
        token = request.META.get("HTTP_AUTHORIZATION", "").split(" ")[1]
        
        # 2. Fetch JWKS from Clerk (cached in Redis for 1 hour)
        jwks = _fetch_jwks()
        
        # 3. Verify JWT signature using RS256 algorithm
        payload = jwt.decode(token, rsa_key, algorithms=["RS256"])
        
        # 4. Get or create user in our database
        user = User.objects.get_or_create(
            clerk_id=payload["sub"],
            defaults={"email": payload.get("email")}
        )
        
        return (user, token)
```

#### Security Features

- **JWKS Caching** - Public keys cached in Redis (1-hour TTL) to reduce API calls
- **Auth Rate Limiting** - Max 10 failed attempts per minute per IP, then 5-minute block
- **Webhook Verification** - HMAC-SHA256 signature validation for Clerk webhooks
- **Replay Attack Prevention** - 5-minute timestamp window for webhooks

---

### 2. AI-Powered Course Generation

The core feature - generating personalized learning courses using LLM.

#### Generation Flow

```
User Request → Parse Duration → Build Skeleton → AI Fill Content → Save to DB
     ↓              ↓                ↓                  ↓
  "Python,     "4 weeks"      Empty structure    LLM generates:
   1 month"                   (4 weeks ×          - Week themes
                              5 days/week)        - Day titles
                                                  - Theory content
                                                  - Code examples
                                                  - Quiz questions
```

#### Implementation Architecture

```python
# services/course/generator.py

class CourseGenerator:
    """
    Fills course skeleton with AI-generated content.
    Uses parallel processing for multiple weeks.
    """
    
    async def fill_week(self, week_data, topic, skill_level, goals):
        # Step 1: Generate week theme and objectives
        theme, objectives = await self._generate_week_theme(...)
        
        # Step 2: For each of 5 days, generate:
        for day in week_data["days"]:
            # 2a: Day title + tasks
            title, tasks = await self._generate_day_title_tasks(...)
            
            # 2b: Theory content (conceptual explanations)
            theory = await self._generate_theory_content(...)
            
            # 2c: Code examples (practical demonstrations)
            code = await self._generate_code_content(...)
            
            # 2d: Quiz questions (3 MCQs per day)
            quiz = await self._generate_quiz_questions(...)
        
        return filled_week
```

#### Parallel Processing

All weeks are generated in parallel using `asyncio.gather()`:

```python
# Create parallel tasks for all weeks
tasks = [
    self.fill_week(week_data, topic, skill_level, goals)
    for week_data in skeleton["weeks"]
]

# Run all weeks concurrently
filled_weeks = await asyncio.gather(*tasks)
```

#### LLM Integration

We use a self-hosted vLLM server running Qwen 7B:

```python
# services/llm/client.py

# OpenAI-compatible client pointing to vLLM
client = AsyncOpenAI(
    base_url="http://vllm-server:8000/v1",
    api_key="none",
)

async def generate(prompt, system_type="tutor"):
    response = await client.chat.completions.create(
        model="qwen-coder",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS[system_type]},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=3000
    )
    return response.choices[0].message.content
```

#### System Prompts

Different prompts for different generation tasks:

| Task | System Prompt Focus |
|------|---------------------|
| Course Generator | Curriculum design, progressive learning |
| Quiz Generator | Assessment creation, plausible distractors |
| Code Teacher | Working examples, step-by-step explanations |
| Tutor | Clear explanations, encouraging tone |

---

### 3. Quiz System

#### Quiz Types

1. **Daily Quizzes** - 3 MCQ questions per day (generated with content)
2. **Weekly Tests** - 10 MCQ questions covering entire week
3. **Coding Tests** - 2 coding problems per week with test cases

#### Quiz Generation

```python
async def _generate_quiz_questions(self, day_title, topic, skill_level):
    prompt = f"""Generate 3 MCQ quizzes for "{day_title}" in a {skill_level} {topic} course.
    
    Each question must:
    1. Test understanding, not just memory
    2. Have 4 plausible options (a, b, c, d)
    3. Include an explanation that teaches
    
    Return JSON:
    {{
      "quizzes": [
        {{
          "question_number": 1,
          "question_text": "Question?",
          "options": {{"a": "A", "b": "B", "c": "C", "d": "D"}},
          "correct_answer": "a",
          "explanation": "Why A is correct..."
        }}
      ]
    }}"""
    
    return await safe_json_generate(prompt, system_type="quiz_generator")
```

#### Quiz Attempt Tracking

```python
# apps/quizzes/models.py

class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    user_answer = models.TextField()
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)
```

---

### 4. Certificate Generation

PDF certificates generated upon course completion using WeasyPrint.

#### Certificate Data

- Student name
- Course topic
- Completion date
- Final score (avg quiz + test scores)
- Total study hours

#### Implementation

```python
# services/certificate/generator.py

class CertificateGenerator:
    async def generate_certificate(self, user_id, course_id):
        # 1. Calculate final stats
        final_score = (avg_quiz_score + avg_test_score) / 2
        total_hours = total_study_time / 60
        
        # 2. Generate PDF using WeasyPrint
        pdf_url = await self._generate_pdf(
            user_name=user.name,
            course_topic=course.topic,
            completion_date=now(),
            final_score=final_score,
            total_hours=total_hours
        )
        
        # 3. Save certificate record
        Certificate.objects.create(
            user_id=user_id,
            course=course,
            pdf_url=pdf_url,
            quiz_score_avg=avg_quiz_score,
            test_score_avg=avg_test_score
        )
        
        return {"download_url": pdf_url}
```

---

### 5. Progress Tracking

Comprehensive tracking of user learning progress.

#### Progress Model

```python
# apps/courses/models.py

class CourseProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    # Completion tracking
    total_days = models.IntegerField(default=0)
    completed_days = models.IntegerField(default=0)
    current_week = models.IntegerField(default=1)
    current_day = models.IntegerField(default=1)
    
    # Performance metrics
    overall_percentage = models.FloatField(default=0.0)
    avg_quiz_score = models.FloatField(default=0.0)
    avg_test_score = models.FloatField(default=0.0)
    
    # Engagement
    total_study_time = models.IntegerField(default=0)  # minutes
    streak_days = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True)
```

#### Knowledge State Tracking

Per-concept confidence scores for adaptive learning:

```python
class UserKnowledgeState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    concept = models.TextField()
    confidence_score = models.FloatField(default=0.0)
    times_practiced = models.IntegerField(default=0)
    last_error = models.TextField(null=True)
```

---

### 6. Security Implementation

#### Security Headers Middleware

```python
# utils/middleware.py

class SecurityHeadersMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Content-Security-Policy"] = "default-src 'self'; ..."
        response["Permissions-Policy"] = "geolocation=(), microphone=(), ..."
        
        return response
```

#### Rate Limiting

Two-tier rate limiting:

1. **Global Rate Limit** - 1000 requests/hour per IP
2. **Auth Rate Limit** - 10 failed auth attempts per minute → 5-minute block

```python
class RateLimitMiddleware:
    def __call__(self, request):
        ip = self._get_client_ip(request)
        
        # Check if blocked
        if cache.get(f"ratelimit:blocked:{ip}"):
            return JsonResponse({"error": "Rate limit exceeded"}, status=429)
        
        # Check request count
        count = cache.get_or_set(f"ratelimit:count:{ip}", 0, timeout=3600)
        if count >= 1000:
            cache.set(f"ratelimit:blocked:{ip}", True, timeout=3600)
            return JsonResponse({"error": "Rate limit exceeded"}, status=429)
        
        cache.incr(f"ratelimit:count:{ip}")
        return self.get_response(request)
```

#### Request Logging

Structured JSON logging for all requests:

```python
class RequestLoggingMiddleware:
    def __call__(self, request):
        log_data = {
            "method": request.method,
            "path": request.path,
            "user_id": str(request.user.id) if request.user.is_authenticated else None,
            "ip": self._get_client_ip(request),
            "status": response.status_code,
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        }
        logger.info("Request: %s", json.dumps(log_data))
```

---

### 7. Async Task Processing (Celery)

Background tasks for long-running operations.

#### Task Queues

| Queue | Purpose |
|-------|---------|
| `course_generation` | Course content generation |
| `quiz_generation` | Weekly test generation |
| `certificates` | Certificate PDF generation |

#### Example Task

```python
# apps/courses/tasks.py

@celery_app.task(bind=True, queue="course_generation")
def generate_course_content_task(self, course_id, topic, weeks, level, goals):
    """
    Celery task for async course generation.
    """
    generator = CourseGenerator()
    
    # Build skeleton
    skeleton = build_skeleton(weeks, topic, level)
    
    # Fill with AI content (async)
    loop = asyncio.get_event_loop()
    filled = loop.run_until_complete(
        generator.fill_skeleton_with_ai_async(skeleton, level, goals, course_id)
    )
    
    # Update course status
    Course.objects.filter(id=course_id).update(
        generation_status="ready",
        generation_progress=100
    )
    
    return {"course_id": course_id, "status": "completed"}
```

---

## Database Schema

### Core Tables

```sql
-- Users
users (
    id UUID PRIMARY KEY,
    clerk_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE,
    name TEXT,
    skill_level VARCHAR(12),
    created_at TIMESTAMP
)

-- Courses
courses (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    course_name VARCHAR(255),
    topic TEXT,
    level VARCHAR(20),
    duration_weeks INT,
    hours_per_day INT,
    goals TEXT[],
    status VARCHAR(20),
    generation_status VARCHAR(20),
    created_at TIMESTAMP
)

-- Week Plans
week_plans (
    id UUID PRIMARY KEY,
    course_id UUID REFERENCES courses,
    week_number INT,
    theme TEXT,
    objectives TEXT[],
    is_completed BOOLEAN,
    test_generated BOOLEAN
)

-- Day Plans
day_plans (
    id UUID PRIMARY KEY,
    week_plan_id UUID REFERENCES week_plans,
    day_number INT,
    title TEXT,
    tasks JSONB,
    theory_content TEXT,
    code_content TEXT,
    quiz_raw TEXT,
    is_completed BOOLEAN,
    is_locked BOOLEAN,
    theory_generated BOOLEAN,
    code_generated BOOLEAN,
    quiz_generated BOOLEAN
)

-- Quiz Questions
quiz_questions (
    id UUID PRIMARY KEY,
    course_id UUID REFERENCES courses,
    day_plan_id UUID REFERENCES day_plans,
    question_text TEXT,
    question_type VARCHAR(15),
    options JSONB,
    correct_answer TEXT,
    explanation TEXT,
    difficulty INT
)

-- Course Progress
course_progress (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    course_id UUID REFERENCES courses,
    completed_days INT,
    current_week INT,
    current_day INT,
    overall_percentage FLOAT,
    avg_quiz_score FLOAT,
    total_study_time INT,
    streak_days INT
)
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/me/` | Get current user profile |
| `PUT` | `/api/users/me/` | Update user profile |
| `POST` | `/api/webhooks/clerk/` | Clerk webhook handler |

### Courses
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/courses/generate/` | Create new course (async) |
| `GET` | `/api/courses/` | List user's courses |
| `GET` | `/api/courses/{id}/` | Get course details |
| `GET` | `/api/courses/{id}/status/` | Get generation status |
| `DELETE` | `/api/courses/{id}/` | Delete course |
| `GET` | `/api/courses/{id}/progress/` | Get learning progress |

### Content
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/` | Get all weeks |
| `GET` | `/api/courses/{id}/weeks/{w}/` | Get week details |
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/` | Get day content |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/complete/` | Mark day complete |

### Quizzes
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/` | Get quiz questions |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/submit/` | Submit answers |

### Certificates
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/certificates/` | List user's certificates |
| `GET` | `/api/courses/{id}/certificate/` | Get course certificate |

---

## Environment Configuration

```bash
# .env.example

# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=learnai
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Clerk Authentication
CLERK_SECRET_KEY=sk_test_xxx
CLERK_JWKS_URL=https://api.clerk.com/v1/jwks
CLERK_WEBHOOK_SECRET=whsec_xxx

# vLLM Server
VLLM_BASE_URL=http://your-vllm-server:8000
VLLM_MODEL=qwen-coder
VLLM_MAX_TOKENS=3000

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS_PER_HOUR=1000

# External APIs
TAVILY_API_KEY=tvly_xxx
JUDGE0_API_URL=https://judge0.example.com
JUDGE0_API_KEY=xxx
```

---

## Running the Project

### Development Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup PostgreSQL with pgvector
createdb learnai
psql -d learnai -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 4. Run migrations
python manage.py migrate

# 5. Start development server
python manage.py runserver

# 6. Start Celery worker (separate terminal)
celery -A config worker -l info --pool=solo -Q course_generation,quiz_generation,certificates
```

### Production Deployment

```bash
# Gunicorn (WSGI)
gunicorn config.wsgi:application -b 0.0.0.0:8000

# Uvicorn (ASGI for WebSockets)
uvicorn config.asgi:application -b 0.0.0.0:8000

# Celery workers
celery -A config worker -l info --pool=solo -Q course_generation
celery -A config worker -l info --pool=solo -Q quiz_generation
celery -A config worker -l info --pool=solo -Q certificates
celery -A config beat -l info  # Periodic tasks
```

---

## Key Design Decisions

### Why Django over FastAPI?

1. **Batteries Included** - Admin panel, ORM, auth, migrations out of the box
2. **Mature Ecosystem** - DRF, Celery, Channels all well-integrated
3. **Team Familiarity** - Faster development with known tools
4. **PostgreSQL Integration** - Native support for JSONB, arrays, pgvector

### Why Clerk for Auth?

1. **Delegated Auth** - No password handling, reduced security surface
2. **JWT-based** - Stateless, scalable across services
3. **Built-in Features** - Social login, MFA, user management UI
4. **Webhooks** - Real-time user sync to our database

### Why vLLM for LLM?

1. **Self-hosted** - Full control, no API costs per token
2. **OpenAI Compatible** - Easy integration with existing SDKs
3. **High Performance** - Optimized inference engine
4. **Model Flexibility** - Can swap models without code changes

### Why Celery for Async Tasks?

1. **Reliability** - Task persistence, retries, error handling
2. **Monitoring** - Flower UI for task inspection
3. **Scalability** - Multiple workers, queue routing
4. **Django Integration** - django-celery-beat for periodic tasks

---

## Future Improvements

1. **Caching Layer** - Redis caching for frequently accessed courses
2. **CDN Integration** - Static assets and certificate PDFs
3. **Monitoring** - Prometheus + Grafana for metrics
4. **Containerization** - Docker + Kubernetes deployment
5. **Testing** - Comprehensive test suite with pytest

---

## License

MIT License
