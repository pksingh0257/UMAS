from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import ProcurementCase, CaseStageHistory


class CaseStageHistoryInline(admin.TabularInline):
    model = CaseStageHistory
    extra = 0
    fields = [
        "from_stage",
        "to_stage",
        "action",
        "performed_by",
        "remarks",
        "created_at",
    ]
    readonly_fields = [
        "from_stage",
        "to_stage",
        "action",
        "performed_by",
        "remarks",
        "created_at",
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProcurementCase)
class ProcurementCaseAdmin(admin.ModelAdmin):
    list_display = [
        "case_number",
        "requirement_item",
        "current_stage",
        "fund_head",
        "is_closed",
    ]
    list_filter = ["current_stage", "is_closed", "fund_head"]
    search_fields = ["case_number"]
    readonly_fields = ["case_number", "current_stage", "is_closed", "closed_at"]
    exclude = ["created_by", "modified_by", "is_deleted", "deleted_at"]
    inlines = [CaseStageHistoryInline]
    actions = ["advance_stage"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Advance selected cases to next stage")
    def advance_stage(self, request, queryset):
        advanced, failed = 0, 0
        for case in queryset:
            try:
                case.advance(user=request.user)
                advanced += 1
            except ValidationError as e:
                failed += 1
                self.message_user(
                    request, f"{case.case_number}: {e.message}", level=messages.ERROR
                )
        if advanced:
            self.message_user(request, f"{advanced} case(s) advanced successfully.")


@admin.register(CaseStageHistory)
class CaseStageHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "case",
        "from_stage",
        "to_stage",
        "action",
        "performed_by",
        "created_at",
    ]
    list_filter = ["action", "to_stage"]
    search_fields = ["case__case_number"]
    readonly_fields = [f.name for f in CaseStageHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
