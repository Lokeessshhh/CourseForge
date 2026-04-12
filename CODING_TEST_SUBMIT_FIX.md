# Coding Test Submit 0% Fix

## Problem
When running coding tests, the execute endpoint worked correctly and showed "accepted" status, but when submitting the test, it showed 0% score.

## Root Cause
The **execute endpoint** (`execute_coding_challenge`) was **not saving execution results** to the `CodingTestAttempt` model's `submissions` field. It only returned the results to the frontend.

When the frontend called the **submit endpoint**, it sent the `challenge_results` collected from frontend state. However:
1. The backend had no record of what was executed
2. If there was any mismatch or missing data, the score calculation would fail
3. The backend should be the source of truth for execution results, not the frontend

## Solution

### 1. Execute Endpoint Fix (`views_coding_test.py` lines ~203-218)
Added code to **save each execution result** to the attempt's `submissions` field:

```python
# Save execution result to attempt's submissions
if not attempt.submissions:
    attempt.submissions = {}

# Store result for this challenge index
attempt.submissions[str(challenge_index)] = {
    "problem_index": challenge_index,
    "is_correct": is_correct,
    "stdout": result.get("stdout", ""),
    "stderr": result.get("stderr", ""),
    "compile_output": result.get("compile_output", ""),
    "status": result.get("status"),
    "execution_time": result.get("time"),
    "memory_used": result.get("memory"),
}
attempt.save(update_fields=["submissions"])
```

### 2. Submit Endpoint Enhancement (`views_coding_test.py` lines ~269-282)
Added logic to **use backend-stored submissions** as the source of truth:

```python
# If challenge_results is empty or incomplete, use the saved submissions from attempt
if not challenge_results and attempt.submissions:
    # Convert dict back to list format
    challenge_results = []
    for key in sorted(attempt.submissions.keys(), key=lambda x: int(x)):
        challenge_results.append(attempt.submissions[key])
    logger.info(f"Submit coding test: Using saved submissions from attempt, count={len(challenge_results)}")
elif challenge_results and attempt.submissions:
    # Use backend submissions as source of truth
    logger.info(f"Submit coding test: Received {len(challenge_results)} results from frontend, using backend-stored results")
    challenge_results = []
    for key in sorted(attempt.submissions.keys(), key=lambda x: int(x)):
        challenge_results.append(attempt.submissions[key])
```

## Benefits
1. **Execution results are now persisted** to the database immediately after each run
2. **Backend is the source of truth** for execution results, preventing frontend/backend mismatches
3. **Submit endpoint is more robust** - it uses backend-stored results even if frontend sends incomplete data
4. **Better logging** - tracks when saved submissions are used vs frontend submissions
5. **Tick/success indicators will now display correctly** because the score calculation uses authoritative backend data

## Testing
After restarting the backend server:
1. Start a coding test attempt
2. Execute code for each problem (results are now saved to DB)
3. Submit the test
4. You should now see the correct score with tick marks for passed problems

## Files Changed
- `backend/apps/courses/views_coding_test.py`
  - `execute_coding_challenge()` function: Added submission saving logic
  - `submit_coding_test()` function: Added backend submission priority logic
