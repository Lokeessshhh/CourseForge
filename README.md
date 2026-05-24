# 🚀 CourseForge — AI-Powered Course Generation Platform

> Generate complete, production-ready coding courses from a single topic name — powered by LLMs, RAG, and real-time streaming.

CourseForge is a full-stack AI platform that creates personalized multi-week coding courses on demand. Type a topic (e.g., "Java Spring Boot", "Machine Learning with Python") and CourseForge generates a complete course with daily lessons, theory content, code examples, MCQs, coding tests, progress tracking, and PDF certificates — all AI-generated in parallel.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **AI Course Generation** | Create full courses (1–12+ weeks) from a topic name. Parallel week generation with 21+ LLM calls per week. |
| **Course Updates** | Update existing courses by percentage (50%/75%), extend (add weeks), or compact (compress content). |
| **Daily Lessons** | Each day includes theory (with Mermaid diagrams), code examples, and 3 MCQ quizzes. |
| **Weekly Tests** | 10 MCQs per week with 3 parallel LLM batches. 60% pass required to advance. |
| **Coding Tests** | 2 coding problems per week, auto-graded via Judge0 CE. |
| **Certificate System** | PDF certificate on course completion (100% days done + 50% avg quiz score). |
| **RAG-Powered AI Tutor** | Real-time chat with context-aware answers using hybrid retrieval (Vector + BM25 + RRF) + Cohere reranking. |
| **4-Tier Memory System** | Session, course, user, and global memory for personalized tutoring. |
| **Progress Tracking** | Dashboard with charts, streak calendar, daily activity tracking, and detailed metrics. |
| **Web Search Integration** | Tavily-powered real-time web search for up-to-date course content. |
| **Mobile Responsive** | Fully responsive design across all devices. |
| **Mini Games** | Memory, Reaction, Math, Number Guess, ClickSpeed games embedded in the dashboard. |
| **SSE Real-Time Progress** | Server-Sent Events for live generation progress updates. |
| **Enterprise Security** | Clerk JWT auth, Redis-cached JWKS, rate limiting, CSP headers, webhook verification. |

---

