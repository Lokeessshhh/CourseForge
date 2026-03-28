"""
Production-grade Weekly Test System with Judge0 Integration
================================================================

This document provides a comprehensive overview of the weekly test system
with code execution capabilities using Judge0.

## What's Been Implemented

### 1. Judge0 Integration (Production-Grade)
- **File**: `backend/services/judge0/client.py`
- **Features**:
  - Comprehensive error handling and logging
  - Support for 10+ programming languages (Python, JavaScript, Java, C++, C#, Go, Rust, PHP, Ruby, SQL)
  - Timeout management (30s submission, 60s result wait)
  - Automatic retry logic with configurable max retries
  - Connection pooling for high-performance execution
  - Detailed execution tracking (stdout, stderr, compile output, time, memory)
  - Status mapping (accepted, wrong_answer, time_limit_exceeded, compilation_error, runtime_error, internal_error)

### 2. Coding Test Models
- **File**: `backend/apps/courses/models_coding_test.py`
- **Models**:
  - `CodingTest`: Stores weekly coding challenges with metadata
  - `CodingTestAttempt`: Tracks user attempts with detailed results
  - `CodeExecution`: Records every code execution for debugging and analytics

### 3. Coding Test Views
- **File**: `backend/apps/courses/views_coding_test.py`
- **Endpoints**:
  - `GET /api/courses/{id}/weeks/{w}/coding-test/` - Get coding test challenges
  - `POST /api/courses/{id}/weeks/{w}/coding-test/start/` - Start a test attempt
  - `POST /api/courses/{id}/weeks/{w}/coding-test/execute/` - Execute code with Judge0
  - `POST /api/courses/{id}/weeks/{w}/coding-test/submit/` - Submit test results

### 4. Weekly Test Improvements
- **File**: `backend/apps/courses/views.py`
- **Improvements**:
  - Comprehensive logging for debugging
  - Detailed error messages
  - Performance tracking (strong/weak days)
  - Recommendation generation
  - Week completion tracking

### 5. Frontend Fixes
- **File**: `frontend/app/hooks/api/useLesson.ts`
- **Fixes**:
  - Weekly test submission now uses correct format (letters a/b/c/d instead of indices 0/1/2/3)
  - Matches the QuizSubmitSerializer expectations

## How to Use

### Weekly MCQ Test
1. Complete all 5 days in a week
2. Weekly test unlocks automatically
3. Take the 10-question MCQ test
4. Get detailed results with strong/weak day analysis
5. Pass with 60% to unlock next week

### Weekly Coding Test
1. Complete all 5 days in a week
2. Weekly coding test unlocks automatically
3. Start the coding test attempt
4. Solve 3 coding challenges
5. Submit code for each challenge
6. Get real-time execution results from Judge0
7. Pass with 60% to unlock next week

## Configuration

### Judge0 API Setup
Add to `backend/.env`:
```
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=your_rapidapi_key_here
JUDGE0_API_HOST=judge0-ce.p.rapidapi.com
```

Get API key from: https://rapidapi.com/judge0-ce-judge0-ce-judge0-ce-default/api/judge0-ce

### Database Migrations
Run migrations to create new tables:
```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

## Production-Grade Features

### Error Handling
- Comprehensive try-catch blocks
- Detailed error logging
- User-friendly error messages
- Graceful degradation when Judge0 unavailable

### Logging
- Request/response logging
- Execution tracking
- Performance metrics
- Error alerts

### Security
- Authentication required for all endpoints
- User isolation (users can only access their own data)
- Input validation
- SQL injection protection

### Performance
- Connection pooling
- Async execution
- Caching where appropriate
- Optimized database queries

### Monitoring
- Execution time tracking
- Memory usage monitoring
- Success/failure rates
- User activity logging

## Testing

### Test Weekly MCQ Test
1. Create a course
2. Complete all 5 days in week 1
3. Take the weekly MCQ test
4. Verify results and progress updates

### Test Weekly Coding Test
1. Create a course
2. Complete all 5 days in week 1
3. Take the weekly coding test
4. Submit code for challenges
5. Verify execution results
6. Check progress updates

## API Endpoints

### Weekly MCQ Test
- `GET /api/courses/{id}/weeks/{w}/test/` - Get test questions
- `POST /api/courses/{id}/weeks/{w}/test/submit/` - Submit answers

### Weekly Coding Test
- `GET /api/courses/{id}/weeks/{w}/coding-test/` - Get coding challenges
- `POST /api/courses/{id}/weeks/{w}/coding-test/start/` - Start attempt
- `POST /api/courses/{id}/weeks/{w}/coding-test/execute/` - Execute code
- `POST /api/courses/{id}/weeks/{w}/coding-test/submit/` - Submit results

## Response Formats

### Weekly MCQ Test Submit
```json
{
  "success": true,
  "data": {
    "score": 7,
    "total": 10,
    "percentage": 70.0,
    "passed": true,
    "next_week_unlocked": true,
    "results": [...],
    "week_summary": {
      "strong_days": [1, 2, 3],
      "weak_days": [4],
      "recommendation": "Review Day 4 content before moving on"
    }
  }
}
```

### Coding Test Execute
```json
{
  "success": true,
  "data": {
    "execution_id": "uuid",
    "status": "accepted",
    "stdout": "42",
    "stderr": "",
    "compile_output": "",
    "execution_time": 0.123,
    "memory_used": 2048,
    "is_correct": true
  }
}
```

## Supported Languages

- Python (3)
- JavaScript (Node.js)
- Java
- C++ (GCC 9.4.0)
- C (GCC 9.4.0)
- C# (Mono 6.12.0)
- Go (1.18.5)
- Rust (1.73.0)
- PHP (8.2.8)
- Ruby (3.2.2)
- SQL (SQLite 3)

## Next Steps

1. Run database migrations
2. Configure Judge0 API key
3. Test weekly MCQ test functionality
4. Test weekly coding test functionality
5. Monitor logs for any issues
6. Scale Judge0 API usage as needed
