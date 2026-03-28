
# Bugs and Production-Readiness Audit

This file is a living checklist of issues and gaps that should be addressed to make the project production-grade.

Format conventions:

- **Severity**: `P0` (must-fix before prod), `P1` (high), `P2` (medium), `P3` (low)
- **Area**: Backend / Frontend / Infra / Security / Observability
- **Where**: file(s) and/or module(s)
- **Fix**: what to change / what “done” means

## P0 (Must-fix before production)

### Backend

1. **Runtime defaults to development settings**
   - **Area**: Backend / Infra
   - **Where**:
     - `backend/config/asgi.py` (`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")`)
     - `backend/config/wsgi.py` (same)
     - `backend/config/celery.py` (same)
     - `backend/manage.py` (same)
   - **Why it matters**: production deployments can accidentally run with dev settings (debug/CORS/SSL/rate limits/etc.).
   - **Fix**: set default to `config.settings.production` *or* require `DJANGO_SETTINGS_MODULE` to be set explicitly and fail fast if missing.

2. **Clerk webhook verification appears incompatible with Svix signature format**
   - **Area**: Backend / Security
   - **Where**: `backend/services/auth/clerk.py` (`verify_clerk_webhook`)
   - **Why it matters**: webhook verification may fail (or be implemented incorrectly), blocking user sync and creating security risk.
   - **Fix**: use the `svix` library’s verifier (recommended) or implement Svix signature verification exactly (base64 signature, correct signing string, constant-time compare). Add tests with known good vectors.

3. **Secret-key fallback is unsafe**
   - **Area**: Backend / Security
   - **Where**: `backend/config/settings/base.py` (`SECRET_KEY = ... "change-me-in-production"`)
   - **Why it matters**: a misconfigured production environment could run with a known secret.
   - **Fix**: in `production.py` enforce `DJANGO_SECRET_KEY` presence (raise exception if empty/placeholder).

4. **Production `ALLOWED_HOSTS` fallback may hide misconfiguration**
   - **Area**: Backend / Security
   - **Where**: `backend/config/settings/production.py` defaults to `localhost` when env is missing.
   - **Fix**: require `ALLOWED_HOSTS` in production (fail fast if missing).

5. **Security headers middleware CSP likely breaks split-origin deployments**
   - **Area**: Backend / Security
   - **Where**: `backend/utils/middleware.py` (`Content-Security-Policy`, `connect-src 'self'`)
   - **Why it matters**: if frontend is hosted on a different origin, API/WebSocket calls may be blocked.
   - **Fix**: make CSP configurable per environment (allow frontend origin + WS origin) and avoid overly strict defaults.

6. **WebSocket auth token passed via query string**
   - **Area**: Backend / Security
   - **Where**:
     - `backend/apps/websockets/routing.py` (documents `?token=<jwt>`)
     - `backend/services/auth/clerk.py` (`ClerkWebSocketMiddleware` parses query)
   - **Why it matters**: query-string tokens can leak via logs, proxies, referers, and browser history.
   - **Fix**: prefer `Sec-WebSocket-Protocol` or a short-lived one-time WS auth ticket fetched over HTTPS.

### Frontend

7. **Clerk token retrieval is likely incorrect for Next.js App Router**
   - **Area**: Frontend / Auth
   - **Where**: `frontend/app/lib/api.ts` imports `getToken` from `@clerk/nextjs`
   - **Why it matters**: token retrieval differs by server/client context in App Router; wrong usage can silently produce unauthenticated API calls.
   - **Fix**:
     - For **server** calls: use `auth()` from `@clerk/nextjs/server`.
     - For **client** calls: use `useAuth()` and its `getToken()`.
     - Split `api` utilities into server-only and client-only modules.

8. **No environment validation for frontend public URLs**
   - **Area**: Frontend / Reliability
   - **Where**: `frontend/app/lib/api.ts` defaults to `http://localhost:8000` and `ws://localhost:8000`
   - **Why it matters**: production build may run but call localhost at runtime.
   - **Fix**: validate `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` at startup/build (fail build if missing in production).

## P1 (High priority)

### Backend

