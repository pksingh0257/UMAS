from django.contrib import admin

from .models import (
    FinancialYear,
    FundEntry,
    FundTransaction,
)


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "start_date",
        "end_date",
        "is_active",
        "is_closed",
    )

    list_filter = (
        "is_active",
        "is_closed",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "-start_date",
    )


@admin.register(FundEntry)
class FundEntryAdmin(admin.ModelAdmin):
    list_display = (
        "entry_date",
        "financial_year",
        "get_fund_head",
        "sub_head",
        "entry_type",
        "amount",
        "status",
        "created_by",
        "cfa_acted_by",
    )

    list_filter = (
        "financial_year",
        "entry_type",
        "status",
        "sub_head__fund_head",
        "sub_head",
    )

    search_fields = (
        "sub_head__name",
        "sub_head__code",
        "sub_head__fund_head__name",
        "source",
        "authority_number",
        "remarks",
    )

    readonly_fields = (
        "cfa_acted_by",
        "cfa_acted_at",
        "created_at",
        "modified_at",
    )

    ordering = (
        "-entry_date",
        "-created_at",
    )

    @admin.display(
        description="Fund",
        ordering="sub_head__fund_head__name",
    )
    def get_fund_head(self, obj):
        return obj.sub_head.fund_head.name


@admin.register(FundTransaction)
class FundTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "financial_year",
        "get_fund_head",
        "sub_head",
        "transaction_type",
        "amount",
        "reference_number",
        "created_by",
        "is_reversed",
    )

    list_filter = (
        "financial_year",
        "transaction_type",
        "sub_head__fund_head",
        "sub_head",
        "is_reversed",
    )

    search_fields = (
        "sub_head__name",
        "sub_head__code",
        "reference_number",
        "reference_type",
        "remarks",
    )

    readonly_fields = (
        "fund_entry",
        "financial_year",
        "sub_head",
        "transaction_type",
        "amount",
        "transaction_date",
        "reference_number",
        "reference_type",
        "reference_id",
        "remarks",
        "created_by",
        "modified_by",
        "created_at",
        "modified_at",
    )

    ordering = (
        "-transaction_date",
        "-created_at",
    )

    def has_add_permission(self, request):
        # Ledger records must be generated through authorised workflows.
        return False

    def has_delete_permission(self, request, obj=None):
        # Financial transactions must never be deleted.
        return False

    @admin.display(
        description="Fund",
        ordering="sub_head__fund_head__name",
    )
    def get_fund_head(self, obj):
        return obj.sub_head.fund_head.name