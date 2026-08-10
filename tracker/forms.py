from django import forms

from .models import Activity, LearningSession, PlanSettings, Subject, WeightEntry

INPUT = "input-field"


class DailyActivityForm(forms.Form):
    """Builds one field per applicable Activity for a given date, on the fly."""

    def __init__(self, *args, activities=None, existing_values=None, **kwargs):
        super().__init__(*args, **kwargs)
        existing_values = existing_values or {}
        self.activity_fields = []
        for activity in activities:
            field_name = f"activity_{activity.id}"
            initial = existing_values.get(activity.id, 0)
            if activity.kind == "check":
                field = forms.BooleanField(
                    required=False,
                    initial=bool(initial),
                    widget=forms.CheckboxInput(attrs={"class": "toggle-checkbox"}),
                )
            else:
                field = forms.IntegerField(
                    required=False,
                    min_value=0,
                    initial=initial,
                    widget=forms.NumberInput(attrs={"class": INPUT, "placeholder": "0"}),
                )
            self.fields[field_name] = field
            self.activity_fields.append((activity, field_name))

    def cleaned_value_for(self, activity, field_name):
        val = self.cleaned_data.get(field_name)
        if activity.kind == "check":
            return 1 if val else 0
        return val or 0


class NotesForm(forms.Form):
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT, "rows": 3, "placeholder": "Anything worth remembering about today?"}),
    )


class WeightEntryForm(forms.ModelForm):
    class Meta:
        model = WeightEntry
        fields = ["date", "weight_kg", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "weight_kg": forms.NumberInput(attrs={"class": INPUT, "step": "0.1", "placeholder": "kg"}),
            "notes": forms.TextInput(attrs={"class": INPUT, "placeholder": "Optional note"}),
        }


class LearningSessionForm(forms.ModelForm):
    class Meta:
        model = LearningSession
        fields = ["date", "subject", "minutes", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "subject": forms.Select(attrs={"class": INPUT}),
            "minutes": forms.NumberInput(attrs={"class": INPUT, "min": 1, "placeholder": "minutes"}),
            "notes": forms.TextInput(attrs={"class": INPUT, "placeholder": "What did you cover?"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["name", "kind", "target", "unit", "icon", "skip_on_rest_day"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. Read 10 pages"}),
            "kind": forms.Select(attrs={"class": INPUT}),
            "target": forms.NumberInput(attrs={"class": INPUT, "min": 1}),
            "unit": forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. pages (optional)"}),
            "icon": forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. \U0001F4DA"}),
            "skip_on_rest_day": forms.CheckboxInput(attrs={"class": "toggle-checkbox"}),
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": INPUT, "placeholder": "e.g. Rust Basics"})}


class PlanSettingsForm(forms.ModelForm):
    class Meta:
        model = PlanSettings
        fields = [
            "plan_name", "start_date", "plan_weeks",
            "starting_weight_kg", "target_weight_kg",
            "rest_weekday", "weigh_in_weekday",
        ]
        widgets = {
            "plan_name": forms.TextInput(attrs={"class": INPUT}),
            "start_date": forms.DateInput(attrs={"class": INPUT, "type": "date"}),
            "plan_weeks": forms.NumberInput(attrs={"class": INPUT, "min": 1}),
            "starting_weight_kg": forms.NumberInput(attrs={"class": INPUT, "step": "0.1"}),
            "target_weight_kg": forms.NumberInput(attrs={"class": INPUT, "step": "0.1"}),
            "rest_weekday": forms.Select(attrs={"class": INPUT}),
            "weigh_in_weekday": forms.Select(attrs={"class": INPUT}),
        }
