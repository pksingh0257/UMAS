import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def reference_document_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    safe_name = slugify(Path(filename).stem) or "document"
    year = instance.issue_date.year if instance.issue_date else timezone.localdate().year
    category = slugify(instance.category or "other")
    return f"documentation/{year}/{category}/{safe_name}{extension}"


def reference_preview_upload_path(instance, filename):
    safe_name = slugify(Path(filename).stem) or "preview"
    year = instance.issue_date.year if instance.issue_date else timezone.localdate().year
    category = slugify(instance.category or "other")
    return f"documentation/{year}/{category}/previews/{safe_name}.pdf"


class ReferenceDocument(models.Model):
    CATEGORY_CHOICES = [
        ("GFR", "GFR"),
        ("DPM", "Defence Procurement Manual"),
        ("DFPDS", "Delegation of Financial Powers"),
        ("GEM", "GeM Guidelines"),
        ("MOD", "MoD Instructions"),
        ("ARMY_HQ", "Army HQ Letters"),
        ("COMMAND", "Command Instructions"),
        ("PCDA_CDA", "PCDA / CDA Circulars"),
        ("UNIT_SOP", "Unit SOPs"),
        ("OTHER", "Other Important Documents"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("SUPERSEDED", "Superseded"),
        ("ARCHIVED", "Archived"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    document_name = models.CharField(
        max_length=250,
        verbose_name="Document Name",
    )

    reference_number = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        verbose_name="Reference Number",
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
    )

    issuing_authority = models.CharField(
        max_length=180,
        verbose_name="Issuing Authority",
    )

    issue_date = models.DateField(
        blank=True,
        null=True,
    )

    effective_date = models.DateField(
        blank=True,
        null=True,
    )

    version_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Version / Amendment Number",
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    document_file = models.FileField(
        upload_to=reference_document_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "doc", "docx"]
            )
        ],
    )

    preview_pdf = models.FileField(
        upload_to=reference_preview_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf"]
            )
        ],
        blank=True,
        null=True,
        help_text=(
            "Optional PDF preview for DOC/DOCX files. "
            "PDF documents do not need a separate preview."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
    )

    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="superseded_by",
        blank=True,
        null=True,
        help_text="Select the older document replaced by this document.",
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    is_featured = models.BooleanField(
        default=False,
        help_text="Display this document in Quick Access.",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reference_documents_uploaded",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reference_documents_updated",
        blank=True,
        null=True,
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "doc_reference_documents"
        ordering = ["-uploaded_at"]
        verbose_name = "Reference Document"
        verbose_name_plural = "Reference Documents"
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
            models.Index(fields=["issuing_authority"]),
            models.Index(fields=["uploaded_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "document_name",
                    "reference_number",
                    "version_number",
                ],
                name="unique_reference_document_version",
            )
        ]

    def __str__(self):
        if self.version_number:
            return f"{self.document_name} ({self.version_number})"
        return self.document_name

    def clean(self):
        errors = {}

        if (
            self.issue_date
            and self.effective_date
            and self.effective_date < self.issue_date
        ):
            errors["effective_date"] = (
                "Effective date cannot be earlier than issue date."
            )

        if self.supersedes_id and self.supersedes_id == self.pk:
            errors["supersedes"] = (
                "A document cannot supersede itself."
            )

        if self.document_file:
            extension = Path(self.document_file.name).suffix.lower()

            if extension in {".doc", ".docx"} and not self.preview_pdf:
                # Preview remains optional for Phase 2, but the warning is
                # deliberately not a validation error. The viewer phase will
                # use preview_pdf when available and offer download otherwise.
                pass

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def document_year(self):
        return self.issue_date.year if self.issue_date else None

    @property
    def file_extension(self):
        if not self.document_file:
            return ""
        return Path(self.document_file.name).suffix.lower().lstrip(".")

    @property
    def file_size_bytes(self):
        if not self.document_file:
            return 0
        try:
            return self.document_file.size
        except (FileNotFoundError, OSError):
            return 0

    @property
    def file_size_display(self):
        size = self.file_size_bytes

        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"

        return f"{size / (1024 * 1024):.1f} MB"

    @property
    def preview_file(self):
        if self.file_extension == "pdf":
            return self.document_file

        if self.preview_pdf:
            return self.preview_pdf

        return None
