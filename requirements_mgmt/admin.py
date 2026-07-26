from django.contrib import admin
from .models import Requirement


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    """
    Requirement is now a single flat model (no more RequirementRequest +
    RequirementItem inline formset — that pattern is gone along with the
    old models, so there's no inline class here anymore).
    """

    list_display = [
        "requirement_id", "item_name", "category", "quantity",
        "estimated_cost", "priority", "purchase_mode",
        "workflow_status", "ao_status", "cfa_status",
        "raised_by", "created_at",
    ]
    list_filter = ["priority", "purchase_mode", "workflow_status", "ao_status", "cfa_status"]
    search_fields = ["requirement_id", "item_name", "category", "demanded_by"]

    # requirement_id is auto-generated in save(); created_at/updated_at are
    # auto-managed. Left the ao_/cfa_ decision fields EDITABLE here (not
    # readonly) so an admin/superuser can manually correct a workflow
    # state if something goes wrong — remove them from this list if you'd
    # rather force all decisions through the AO/CFA screens only.
    readonly_fields = ["requirement_id", "created_at", "updated_at"]

    fieldsets = (
        ("Identity", {
            "fields": ("requirement_id", "raised_by", "created_at", "updated_at")
        }),
        ("Item Details", {
            "fields": (
                "item_name", "category", "quantity", "purpose",
                "estimated_cost", "demanded_by", "fund_head",
                "purchase_mode", "priority", "attachment",
            )
        }),
        ("Workflow", {
            "fields": ("workflow_status",)
        }),
        ("Account Officer Decision", {
            "fields": ("ao_status", "ao_remarks", "ao_acted_by", "ao_acted_at")
        }),
        ("CFA Decision", {
            "fields": ("cfa_status", "cfa_remarks", "cfa_acted_by", "cfa_acted_at")
        }),
    )