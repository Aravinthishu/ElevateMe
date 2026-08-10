import calendar as cal
import datetime
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ActivityForm,
    DailyActivityForm,
    LearningSessionForm,
    NotesForm,
    PlanSettingsForm,
    SubjectForm,
    WeightEntryForm,
)
from .models import (
    Activity,
    ActivityLog,
    DayNote,
    LearningSession,
    PlanSettings,
    Subject,
    WeightEntry,
)


def _today():
    return timezone.localdate()


def week_start(d):
    return d - datetime.timedelta(days=d.weekday())


def _applicable_activities(date, settings=None):
    settings = settings or PlanSettings.get_solo()
    return [a for a in Activity.objects.filter(is_active=True) if a.applies_on(date, settings)]


def _day_status(date, settings=None):
    """Returns (done_count, total_count, ratio, per_activity list of (activity, value, done))."""
    settings = settings or PlanSettings.get_solo()
    activities = _applicable_activities(date, settings)
    logs = {l.activity_id: l for l in ActivityLog.objects.filter(date=date, activity__in=activities)}
    rows = []
    done_count = 0
    for a in activities:
        log = logs.get(a.id)
        value = log.value if log else 0
        done = a.is_done(value)
        if done:
            done_count += 1
        rows.append({"activity": a, "value": value, "done": done})
    total = len(activities)
    ratio = (done_count / total) if total else 0
    return done_count, total, ratio, rows


def _status_label(ratio, has_data=True):
    if not has_data:
        return "empty"
    if ratio >= 0.999:
        return "completed"
    if ratio <= 0:
        return "missed"
    return "partial"


def _activity_streak(activity, as_of, settings=None):
    settings = settings or PlanSettings.get_solo()
    logs = {l.date: l for l in ActivityLog.objects.filter(activity=activity, date__lte=as_of).order_by("-date")[:400]}
    streak = 0
    d = as_of
    while True:
        if activity.applies_on(d, settings) and d not in logs:
            break
        if not activity.applies_on(d, settings):
            d -= datetime.timedelta(days=1)
            continue
        log = logs[d]
        if not activity.is_done(log.value):
            break
        streak += 1
        d -= datetime.timedelta(days=1)
    return streak


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def dashboard(request):
    settings = PlanSettings.get_solo()
    today = _today()
    tracking_started = today >= settings.start_date

    done_count, total, ratio, rows = _day_status(today, settings)

    activities = list(Activity.objects.filter(is_active=True))
    streaks = [{"activity": a, "streak": _activity_streak(a, today, settings)} for a in activities[:6]]

    latest_weight = WeightEntry.objects.order_by("-date").first()
    current_weight = latest_weight.weight_kg if latest_weight else settings.starting_weight_kg
    span = settings.target_weight_kg - settings.starting_weight_kg
    if span != 0:
        progress_pct = float(min(max((current_weight - settings.starting_weight_kg) / span * 100, 0), 100))
    else:
        progress_pct = 100.0

    weight_entries = list(WeightEntry.objects.order_by("date"))
    weight_chart = {
        "labels": [f"Wk {e.week_number()}" for e in weight_entries],
        "data": [float(e.weight_kg) for e in weight_entries],
    }

    week_dates = [week_start(today) + datetime.timedelta(days=i) for i in range(7)]
    week_cells = []
    for d in week_dates:
        if d > today:
            week_cells.append({"date": d, "is_future": True, "is_today": False, "status": "future"})
        else:
            dc, tt, r, _ = _day_status(d, settings)
            week_cells.append({
                "date": d, "is_future": False, "is_today": d == today,
                "status": _status_label(r, tt > 0), "pct": round(r * 100),
            })

    context = {
        "settings": settings,
        "today": today,
        "tracking_started": tracking_started,
        "done_count": done_count,
        "total_count": total,
        "ratio_pct": round(ratio * 100),
        "rows": rows[:6],
        "streaks": streaks,
        "current_weight": current_weight,
        "progress_pct": round(progress_pct, 1),
        "kg_to_go": max(settings.target_weight_kg - current_weight, 0) if span >= 0 else max(current_weight - settings.target_weight_kg, 0),
        "weight_chart_json": json.dumps(weight_chart),
        "week_cells": week_cells,
        "plan_week_number": max(settings.week_number(today), 0),
    }
    return render(request, "tracker/dashboard.html", context)


