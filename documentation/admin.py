from django.contrib import admin

from .models import ReferenceDocument


@admin.register(ReferenceDocument)
class ReferenceDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_name",
        "category",
        "issuing_authority",
        "issue_date",
        "version_number",
        "status",
        "is_featured",
        "uploaded_by",
        "uploaded_at",
    )

    list_filter = (
        "category",
        "status",
        "is_featured",
        "issuing_authority",
        "issue_date",
    )

    search_fields = (
        "document_name",
        "reference_number",
        "version_number",
        "issuing_authority",
        "description",
    )

    readonly_fields = (
        "uploaded_at",
        "updated_at",
    )

    autocomplete_fields = (
        "uploaded_by",
        "updated_by",
        "supersedes",
    )

    ordering = (
        "-uploaded_at",
    )

    fieldsets = (
        (
            "Document Details",
            {
                "fields": (
                    "document_name",
                    "reference_number",
                    "category",
                    "issuing_authority",
                    "issue_date",
                    "effective_date",
                    "version_number",
                    "description",
                )
            },
        ),
        (
            "Files",
            {
                "fields": (
                    "document_file",
                    "preview_pdf",
                )
            },
        ),
        (
            "Status and Version",
            {
                "fields": (
                    "status",
                    "supersedes",
                    "is_featured",
                    "remarks",
                )
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "uploaded_by",
                    "updated_by",
                    "uploaded_at",
                    "updated_at",
                )
            },
        ),
    )
