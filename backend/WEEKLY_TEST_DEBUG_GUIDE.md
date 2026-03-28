# Weekly Test Debug Endpoint - How to Use

## Quick Start

The debug endpoint is now enabled and ready to use!

### Method 1: Using the Python Script (Recommended)

Run the unlock script:

```bash
cd backend
python unlock_weekly_test.py
```

Follow the prompts:
- Enter your Course ID (UUID)
- Enter Week Number (1, 2, 3, etc.)
- Enter your User Email

Example:
```
Enter Course ID (UUID): 550e8400-e29b-41d4-a716-446655440000
Enter Week Number (1, 2, 3, etc.): 1
Enter User Email: your@email.com
```

### Method 2: Using curl

```bash
curl -X POST http://localhost:8000/api/courses/{COURSE_ID}/weeks/{WEEK_NUMBER}/test/unlock/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

### Method 3: Using Postman

1. Create a POST request to: `http://localhost:8000/api/courses/{COURSE_ID}/weeks/{WEEK_NUMBER}/test/unlock/`
2. Add Authorization header with your JWT token
3. Send the request

### Method 4: Using Browser Console

Open your browser console (F12) and run:

```javascript
fetch('/api/courses/YOUR_COURSE_ID/weeks/1/test/unlock/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_JWT_TOKEN',
    'Content-Type': 'application/json'
  }
})
.then(response => response.json())
.then(data => console.log(data))
```

## How to Get Your Course ID

1. Go to your courses page: `http://localhost:3000/dashboard/courses`
2. Click on a course
3. Look at the URL: `http://localhost:3000/dashboard/courses/{COURSE_ID}`
4. The `{COURSE_ID}` is your UUID

## How to Get Your JWT Token

1. Open your browser DevTools (F12)
2. Go to Application tab
3. Local Storage → Your site
4. Find the `__session` or `clerk_session` key
5. Copy the JWT token

## What Happens After Unlocking

1. The weekly test is unlocked immediately
2. If the test doesn't exist, it's created automatically
3. Test questions are generated in the background (Celery task)
4. You can now access the weekly test page

## Verify It Worked

1. Go to: `http://localhost:3000/dashboard/courses/{COURSE_ID}/week/{WEEK_NUMBER}/test`
2. You should see the weekly test questions (not the "not unlocked" error)
3. The test should load successfully

## If Test Questions Don't Appear

The test questions are generated in the background. Wait a few seconds and refresh the page. If questions still don't appear:

1. Check the backend logs for any errors
2. Make sure Celery is running: `celery -A config worker -l info`
3. Try unlocking the test again

## Troubleshooting

### Error: "Not found"
- Check that the course ID is correct
- Check that the week number exists for this course
- Make sure you're logged in as the course owner

### Error: "Weekly test not generated yet"
- Wait a few seconds for the background task to complete
- Refresh the page
- Check Celery is running

### Error: "Unauthorized"
- Make sure you're logged in
- Check your JWT token is valid
- Verify you own the course

## Production Use

**IMPORTANT:** The debug endpoint should only be used in development/testing. In production, users should complete all 5 days to unlock the weekly test naturally.

To disable the debug endpoint in production, remove this line from `urls.py`:
```python
path("<uuid:course_id>/weeks/<int:week_number>/test/unlock/", views_debug.unlock_weekly_test, name="week-test-unlock"),
```
