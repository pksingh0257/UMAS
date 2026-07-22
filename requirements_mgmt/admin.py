from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import RequirementRequest, RequirementItem


class RequirementItemInline(admin.TabularInline):
    model = RequirementItem
    extra = 1
    fields = [
        "item_number",
        "description",
        "quantity",
        "fund_head",
        "item_category",
        "priority",
        "case_generated",
    ]
    readonly_fields = ["item_number", "case_generated"]
    exclude = ["created_by", "modified_by", "is_deleted", "deleted_at"]


@admin.register(RequirementRequest)
class RequirementRequestAdmin(admin.ModelAdmin):
    list_display = ["request_number", "unit", "raised_by", "status", "submitted_at"]
    list_filter = ["status", "unit"]
    search_fields = ["request_number"]
    readonly_fields = ["request_number", "status", "submitted_at"]
    exclude = ["created_by", "modified_by", "is_deleted", "deleted_at"]
    inlines = [RequirementItemInline]
    actions = ["submit_requests"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            if not obj.raised_by_id:
                obj.raised_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.created_by = request.user
            instance.modified_by = request.user
            instance.save()
        formset.save_m2m()

    @admin.action(description="Submit selected Requirement Requests")
    def submit_requests(self, request, queryset):
        submitted, skipped = 0, 0
        for req in queryset:
            if req.status == "SUBMITTED":
                skipped += 1
                continue
            try:
                req.submit(user=request.user)
                submitted += 1
            except ValidationError as e:
                self.message_user(
                    request, f"{req.request_number}: {e.message}", level=messages.ERROR
                )
        if submitted:
            self.message_user(
                request, f"{submitted} request(s) submitted successfully."
            )
        if skipped:
            self.message_user(
                request,
                f"{skipped} request(s) were already submitted.",
                level=messages.WARNING,
            )


@admin.register(RequirementItem)
class RequirementItemAdmin(admin.ModelAdmin):
    list_display = [
        "item_number",
        "requirement_request",
        "description",
        "quantity",
        "fund_head",
        "priority",
        "case_generated",
    ]
    list_filter = ["priority", "case_generated", "fund_head"]
    search_fields = ["item_number", "description"]
    readonly_fields = ["item_number", "case_generated"]
    exclude = ["created_by", "modified_by", "is_deleted", "deleted_at"]
