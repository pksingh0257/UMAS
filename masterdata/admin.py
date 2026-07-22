from django.contrib import admin
from .models import Unit, FundHead, SubHead, ItemCategory


class AuditedAdmin(admin.ModelAdmin):
    """Shared behavior: hide audit fields from the form, auto-fill on save."""
    exclude = ['created_by', 'modified_by', 'is_deleted', 'deleted_at']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Unit)
class UnitAdmin(AuditedAdmin):
    list_display = ['code', 'name', 'contact_officer', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(FundHead)
class FundHeadAdmin(AuditedAdmin):
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(SubHead)
class SubHeadAdmin(AuditedAdmin):
    list_display = ['code', 'name', 'fund_head', 'is_active']
    list_filter = ['is_active', 'fund_head']
    search_fields = ['name', 'code']


@admin.register(ItemCategory)
class ItemCategoryAdmin(AuditedAdmin):
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']