# ---------------------------------------------------------------------------
# Day detail
# ---------------------------------------------------------------------------

def day_detail(request, date):
    d = datetime.date.fromisoformat(date)
    settings = PlanSettings.get_solo()
    activities = _applicable_activities(d, settings)
    existing = {l.activity_id: l.value for l in ActivityLog.objects.filter(date=d, activity__in=activities)}
    note_obj, _ = DayNote.objects.get_or_create(date=d)

    if request.method == "POST":
        form = DailyActivityForm(request.POST, activities=activities, existing_values=existing)
        notes_form = NotesForm(request.POST, initial={"notes": note_obj.notes})
        if form.is_valid() and notes_form.is_valid():
            for activity, field_name in form.activity_fields:
                value = form.cleaned_value_for(activity, field_name)
                ActivityLog.objects.update_or_create(activity=activity, date=d, defaults={"value": value})
            note_obj.notes = notes_form.cleaned_data["notes"]
            note_obj.save()
            messages.success(request, f"Saved {d.strftime('%A, %b %d')}.")
            return redirect("tracker:day_detail", date=d.isoformat())
    else:
        form = DailyActivityForm(activities=activities, existing_values=existing)
        notes_form = NotesForm(initial={"notes": note_obj.notes})

    context = {
        "day": d,
        "form": form,
        "notes_form": notes_form,
        "is_today": d == _today(),
        "is_rest_day": settings.is_rest_day(d),
        "learning_sessions": LearningSession.objects.filter(date=d),
        "prev_day": d - datetime.timedelta(days=1),
        "next_day": d + datetime.timedelta(days=1),
        "has_activities": len(activities) > 0,
    }
    return render(request, "tracker/day_detail.html", context)


def today_redirect(request):
    return redirect("tracker:day_detail", date=_today().isoformat())


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def calendar_view(request, year=None, month=None):
    settings = PlanSettings.get_solo()
    today = _today()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    first_of_month = datetime.date(year, month, 1)
    cal.setfirstweekday(cal.MONDAY)
    month_days = cal.monthcalendar(year, month)

    weights = {w.date: w for w in WeightEntry.objects.filter(date__year=year, date__month=month)}

    weeks = []
    for week in month_days:
        week_cells = []
        for day_num in week:
            if day_num == 0:
                week_cells.append(None)
                continue
            d = datetime.date(year, month, day_num)
            if d > today:
                week_cells.append({"date": d, "day_num": day_num, "status": "future", "is_today": False,
                                    "is_weigh_in": settings.is_weigh_in_day(d), "weight": weights.get(d)})
            else:
                dc, tt, r, _ = _day_status(d, settings)
                week_cells.append({
                    "date": d, "day_num": day_num, "status": _status_label(r, tt > 0),
                    "is_today": d == today, "is_weigh_in": settings.is_weigh_in_day(d), "weight": weights.get(d),
                })
        weeks.append(week_cells)

    prev_month = (first_of_month - datetime.timedelta(days=1)).replace(day=1)
    next_month_last_day = cal.monthrange(year, month)[1]
    next_month = (first_of_month + datetime.timedelta(days=next_month_last_day + 1)).replace(day=1)

    context = {
        "year": year, "month": month, "month_name": first_of_month.strftime("%B %Y"),
        "weeks": weeks,
        "prev_year": prev_month.year, "prev_month": prev_month.month,
        "next_year": next_month.year, "next_month": next_month.month,
        "today": today,
    }
    return render(request, "tracker/calendar.html", context)


# ---------------------------------------------------------------------------
# Weekly review
# ---------------------------------------------------------------------------

