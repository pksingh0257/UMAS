from pathlib import Path

from django.core.exceptions import ValidationError


MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
ALLOWED_PREVIEW_EXTENSIONS = {".pdf"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
}


def validate_document_upload(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            "Only PDF, DOC and DOCX files are allowed."
        )

    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            "The uploaded file exceeds the maximum size of 50 MB."
        )

    content_type = getattr(uploaded_file, "content_type", None)

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            "The uploaded file type is not supported."
        )


def validate_preview_pdf(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in ALLOWED_PREVIEW_EXTENSIONS:
        raise ValidationError(
            "The preview file must be a PDF."
        )

    if uploaded_file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            "The preview PDF exceeds the maximum size of 50 MB."
        )
