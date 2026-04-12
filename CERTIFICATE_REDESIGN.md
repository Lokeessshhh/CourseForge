# Certificate Redesign - April 11, 2026

## Changes Implemented

### 1. Backend Updates

**File:** `backend/apps/certificates/views.py`

- Updated `certificate_list` endpoint to include `completion_percentage` for each certificate
- Now fetches `CourseProgress` to calculate actual progress percentage
- Returns `completion_percentage: 100` for unlocked certificates
- Returns actual progress (0-99%) for locked certificates

### 2. Certificate List Page

**File:** `frontend/app/dashboard/certificates/page.tsx`

**Added:**
- Progress bar section for locked certificates showing completion percentage
- Progress hint text: "Complete course to unlock certificate"
- Animated progress bar that fills based on course progress
- Updated TypeScript interface to include `completion_percentage` field

**Removed:**
- Old requirements list (Complete all lessons, Pass quizzes, etc.)
- Replaced with cleaner progress visualization

### 3. Individual Certificate Page (Locked State)

**File:** `frontend/app/dashboard/certificates/[course_id]/page.tsx`

**New Design for Locked Certificates:**
- **BIG full-size certificate preview** (100% width, covers 3 certificate dimensions)
- Shows complete certificate layout with all sections blurred:
  - COURSEFORGE logo (blurred)
  - CERTIFICATE OF COMPLETION title (blurred)
  - Student Name placeholder (blurred)
  - Course Name placeholder (blurred)
  - Stats section with FINAL SCORE and STUDY HOURS (blurred, showing 00% and 0)
  - Completion date (blurred, showing "Date")
  - Certificate ID (blurred, showing "XXXX-XXXX-XXXX")
  - Double border frame (visible)
- **Heavy blur effect** (8px blur + 75% dark overlay)
- **Centered overlay text:**
  - Line 1: "Complete Course" (36px bold heading, uppercase, 4px letter-spacing)
  - Line 2: [Continue Course →] (16px white button with padding)
- Clicking button/link navigates to course page
- Right panel shows requirements list

**CSS Classes Added:**
- `.bigDemo` - Full-width certificate, no transform, proper aspect ratio
- `.lockOverlayBig` - Large dark overlay (75% opacity) with 8px blur
- `.overlayContentBig` - Spacious centered container (40px padding, 24px gap)
- `.lockTitleTextBig` - Large 36px uppercase heading
- `.continueCourseBtnBig` - Prominent 16px button with 16px/32px padding

### 4. Styling Updates

**File:** `frontend/app/dashboard/certificates/certificates.module.css`

**Added Progress Section Styles:**
- `.progressSection` - Container with gray background and border
- `.progressHeader` - Flex row with label and percentage
- `.progressLabel` - "PROGRESS" label styling
- `.progressValue` - Percentage value styling
- `.progressBar` - Thin bar with border
- `.progressFill` - Animated fill (black background)
- `.progressHint` - Gray hint text below progress bar

**File:** `frontend/app/dashboard/certificates/[course_id]/page.module.css`

**Added Locked Certificate Styles:**
- `.bigDemo` - Full-size certificate preview
- `.lockOverlayBig` - Full coverage dark overlay with heavy blur
- `.overlayContentBig` - Centered flex column with spacing
- `.lockTitleTextBig` - Large white uppercase heading
- `.continueCourseBtnBig` - Prominent white button
- Mobile responsive adjustments for all big demo elements

## Visual Design

### Certificate List Card (Locked):
```
┌──────────────────────────┐
│ [Blurred Cert Preview]   │
│   LOCK                   │
├──────────────────────────┤
│ Course Name              │
│ Topic description        │
│                          │
│ PROGRESS            45%  │
│ [████░░░░░░]             │
│ Complete course to       │
│ unlock certificate       │
│                          │
│ [CONTINUE COURSE →]      │
└──────────────────────────┘
```

### Individual Certificate Page (Locked):
```
┌─────────────────────────────────────────────┐
│  [BIG BLURRED CERTIFICATE PREVIEW]          │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │  COURSEFORGE (blurred)                │ │
│  │                                       │ │
│  │  CERTIFICATE OF COMPLETION (blurred)  │ │
│  │                                       │ │
│  │  ┌───────────────────────────────┐   │ │
│  │  │ This certifies that (blurred) │   │ │
│  │  │ Student Name (blurred)        │   │ │
│  │  │ has completed (blurred)       │   │ │
│  │  │ Course Name (blurred)         │   │ │
│  │  │                               │   │ │
│  │  │ FINAL SCORE: 00% (blurred)   │   │ │
│  │  │ STUDY HOURS: 0 (blurred)     │   │ │
│  │  │                               │   │ │
│  │  │ Completed on Date (blurred)  │   │ │
│  │  │                               │   │ │
│  │  │ CERTIFICATE ID                │   │ │
│  │  │ XXXX-XXXX-XXXX (blurred)     │   │ │
│  │  └───────────────────────────────┘   │ │
│  │                                       │ │
│  │  ┌───────────────────────────────┐   │ │
│  │  │                               │   │ │
│  │  │    Complete Course            │   │ │
│  │  │    [Continue Course →]       │   │ │
│  │  │                               │   │ │
│  │  └───────────────────────────────┘   │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Right Panel:                               │
│  CERTIFICATE LOCKED                         │
│  • Complete all lessons                     │
│  • Pass all quizzes                         │
│  • Complete weekly tests                    │
│  • Finish coding challenges                 │
│  [CONTINUE COURSE →]                        │
│  [BACK TO CERTIFICATES →]                   │
└─────────────────────────────────────────────┘
```

## Benefits

1. **Big Preview** - Users see exactly what the certificate will look like (3x size)
2. **Motivating Preview** - Full certificate layout visible but blurred
3. **Clear Call-to-Action** - Large "Complete Course" text with prominent button
4. **Clean Design** - Professional certificate layout with proper spacing
5. **Immediate Action** - One click to continue course from certificate page
6. **Responsive** - Works on desktop and mobile with adjusted sizing
