from .models import PlanSettings


def plan_settings(request):
    return {"settings": PlanSettings.get_solo()}