1. **Production logging path is hardcoded to Linux**
   - **Area**: Backend / Observability
   - **Where**: `backend/config/settings/production.py` uses `LOG_DIR = "/var/log/learnai"` and `os.makedirs(...)`.
   - **Why it matters**: can crash at import-time (especially on Windows or restricted containers).
   - **Fix**: make log directory configurable via env; avoid failing during settings import.

2. **Duplicate import**
   - **Area**: Backend / Maintainability
   - **Where**: `backend/services/auth/clerk.py` imports `database_sync_to_async` twice.
   - **Fix**: remove duplication; add linting in CI.

3. **Health check can become slow/noisy**
   - **Area**: Backend / Reliability
   - **Where**: `backend/config/urls.py` health check pings vLLM and inspects celery.
   - **Fix**: split liveness vs readiness; make external checks optional/time-bounded; reduce celery inspection overhead.

4. **CORS policy enforcement gaps**
   - **Area**: Backend / Security
   - **Where**:
     - `backend/config/settings/development.py` sets `CORS_ALLOW_ALL_ORIGINS=True`
     - `backend/config/settings/production.py` expects `CORS_EXTRA_ORIGINS`
   - **Fix**: in production, enforce non-empty `CORS_ALLOWED_ORIGINS` and document required env vars.

### Frontend

5. **Missing `next.config.js` production hardening**
   - **Area**: Frontend / Performance / Security
   - **Where**: `frontend/next.config.js` is empty.
   - **Fix** (typical):
     - set `output: 'standalone'` for Docker deployment
     - set `poweredByHeader: false`
     - configure `headers()` for security headers (or do it at proxy)
     - configure `images` domains if using `next/image`

6. **WebSocket client implementation is not discoverable**
   - **Area**: Frontend / Functionality
   - **Where**: backend has `backend/apps/websockets/*`, but frontend search did not find any `WebSocket(...)` usage.
   - **Fix**: ensure there is a single WS client module with:
     - reconnection/backoff
     - heartbeat/ping
     - message schema matching backend
     - auth strategy compatible with backend

## P2 (Medium priority)

### Backend

1. **All API errors are logged at `error` level**
   - **Area**: Backend / Observability
   - **Where**: `backend/utils/exceptions.py`
   - **Why it matters**: 4xx client errors can overwhelm error logs.
   - **Fix**: log 4xx at `warning/info`; 5xx at `error`; add request ID / correlation IDs.

2. **Rate limiting is duplicated (middleware + DRF throttling)**
   - **Area**: Backend / Reliability
   - **Where**:
     - `backend/utils/middleware.py` (`RateLimitMiddleware`)
     - `backend/config/settings/production.py` (`DEFAULT_THROTTLE_CLASSES`)
   - **Fix**: choose one canonical strategy; document and tune.

3. **CSP includes `'unsafe-inline'`**
   - **Area**: Backend / Security
   - **Where**: `backend/utils/middleware.py`
   - **Fix**: remove `'unsafe-inline'` (or gate behind development); adopt nonces/hashes if needed.

### Frontend

4. **API client has no explicit timeouts**
   - **Area**: Frontend / Reliability
   - **Where**: `frontend/app/lib/api.ts` uses `fetch` without `AbortController`.
   - **Fix**: add request timeouts and optional retries for idempotent calls.

## P3 (Low priority / quality)

1. **Standardize API response contracts**
   - **Area**: Backend + Frontend
   - **Where**:
     - backend error envelope: `backend/utils/exceptions.py`
     - frontend unwrapping: `frontend/app/lib/api.ts`
   - **Fix**: decide envelope strategy for success+error responses; document; ensure consistency across endpoints.

2. **Add CI quality gates**
   - **Area**: Infra / Quality
   - **Where**: Repo-wide
   - **Fix**: backend lint+tests (ruff/pytest), frontend lint+typecheck (eslint/tsc), run on PRs.

---

## Notes on previously listed issues

The older `BUGS_FOUND.md` list included items such as “DayPlan content mismatch”, “missing serializers/imports”, and “subprocess security issue”. In this audit pass, I could not confirm those via repo-wide search (they may have been fixed already, renamed, or located under different paths). If you point me to the exact modules/paths, I can re-verify and re-add them with precise file references.

