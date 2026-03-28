"""Courses app URL patterns — /api/courses/"""
from django.urls import path
from . import views
from . import views_coding_test
from . import views_debug

urlpatterns = [
    # Course CRUD
    path("",                                                       views.course_list,     name="course-list"),
    path("generate/",                                              views.course_generate, name="course-generate"),
    path("<uuid:course_id>/",                                      views.course_detail,   name="course-detail"),
    path("<uuid:course_id>/status/",                               views.course_status,   name="course-status"),
    path("<uuid:course_id>/delete/",                               views.course_delete,   name="course-delete"),
    # Weeks
    path("<uuid:course_id>/weeks/",                                views.course_weeks,    name="course-weeks"),
    path("<uuid:course_id>/weeks/<int:week_number>/",              views.week_detail,     name="week-detail"),
    # Days
    path("<uuid:course_id>/weeks/<int:week_number>/days/",         views.week_days,       name="week-days"),
    path("<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/",           views.day_detail,    name="day-detail"),
    path("<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/start/",    views.day_start,    name="day-start"),
    path("<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/complete/", views.day_complete, name="day-complete"),
    # Daily Quiz
    path("<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/quiz/",       views.day_quiz,      name="day-quiz"),
    path("<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/quiz/submit/", views.day_quiz_submit, name="day-quiz-submit"),
    # Weekly MCQ Test (10 questions)
    path("<uuid:course_id>/weeks/<int:week_number>/test/",          views.week_test,       name="week-test"),
    path("<uuid:course_id>/weeks/<int:week_number>/test/submit/",   views.week_test_submit, name="week-test-submit"),
    path("<uuid:course_id>/weeks/<int:week_number>/test/results/",  views.week_test_results, name="week-test-results"),
    # DEBUG: Manually unlock weekly test
    path("<uuid:course_id>/weeks/<int:week_number>/test/unlock/",   views_debug.unlock_weekly_test, name="week-test-unlock"),
    # Weekly Coding Test with Judge0 integration
    path("<uuid:course_id>/weeks/<int:week_number>/coding-test/",          views_coding_test.get_coding_test,         name="coding-test"),
    path("<uuid:course_id>/weeks/<int:week_number>/coding-test/start/",   views_coding_test.start_coding_test,        name="coding-test-start"),
    path("<uuid:course_id>/weeks/<int:week_number>/coding-test/execute/", views_coding_test.execute_coding_challenge, name="coding-test-execute"),
    path("<uuid:course_id>/weeks/<int:week_number>/coding-test/submit/",   views_coding_test.submit_coding_test,       name="coding-test-submit"),
    # Progress & Certificate
    path("<uuid:course_id>/progress/",                             views.course_progress, name="course-progress"),
    path("<uuid:course_id>/certificate/",                          views.course_certificate, name="course-certificate"),
]
