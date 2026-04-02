"""
Course Service Package.

Provides production-grade services for:
- Course completion tracking
- Weekly test management
- Progress validation
- Certificate generation triggers
"""

from .completion import CourseCompletionService, get_completion_service
from .weekly_test import WeeklyTestService, get_weekly_test_service

__all__ = [
    "CourseCompletionService",
    "get_completion_service",
    "WeeklyTestService",
    "get_weekly_test_service",
]
