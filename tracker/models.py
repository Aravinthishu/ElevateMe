import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

WEEKDAYS = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
    (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]

ACTIVITY_KIND_CHECK = "check"
ACTIVITY_KIND_COUNT = "count"
ACTIVITY_KINDS = [
    (ACTIVITY_KIND_CHECK, "Yes / No"),
    (ACTIVITY_KIND_COUNT, "Number with a daily target"),
]


class PlanSettings(models.Model):
    """Singleton row holding everything about the plan that the user can
    tune from the Settings page: name, dates, and the weight goal."""

    plan_name = models.CharField(max_length=60, default="GRIND90")
    start_date = models.DateField(default=datetime.date.today)
    plan_weeks = models.PositiveSmallIntegerField(default=12)

    starting_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("60.0"))
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("70.0"))

    rest_weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, default=6)  # Sunday
    weigh_in_weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, default=0)  # Monday

    class Meta:
        verbose_name = "Plan settings"
        verbose_name_plural = "Plan settings"

    def __str__(self):
        return self.plan_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def total_gain_target(self):
        return self.target_weight_kg - self.starting_weight_kg

    @property
    def required_weekly_pace(self):
        if self.plan_weeks == 0:
            return Decimal("0")
        return round(self.total_gain_target / Decimal(self.plan_weeks), 2)

    @property
    def end_date(self):
        return self.start_date + datetime.timedelta(weeks=self.plan_weeks)

    def is_rest_day(self, date):
        return date.weekday() == self.rest_weekday

    def is_weigh_in_day(self, date):
        return date.weekday() == self.weigh_in_weekday

    def week_number(self, date):
        delta_days = (date - self.start_date).days
        return (delta_days // 7) + 1


class Activity(models.Model):
    """A single trackable daily habit, fully user-defined."""

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=ACTIVITY_KINDS, default=ACTIVITY_KIND_CHECK)
    target = models.PositiveIntegerField(default=1, help_text="For 'Number' activities, the daily target.")
    unit = models.CharField(max_length=20, blank=True, help_text="e.g. problems, min, g")
    icon = models.CharField(max_length=4, blank=True, help_text="One emoji or short glyph, optional")
    skip_on_rest_day = models.BooleanField(default=False, help_text="Not required on the plan's rest day")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name_plural = "Activities"

    def __str__(self):
        return self.name

    def applies_on(self, date, settings=None):
        if not self.skip_on_rest_day:
            return True
        settings = settings or PlanSettings.get_solo()
        return not settings.is_rest_day(date)

    def is_done(self, value):
        if self.kind == ACTIVITY_KIND_CHECK:
            return bool(value)
        return value >= self.target


class ActivityLog(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField(db_index=True)
    value = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("activity", "date")]

    def __str__(self):
        return f"{self.activity.name} — {self.date}"

    @property
    def done(self):
        return self.activity.is_done(self.value)


class DayNote(models.Model):
    date = models.DateField(unique=True, db_index=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.date.isoformat()


class WeightEntry(models.Model):
    date = models.DateField(unique=True, db_index=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        verbose_name_plural = "Weight entries"

    def __str__(self):
        return f"{self.date.isoformat()} — {self.weight_kg}kg"

    def clean(self):
        settings = PlanSettings.get_solo()
        if self.date and not settings.is_weigh_in_day(self.date):
            weekday_name = dict(WEEKDAYS)[settings.weigh_in_weekday]
            raise ValidationError(
                {"date": f"Weight can only be logged on {weekday_name}s. Pick this week's {weekday_name}."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def week_number(self):
        return PlanSettings.get_solo().week_number(self.date)

    def gain_from_start(self):
        return self.weight_kg - PlanSettings.get_solo().starting_weight_kg


class Subject(models.Model):
    """A user-defined learning/skill track (fully add/remove-able)."""

    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class LearningSession(models.Model):
    date = models.DateField(db_index=True, default=datetime.date.today)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="sessions")
    minutes = models.PositiveSmallIntegerField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.subject.name} — {self.minutes}min ({self.date})"