def weekly_review(request, date=None):
    settings = PlanSettings.get_solo()
    today = _today()
    anchor = datetime.date.fromisoformat(date) if date else today
    start = week_start(anchor)
    end = start + datetime.timedelta(days=6)
    prev_start = start - datetime.timedelta(days=7)
    next_start = start + datetime.timedelta(days=7)

    days = [start + datetime.timedelta(days=i) for i in range(7) if start + datetime.timedelta(days=i) <= today]

    activities = list(Activity.objects.filter(is_active=True))
    activity_stats = []
    for a in activities:
        applicable_days = [d for d in days if a.applies_on(d, settings)]
        logs = {l.date: l for l in ActivityLog.objects.filter(activity=a, date__in=applicable_days)}
        done = sum(1 for d in applicable_days if d in logs and a.is_done(logs[d].value))
        total_value = sum(l.value for l in logs.values())
        activity_stats.append({
            "activity": a, "done": done, "total_days": len(applicable_days),
            "pct": round((done / len(applicable_days) * 100) if applicable_days else 0),
            "total_value": total_value,
        })

    this_week_weight = WeightEntry.objects.filter(date=start).first()
    prev_week_weight = WeightEntry.objects.filter(date=prev_start).first()
    weight_change = (this_week_weight.weight_kg - prev_week_weight.weight_kg) if (this_week_weight and prev_week_weight) else None

    day_rows = []
    for d in days:
        dc, tt, r, _ = _day_status(d, settings)
        day_rows.append({"date": d, "done": dc, "total": tt, "pct": round(r * 100)})

    context = {
        "week_start": start, "week_end": end,
        "prev_start": prev_start, "next_start": next_start,
        "is_current_week": start == week_start(today),
        "activity_stats": activity_stats,
        "this_week_weight": this_week_weight, "prev_week_weight": prev_week_weight,
        "weight_change": weight_change,
        "day_rows": day_rows,
        "week_number": max(settings.week_number(start), 0),
    }
    return render(request, "tracker/weekly_review.html", context)


# ---------------------------------------------------------------------------
# Monthly review
# ---------------------------------------------------------------------------

def monthly_review(request, year=None, month=None):
    settings = PlanSettings.get_solo()
    today = _today()
    year = int(year) if year else today.year
    month = int(month) if month else today.month

    start = datetime.date(year, month, 1)
    last_day = cal.monthrange(year, month)[1]
    end = datetime.date(year, month, last_day)
    effective_end = min(end, today)
    days = [start + datetime.timedelta(days=i) for i in range((effective_end - start).days + 1)] if effective_end >= start else []

    activities = list(Activity.objects.filter(is_active=True))
    category_stats = []
    for a in activities:
        applicable_days = [d for d in days if a.applies_on(d, settings)]
        logs = {l.date: l for l in ActivityLog.objects.filter(activity=a, date__in=applicable_days)}
        done = sum(1 for d in applicable_days if d in logs and a.is_done(logs[d].value))
        pct = round((done / len(applicable_days) * 100) if applicable_days else 0)
        category_stats.append({"activity": a, "pct": pct})

    weight_entries = list(WeightEntry.objects.filter(date__range=(start, end)).order_by("date"))
    weight_chart = {
        "labels": [f"Wk {e.week_number()}" for e in weight_entries],
        "data": [float(e.weight_kg) for e in weight_entries],
    }

    subjects = Subject.objects.filter(is_active=True)
    learning_totals = []
    for s in subjects:
        total = sum(sess.minutes for sess in LearningSession.objects.filter(date__range=(start, end), subject=s))
        learning_totals.append({"subject": s, "minutes": total})

    streaks = [{"activity": a, "streak": _activity_streak(a, effective_end, settings)} for a in activities[:6]] if days else []

    prev_month = (start - datetime.timedelta(days=1)).replace(day=1)
    next_month = end + datetime.timedelta(days=1)

    context = {
        "year": year, "month": month, "month_name": start.strftime("%B %Y"),
        "category_stats": category_stats,
        "weight_chart_json": json.dumps(weight_chart),
        "weight_entries": weight_entries,
        "learning_totals": learning_totals,
        "streaks": streaks,
        "days_tracked": len(days),
        "prev_year": prev_month.year, "prev_month": prev_month.month,
        "next_year": next_month.year, "next_month": next_month.month,
        "is_current_month": (year, month) == (today.year, today.month),
    }
    return render(request, "tracker/monthly_review.html", context)


# ---------------------------------------------------------------------------
# Weight tracker
# ---------------------------------------------------------------------------

