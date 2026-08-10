from django.contrib import admin

from .models import Activity, ActivityLog, DayNote, LearningSession, PlanSettings, Subject, WeightEntry


@admin.register(PlanSettings)
class PlanSettingsAdmin(admin.ModelAdmin):
    list_display = ("plan_name", "start_date", "plan_weeks", "starting_weight_kg", "target_weight_kg")

    def has_add_permission(self, request):
        return not PlanSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "target", "unit", "skip_on_rest_day", "is_active", "sort_order")
    list_editable = ("sort_order", "is_active")
    list_filter = ("kind", "is_active", "skip_on_rest_day")
    search_fields = ("name",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("date", "activity", "value")
    list_filter = ("activity",)
    date_hierarchy = "date"


@admin.register(WeightEntry)
class WeightEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "weight_kg")
    date_hierarchy = "date"


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ("date", "subject", "minutes")
    list_filter = ("subject",)
    date_hierarchy = "date"


@admin.register(DayNote)
class DayNoteAdmin(admin.ModelAdmin):
    list_display = ("date", "notes")
    date_hierarchy = "date"
