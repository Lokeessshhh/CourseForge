# Code Content Parsing Implementation - April 11, 2026

## Problem Solved

The AI-generated code section was stored as raw markdown text without any structure, making it:
- Hard to distinguish between multiple examples
- Difficult to navigate between code, explanations, and outputs
- No proper separation of examples, explanations, and practice exercises

## Solution Implemented

### **Backend Parser** (`backend/services/course/code_parser.py`)

Production-grade parser that extracts structured components from LLM-generated markdown:

#### **Input Format (from LLM):**
```markdown
## Example 1: Basic Variable Assignment

Description text here...

```python
age = 25
height = 5.9
print("Age:", age)
```

**Explanation:**
- point 1
- point 2

**Output:**
```
Age: 25
Height: 5.9
```

**Common Mistakes:**
- mistake 1

## Example 2: ...
```

#### **Output Format (Structured JSON):**
```json
{
  "examples": [
    {
      "title": "Example: Basic Variable Assignment",
      "description": "Description text here...",
      "code": "age = 25\nheight = 5.9...",
      "language": "python",
      "explanation": ["point 1", "point 2"],
      "output": "Age: 25\nHeight: 5.9",
      "common_mistakes": ["mistake 1"]
    }
  ],
  "practice_exercise": {
    "description": "Practice exercise description...",
    "expected_output": "Expected output here...",
    "hints": ["hint 1"]
  }
}
```

### **Integration in Tasks** (`backend/apps/courses/tasks.py`)

Parser called right before saving code content to DB:

```python
# Parse code content into structured format before saving
structured_code = {}
try:
    from services.course.code_parser import parse_code_content
    structured_code = parse_code_content(code)
    # Store structured JSON in code_content field
    day.code_content = json.dumps(structured_code, indent=2)
    logger.info("[CODE_PARSER] Week %d Day %d: Parsed %d examples",
               week_number, day_num, len(structured_code.get("examples", [])))
except Exception as parse_err:
    # Fallback: store raw content if parsing fails
    logger.warning("[CODE_PARSER] Week %d Day %d: Parsing failed, storing raw: %s",
                  week_number, day_num, parse_err)
    day.code_content = code
```

### **Frontend Rendering** (`frontend/app/dashboard/courses/[id]/week/[w]/day/[d]/page.tsx`)

Updated to detect and render structured content:

1. **Detection**: Tries to parse `code_content` as JSON
2. **Structured Rendering**: If JSON with examples, renders each example with:
   - Title card
   - Description
   - Code editor with language label
   - Run button
   - Output section
   - Explanation list
   - Common mistakes list
3. **Practice Exercise**: Renders at the bottom with:
   - Description
   - Expected output
   - Hints
   - Practice editor
4. **Fallback**: If not structured JSON, renders raw content as before

### **Styling** (`frontend/app/dashboard/courses/[id]/week/[w]/day/[d]/page.module.css`)

Added CSS for:
- `.structuredCodeSection` - Container for all examples
- `.exampleCard` - Card for each example with border and shadow
- `.exampleTitle` - Bold heading for each example
- `.exampleDescription` - Gray description text
- `.explanationSection` - Bullet point explanations
- `.mistakesSection` - Warning-colored common mistakes
- `.expectedOutput` - Gray box with expected output
- `.hints` - Hint list with lightbulb icons

## Error Handling

### **Parser Level:**
- Empty content → Returns empty result structure
- No examples found → Creates single example with all content
- Malformed markdown → Best-effort parsing
- Any exception → Returns raw content as single example

### **Integration Level:**
- Parser import failure → Falls back to raw content
- JSON parsing error → Falls back to raw content
- Missing fields → Gracefully handles undefined/null

### **Frontend Level:**
- Invalid JSON → Renders as raw markdown
- Missing examples → Shows fallback editor
- Missing practice exercise → Shows generic practice prompt

## Benefits

1. **Better UX**: Examples are clearly separated and easy to navigate
2. **Code Focus**: Each example has its own code editor with run button
3. **Learning Support**: Explanations and common mistakes are prominently displayed
4. **Practice Integration**: Practice exercises include expected output and hints
5. **Backward Compatible**: Raw content still works if parsing fails
6. **Production Ready**: Comprehensive error handling at every level

## Testing

1. Create a new course
2. Navigate to any day's code tab
3. Verify examples are rendered as structured cards
4. Verify code is editable in editor
5. Verify run button works
6. Verify explanations and mistakes are displayed
7. Verify practice exercise shows expected output and hints
