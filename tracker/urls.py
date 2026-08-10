from django.urls import path

from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("today/", views.today_redirect, name="today"),
    path("day/<str:date>/", views.day_detail, name="day_detail"),
    path("calendar/", views.calendar_view, name="calendar_current"),
    path("calendar/<int:year>/<int:month>/", views.calendar_view, name="calendar"),
    path("review/week/", views.weekly_review, name="weekly_review_current"),
    path("review/week/<str:date>/", views.weekly_review, name="weekly_review"),
    path("review/month/", views.monthly_review, name="monthly_review_current"),
    path("review/month/<int:year>/<int:month>/", views.monthly_review, name="monthly_review"),
    path("weight/", views.weight_tracker, name="weight_tracker"),
    path("learning/", views.learning_progress, name="learning_progress"),

    path("settings/", views.settings_view, name="settings"),
    path("settings/plan/", views.update_plan_settings, name="update_plan_settings"),
    path("settings/activities/add/", views.add_activity, name="add_activity"),
    path("settings/activities/<int:pk>/delete/", views.delete_activity, name="delete_activity"),
    path("settings/activities/<int:pk>/toggle/", views.toggle_activity, name="toggle_activity"),
    path("settings/subjects/add/", views.add_subject, name="add_subject"),
    path("settings/subjects/<int:pk>/delete/", views.delete_subject, name="delete_subject"),
    path("settings/subjects/<int:pk>/toggle/", views.toggle_subject, name="toggle_subject"),
]