## 🧱 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | ![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js) ![React](https://img.shields.io/badge/React-19-blue?logo=react) ![TypeScript](https://img.shields.io/badge/TypeScript-5-blue?logo=typescript) |
| **Backend** | ![Django](https://img.shields.io/badge/Django-4.2-green?logo=django) ![DRF](https://img.shields.io/badge/DRF-3.14-red) ![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python) |
| **ASGI / WebSocket** | ![Daphne](https://img.shields.io/badge/Daphne-ASGI-purple) ![Channels](https://img.shields.io/badge/Channels-4.x-green) |
| **Database** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql) ![pgvector](https://img.shields.io/badge/pgvector-✓-blue) |
| **Vector DB** | ![Zilliz](https://img.shields.io/badge/Zilliz-Cloud-purple) (Milvus) |
| **Cache** | ![Redis](https://img.shields.io/badge/Upstash-Redis-red?logo=redis) |
| **LLM** | ![OpenRouter](https://img.shields.io/badge/OpenRouter-Qwen-orange) (Qwen 7B/9B) |
| **Embeddings** | Qwen3-Embedding-8B via OpenRouter |
| **Reranker** | Cohere Rerank v3.5 (free via OpenRouter) |
| **Web Search** | ![Tavily](https://img.shields.io/badge/Tavily-Search-blue) |
| **Code Execution** | ![Judge0](https://img.shields.io/badge/Judge0-CE-orange) |
| **Certificates** | WeasyPrint (PDF) |
| **Auth** | ![Clerk](https://img.shields.io/badge/Clerk-Auth-purple?logo=clerk) |
| **Background Tasks** | Python threading (replaced Celery) |
| **Deployment** | ![Docker](https://img.shields.io/badge/Docker-✓-blue?logo=docker) ![Nginx](https://img.shields.io/badge/Nginx-Proxy-green?logo=nginx) ![ngrok](https://img.shields.io/badge/ngrok-Tunnel-pink) |

---

## 🏗️ Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Next.js │◄───►│  Nginx   │◄───►│  Daphne  │
│  (React) │     │  Proxy   │     │  (ASGI)  │
└──────────┘     └──────────┘     └────┬─────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
             ┌──────────┐      ┌──────────┐      ┌──────────┐
             │ Django   │      │ Channels │      │ Thread   │
             │ REST API │      │ WebSocket│      │ Workers  │
             └────┬─────┘      └──────────┘      └──────────┘
                  │
    ┌─────────────┼──────────────┐
    ▼             ▼              ▼
┌──────┐   ┌──────────┐   ┌──────────┐
│Neon  │   │ Upstash  │   │ Zilliz   │
│PG    │   │ Redis    │   │ Cloud    │
│+vec  │   │(Cache+WS)│   │(Vector)  │
└──────┘   └──────────┘   └──────────┘

External APIs:
  - OpenRouter  → LLM, Embeddings, Reranker
  - Tavily      → Web Search
  - Judge0      → Code Execution
  - Clerk       → Authentication
  - SendGrid    → Email
```

### Data Flow — Course Generation

1. User enters course name / duration / level on frontend
2. `POST /api/courses/generate/` returns `202 Accepted` with course ID
3. Background thread creates DB skeleton (weeks/days + progress record)
4. `generate_course_content_task` runs all weeks in parallel via `asyncio.gather`
5. Each week: 1 LLM call for theme → 1 call for 5 day titles → per day: theory + code + quiz (4 calls/day = ~20 calls/week)
6. Each day saved to DB immediately upon completion
7. SSE stream pushes real-time progress to frontend
8. Frontend polls `/api/courses/{id}/generation-progress/` for independent progress bars

### RAG Chat Pipeline

1. User sends message via WebSocket
2. Semantic cache check (Redis exact + pgvector similarity > 0.97)
3. Load user context (course progress, knowledge state)
4. Inject 4-tier memory (session / course / user / global)
5. Query decomposition + HyDE embedding generation
6. Hybrid retrieval: Zilliz dense search + PostgreSQL BM25
7. RRF score fusion → top 60
8. Cohere Rerank v3.5 → top 10
9. Build prompt with context + memory + sources
10. Stream LLM response via OpenRouter
11. Save to conversation history + update memory

---

## 📁 Project Structure

```
COURSEFORGE/
├── backend/                          # Django REST API
│   ├── config/                       # Django project configuration
│   │   ├── settings/
│   │   │   ├── base.py              # Base settings (shared)
│   │   │   ├── development.py       # Dev settings (debug, no rate limits)
│   │   │   └── production.py        # Production settings (hardened)
│   │   ├── urls.py                  # Root URL routing + health checks
│   │   ├── asgi.py                  # ASGI (Daphne + Channels)
│   │   └── wsgi.py                  # WSGI entry point
│   ├── apps/                        # Django applications
│   │   ├── users/                   # User model, Clerk auth, webhooks
│   │   ├── courses/                 # Course/Week/Day models, generation, SSE
│   │   ├── rag/                     # RAG document & chunk models
│   │   ├── conversations/           # Chat history with embeddings
│   │   ├── quizzes/                 # Quiz questions & attempts
│   │   ├── certificates/            # Certificate models & generation
│   │   ├── cache/                   # Semantic query cache
│   │   ├── chat/                    # Chat course management
│   │   ├── admin_api/               # Admin endpoints
│   │   └── websockets/              # WebSocket consumers & routing
│   ├── services/                    # Business logic
│   │   ├── auth/                    # Clerk JWT + webhook verification
│   │   ├── llm/                     # OpenRouter client, embeddings
│   │   ├── course/                  # Course generator (~1400 lines)
│   │   ├── chat/                    # Chat pipeline (12 files)
│   │   ├── rag_pipeline/            # Retriever, reranker, HyDE, RAPTOR
│   │   ├── external/                # Judge0, Tavily, WeasyPrint
│   │   ├── progress/                # Progress tracking service
│   │   ├── indexing/                # Document indexing service
│   │   ├── certificate/             # Certificate generation service
│   │   ├── judge0/                  # Code execution service
│   │   └── web_search/              # Web search service
│   ├── utils/                       # Middleware, exceptions, streaming
│   ├── websockets/                  # WebSocket consumers
│   ├── manage.py                    # Django CLI
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Backend Docker image
│   ├── Procfile                     # Heroku process definition
│   └── .env.example                 # Environment template (108 vars)
│
├── frontend/                        # Next.js 15 Application
│   ├── app/                         # App Router pages
│   │   ├── page.tsx                 # Landing page (14 components)
│   │   ├── layout.tsx               # Root layout (Clerk + providers)
│   │   ├── middleware.ts            # Clerk auth middleware
│   │   ├── dashboard/               # Dashboard (courses, progress, chat)
│   │   │   ├── page.tsx             # Main dashboard (~1259 lines)
│   │   │   ├── courses/             # Course detail pages
│   │   │   ├── generate/            # Course generation pages
│   │   │   ├── progress/            # Progress tracking pages
│   │   │   ├── chat/                # AI tutor chat interface
│   │   │   ├── certificates/        # Certificate pages
│   │   │   └── settings/            # Settings pages
│   │   ├── sign-in/                 # Authentication pages
│   │   ├── sign-up/
│   │   ├── sso-callback/
│   │   └── verify/
│   ├── components/                  # React components (36+)
│   │   ├── auth/                    # Auth-related components
│   │   ├── chat/                    # Chat interface components
│   │   ├── dashboard/               # Dashboard components
│   │   ├── GenerateCourseModal/     # Course generation modal
│   │   ├── GeneratingCourseCard/    # Generation progress card
│   │   ├── GenerationProgressProvider/
│   │   ├── GenerationProgressToast/ # Real-time toast notifications
│   │   ├── CoursePreview/           # Course preview component
│   │   ├── CourseUpdateModal/       # Course update modal
│   │   ├── MermaidRenderer.tsx      # Mermaid diagram renderer
│   │   ├── MiniGames.tsx            # 5 embedded mini games
│   │   ├── WebcamASCII.tsx          # Webcam-to-ASCII art
│   │   ├── Navbar/                  # Navigation bar
│   │   ├── Hero/                    # Landing page hero
│   │   ├── HowItWorks/              # How it works section
│   │   ├── FeaturesGrid/            # Features grid
│   │   ├── Testimonials/            # Testimonials carousel
│   │   ├── Stats/                   # Statistics counter
│   │   ├── FAQ/                     # FAQ accordion
│   │   ├── CTA/                     # Call to action
│   │   ├── Footer/                  # Footer
│   │   ├── StickyNav/               # Sticky navigation
│   │   ├── Cursor/                  # Custom cursor
│   │   ├── LoadingScreen/           # Loading animations
│   │   ├── EasterEgg/               # Easter egg effects
│   │   ├── PageTransition/          # Page transitions
│   │   ├── ErrorBoundary/           # Error boundary
│   │   ├── Skeleton/                # Skeleton loaders
│   │   ├── Toast/                   # Toast notifications
│   │   └── Marquee/                 # Marquee scroll
│   ├── hooks/                       # React hooks (18)
│   │   ├── api/                     # API hooks
│   │   ├── dashboard/               # Dashboard hooks
│   │   ├── useApiClient.ts
│   │   ├── useChatStorage.ts
│   │   ├── useCountUp.ts
│   │   ├── useScrambleText.ts
│   │   └── ...
│   ├── lib/                         # Client libraries
│   │   ├── api.ts                   # API client (74 lines)
│   │   └── env.ts                   # Environment validation
│   ├── context/                     # React context providers
│   │   └── GenerationProgressContext.tsx
│   ├── public/                      # Static assets
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   └── Dockerfile                   # Frontend Docker image
│
├── docker/                          # Docker infrastructure
│   └── nginx/
│       ├── default.conf             # Nginx reverse proxy config
│       └── Dockerfile               # Nginx Docker image
├── docker-compose.yml               # Multi-service deployment
├── .github/workflows/               # CI/CD (Qwen code review)
│   ├── qwen-dispatch.yml
│   ├── qwen-invoke.yml
│   ├── qwen-review.yml
│   ├── qwen-scheduled-triage.yml
│   └── qwen-triage.yml
├── Research Papers/                  # Reference AI research (PDFs)
├── .gitignore
└── README.md
```

---

## 🚦 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ with pgvector extension
- Redis 7+
- (Optional) Docker + Docker Compose

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see below)

# Setup database
createdb courseforge
psql -d courseforge -c "CREATE EXTENSION IF NOT EXISTS vector;"
python manage.py migrate

# Start development server
python manage.py runserver

# Start Daphne for WebSockets (separate terminal)
daphne -b 0.0.0.0 -p 8001 config.asgi:application

# Start background worker for course generation
python start_dev.py
```

### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with your Clerk publishable key + API URL

# Start development server
npm run dev
```

### Docker Deployment

```bash
# Build and run all services
docker-compose up --build

# Services:
#   - Frontend  : http://localhost:3000
#   - Backend   : http://localhost:8000
#   - Nginx     : http://localhost:80
#   - ngrok     : https://<random>.ngrok.io
```

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `REDIS_URL` | Upstash Redis connection string |
| `CLERK_SECRET_KEY` | Clerk API secret |
| `CLERK_JWKS_URL` | Clerk JWKS endpoint |
| `CLERK_WEBHOOK_SECRET` | Clerk webhook signing secret |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `TAVILY_API_KEY` | Tavily search API key |
| `JUDGE0_API_KEY` | Judge0 code execution key |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key (frontend) |
| `NEXT_PUBLIC_API_URL` | Backend API URL (frontend) |

---

## 📡 API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health/` | System health (DB, Redis, LLM) |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/me/` | Get current user profile |
| `PUT` | `/api/users/me/` | Update user profile |
| `GET` | `/api/users/me/knowledge-state/` | Get knowledge states |
| `GET` | `/api/users/me/quiz-history/` | Get quiz history |
| `POST` | `/api/webhooks/clerk/` | Clerk webhook handler |

### Courses
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/courses/generate/` | Generate a new course (returns `202`) |
| `GET` | `/api/courses/` | List user's courses |
| `GET` | `/api/courses/{id}/` | Get course details |
| `GET` | `/api/courses/{id}/status/` | Get generation status |
| `DELETE` | `/api/courses/{id}/` | Delete a course |
| `POST` | `/api/courses/{id}/update/` | Update course (percentage/extend/compact) |
| `POST` | `/api/courses/{id}/update-preview/` | Preview update changes |
| `GET` | `/api/courses/{id}/progress/` | Get detailed progress |
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/` | Get day content |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/complete/` | Mark day complete |
| `GET` | `/api/courses/{id}/generation-progress/` | SSE generation progress |

### Weekly Tests
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/{w}/test/` | Get weekly test (10 MCQs) |
| `POST` | `/api/courses/{id}/weeks/{w}/test/submit/` | Submit test answers |
| `GET` | `/api/courses/{id}/weeks/{w}/test/results/` | Get test results |

### Coding Tests
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/{w}/coding-test/` | Get coding problems |
| `POST` | `/api/courses/{id}/weeks/{w}/coding-test/run/` | Run code (Judge0) |
| `POST` | `/api/courses/{id}/weeks/{w}/coding-test/submit/` | Submit coding test |

### Daily Quizzes
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/` | Get quiz (3 MCQs) |
| `POST` | `/api/courses/{id}/weeks/{w}/days/{d}/quiz/submit/` | Submit quiz |

### Certificates
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/certificates/` | List user's certificates |
| `POST` | `/api/courses/{id}/certificate/generate/` | Generate certificate |
| `GET` | `/api/courses/{id}/certificate/` | Download certificate PDF |

### RAG Documents
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
| `GET` | `/api/conversations/{id}/` | Get messages |
| `DELETE` | `/api/conversations/{id}/` | Delete conversation |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://<host>/ws/chat/{session_id}/?token=<jwt>` | Real-time AI tutor chat |

> Full interactive API docs available at `/api/docs/` (Swagger UI) when running the development server.

---

## 🔒 Security

- **Clerk JWT Authentication** — JWTs validated against Clerk's JWKS endpoint with Redis-cached keys (1-hour TTL)
- **Webhook Verification** — Svix HMAC-SHA256 signature validation with replay attack prevention (5-min window)
- **Rate Limiting** — 1000 requests/hour/IP (configurable), 10 auth failures/min → 5-min block
- **Security Headers** — CSP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy
- **Strict CORS** — Origin whitelist in production
- **Ownership Checks** — All resources scoped to authenticated user; returns 404 on unauthorized access (prevents enumeration)
- **Structured Errors** — Consistent `{success, error, code, details}` format; no internal details exposed
- **Input Validation** — Rigorous DRF serializer validation across all endpoints

---

## 🛡️ RAG Pipeline

```
User Query
    │
    ▼
┌─────────────────────┐
│ Semantic Cache      │── Redis exact + pgvector similarity (>0.97)
└─────────┬───────────┘
          │ (miss)
          ▼
┌─────────────────────┐
│ Query Decomposition │── LLM splits complex queries into sub-queries
└─────────┬───────────┘
          │
┌─────────────────────┐
│ HyDE                │── LLM generates hypothetical answer embedding
└─────────┬───────────┘
          │
┌─────────────────────┐
│ Hybrid Retrieval    │── Zilliz (dense) + PostgreSQL BM25 (sparse)
└─────────┬───────────┘
          │
┌─────────────────────┐
│ RRF Fusion          │── Reciprocal Rank Fusion → top 60
└─────────┬───────────┘
          │
┌─────────────────────┐
│ Cohere Rerank       │── Cross-encoder reranking → top 10
└─────────┬───────────┘
          │
┌─────────────────────┐
│ Memory Injection    │── 4-tier: session, course, user, global
└─────────┬───────────┘
          │
┌─────────────────────┐
│ LLM Generation      │── Prompt with context + memory + sources
└─────────┬───────────┘
          │
          ▼
    Response Stream (WebSocket)
```

---

## 🧪 Development

### Backend

```bash
# Run tests
python manage.py test

# Format code
pip install ruff black isort
black .
isort .

# Lint
ruff check .

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### Frontend

```bash
# Lint
npm run lint

# Build
npm run build

# TypeScript check
npx tsc --noEmit
```

---

## 🐳 Docker Deployment

```yaml
# docker-compose.yml defines 4 services:
services:
  backend:    # Django + Daphne (ASGI)
  frontend:   # Next.js (Node)
  nginx:      # Reverse proxy
  ngrok:      # Public tunnel (dev only)
```

```bash
docker-compose up --build
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📧 Contact

Project Link: [https://github.com/roshaanmehmood/CourseForge](https://github.com/roshaanmehmood/CourseForge)