def weight_tracker(request):
    settings = PlanSettings.get_solo()
    today = _today()
    if request.method == "POST":
        form = WeightEntryForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Weight logged.")
                return redirect("tracker:weight_tracker")
            except ValidationError as e:
                form.add_error("date", e)
    else:
        if settings.is_weigh_in_day(today):
            suggested = today
        else:
            days_ahead = (settings.weigh_in_weekday - today.weekday()) % 7
            suggested = today + datetime.timedelta(days=days_ahead or 7)
        form = WeightEntryForm(initial={"date": suggested})

    entries = list(WeightEntry.objects.order_by("date"))
    chart = {
        "labels": [f"Wk {e.week_number()} ({e.date.strftime('%b %d')})" for e in entries],
        "data": [float(e.weight_kg) for e in entries],
        "target": float(settings.target_weight_kg),
    }

    rows = []
    prev = None
    for e in entries:
        change = (e.weight_kg - prev.weight_kg) if prev else None
        rows.append({"entry": e, "change": change})
        prev = e
    rows.reverse()

    context = {
        "settings": settings,
        "form": form,
        "entries": rows,
        "chart_json": json.dumps(chart),
        "latest": entries[-1] if entries else None,
    }
    return render(request, "tracker/weight_tracker.html", context)


# ---------------------------------------------------------------------------
# Learning progress
# ---------------------------------------------------------------------------

def learning_progress(request):
    today = _today()
    if request.method == "POST":
        form = LearningSessionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Session logged.")
            return redirect("tracker:learning_progress")
    else:
        form = LearningSessionForm(initial={"date": today})

    subjects = Subject.objects.filter(is_active=True)
    subject_stats = []
    for s in subjects:
        sessions = LearningSession.objects.filter(subject=s)
        subject_stats.append({
            "subject": s,
            "total_minutes": sum(x.minutes for x in sessions),
            "session_count": sessions.count(),
            "recent": list(sessions.order_by("-date")[:5]),
        })

    context = {
        "form": form,
        "subject_stats": subject_stats,
        "all_sessions": LearningSession.objects.all()[:30],
        "has_subjects": subjects.exists(),
    }
    return render(request, "tracker/learning.html", context)


# ---------------------------------------------------------------------------
# Settings — plan, activities, subjects (fully dynamic add/remove)
# ---------------------------------------------------------------------------

def settings_view(request):
    settings = PlanSettings.get_solo()
    plan_form = PlanSettingsForm(instance=settings)
    activity_form = ActivityForm()
    subject_form = SubjectForm()

    context = {
        "settings": settings,
        "plan_form": plan_form,
        "activity_form": activity_form,
        "subject_form": subject_form,
        "activities": Activity.objects.all(),
        "subjects": Subject.objects.all(),
    }
    return render(request, "tracker/settings.html", context)


def update_plan_settings(request):
    settings = PlanSettings.get_solo()
    if request.method == "POST":
        form = PlanSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Plan settings updated.")
        else:
            messages.error(request, "Couldn't save plan settings — check the highlighted fields.")
    return redirect("tracker:settings")


def add_activity(request):
    if request.method == "POST":
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.sort_order = Activity.objects.count()
            activity.save()
            messages.success(request, f"Added '{activity.name}' to your daily activities.")
        else:
            messages.error(request, "Couldn't add that activity — check the fields.")
    return redirect("tracker:settings")


def delete_activity(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == "POST":
        name = activity.name
        activity.delete()
        messages.success(request, f"Removed '{name}' and its logged history.")
    return redirect("tracker:settings")


def toggle_activity(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == "POST":
        activity.is_active = not activity.is_active
        activity.save()
    return redirect("tracker:settings")


def add_subject(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.sort_order = Subject.objects.count()
            subject.save()
            messages.success(request, f"Added '{subject.name}' to your learning subjects.")
        else:
            messages.error(request, "That subject couldn't be added — check the name.")
    return redirect("tracker:settings")


def delete_subject(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        name = subject.name
        subject.delete()
        messages.success(request, f"Removed '{name}' and its logged sessions.")
    return redirect("tracker:settings")


def toggle_subject(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == "POST":
        subject.is_active = not subject.is_active
        subject.save()
    return redirect("tracker:settings")
