from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError

from .models import ReferenceDocument
from .validators import (
    validate_document_upload,
    validate_preview_pdf,
)


class ReferenceDocumentUploadForm(forms.ModelForm):
    class Meta:
        model = ReferenceDocument
        fields = [
            "document_name",
            "reference_number",
            "category",
            "issuing_authority",
            "issue_date",
            "effective_date",
            "version_number",
            "description",
            "document_file",
            "preview_pdf",
            "status",
            "supersedes",
            "is_featured",
            "remarks",
        ]

        widgets = {
            "document_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter document title",
                }
            ),
            "reference_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter official reference number",
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-select"}
            ),
            "issuing_authority": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Example: Ministry of Defence",
                }
            ),
            "issue_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "effective_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "version_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Version / amendment number",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Short description of this document",
                }
            ),
            "document_file": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.doc,.docx",
                }
            ),
            "preview_pdf": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf",
                }
            ),
            "status": forms.Select(
                attrs={"class": "form-select"}
            ),
            "supersedes": forms.Select(
                attrs={"class": "form-select"}
            ),
            "is_featured": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional remarks",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["supersedes"].queryset = (
            ReferenceDocument.objects.exclude(
                status="ARCHIVED"
            ).order_by("document_name", "-uploaded_at")
        )

        self.fields["supersedes"].required = False
        self.fields["preview_pdf"].required = False
        self.fields["reference_number"].required = False
        self.fields["issue_date"].required = False
        self.fields["effective_date"].required = False
        self.fields["version_number"].required = False
        self.fields["description"].required = False
        self.fields["remarks"].required = False

    def clean_document_file(self):
        uploaded_file = self.cleaned_data.get("document_file")

        if not uploaded_file:
            raise ValidationError(
                "Please select a document file."
            )

        validate_document_upload(uploaded_file)
        return uploaded_file

    def clean_preview_pdf(self):
        preview_pdf = self.cleaned_data.get("preview_pdf")

        if preview_pdf:
            validate_preview_pdf(preview_pdf)

        return preview_pdf

    def clean(self):
        cleaned_data = super().clean()

        document_file = cleaned_data.get("document_file")
        preview_pdf = cleaned_data.get("preview_pdf")
        supersedes = cleaned_data.get("supersedes")
        status = cleaned_data.get("status")

        if document_file:
            extension = Path(document_file.name).suffix.lower()

            if extension in {".doc", ".docx"} and not preview_pdf:
                self.add_error(
                    "preview_pdf",
                    (
                        "Upload a PDF preview for a DOC/DOCX file so it can "
                        "be viewed inside UAMS. The original Word file will "
                        "still remain available for download."
                    ),
                )

        if supersedes and status != "ACTIVE":
            self.add_error(
                "status",
                (
                    "A replacement document should be uploaded as Active. "
                    "The older document will be marked Superseded."
                ),
            )

        return cleaned_data
