from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_exempt

from .forms import ReferenceDocumentUploadForm
from .models import ReferenceDocument


DOCUMENTATION_ROLES = {
    "ADMINISTRATOR",
    "CFA",
    "ACCOUNTS_OFFICER",
    "HEAD_CLERK",
    "ACCOUNTS_CLERK",
    "ACCOUNTS_JCO",
}

DOCUMENT_UPLOAD_ROLES = {
    "ADMINISTRATOR",
    "CFA",
    "ACCOUNTS_OFFICER",
}


def _ensure_documentation_access(user):
    role = getattr(user, "role", None)
    if role not in DOCUMENTATION_ROLES:
        raise PermissionDenied(
            "You are not authorised to access Documentation."
        )
    return role


def _open_storage_file(field_file):
    try:
        return field_file.open("rb")
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("The requested document file is not available.")


@login_required
def documentation_dashboard(request):
    role = _ensure_documentation_access(request.user)

    documents = ReferenceDocument.objects.select_related(
        "uploaded_by",
        "updated_by",
    )

    search_query = request.GET.get("q", "").strip()
    category_filter = request.GET.get("category", "").strip()
    status_filter = request.GET.get("status", "").strip()
    authority_filter = request.GET.get("authority", "").strip()
    year_filter = request.GET.get("year", "").strip()

    if search_query:
        documents = documents.filter(
            Q(document_name__icontains=search_query)
            | Q(reference_number__icontains=search_query)
            | Q(version_number__icontains=search_query)
            | Q(issuing_authority__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(remarks__icontains=search_query)
        )

    valid_categories = {
        value for value, _ in ReferenceDocument.CATEGORY_CHOICES
    }
    valid_statuses = {
        value for value, _ in ReferenceDocument.STATUS_CHOICES
    }

    if category_filter in valid_categories:
        documents = documents.filter(category=category_filter)
    else:
        category_filter = ""

    if status_filter in valid_statuses:
        documents = documents.filter(status=status_filter)
    else:
        status_filter = ""

    if authority_filter:
        documents = documents.filter(
            issuing_authority=authority_filter
        )

    if year_filter.isdigit():
        documents = documents.filter(
            issue_date__year=int(year_filter)
        )
    else:
        year_filter = ""

    all_documents = ReferenceDocument.objects.all()
    latest_document = all_documents.order_by("-uploaded_at").first()

    authorities = (
        ReferenceDocument.objects.exclude(
            issuing_authority__isnull=True
        )
        .exclude(issuing_authority__exact="")
        .values_list("issuing_authority", flat=True)
        .distinct()
        .order_by("issuing_authority")
    )

    years = (
        ReferenceDocument.objects.exclude(issue_date__isnull=True)
        .dates("issue_date", "year", order="DESC")
    )

    paginator = Paginator(
        documents.order_by("-uploaded_at"),
        10,
    )
    page_obj = paginator.get_page(request.GET.get("page"))

    quick_access_documents = (
        ReferenceDocument.objects.filter(
            is_featured=True,
            status="ACTIVE",
        )
        .order_by("document_name")[:6]
    )

    recent_uploads = (
        ReferenceDocument.objects.order_by("-uploaded_at")[:5]
    )

    context = {
        "role": role,
        "total_documents": all_documents.count(),
        "active_documents": all_documents.filter(
            status="ACTIVE"
        ).count(),
        "archived_documents": all_documents.filter(
            status="ARCHIVED"
        ).count(),
        "latest_upload": (
            latest_document.uploaded_at
            if latest_document else None
        ),
        "page_obj": page_obj,
        "documents": page_obj.object_list,
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "authority_filter": authority_filter,
        "year_filter": year_filter,
        "category_choices": ReferenceDocument.CATEGORY_CHOICES,
        "status_choices": ReferenceDocument.STATUS_CHOICES,
        "authorities": authorities,
        "years": years,
        "quick_access_documents": quick_access_documents,
        "recent_uploads": recent_uploads,
    }

    return render(
        request,
        "documentation/documentation_dashboard.html",
        context,
    )


@login_required
@transaction.atomic
def reference_document_upload(request):
    role = getattr(request.user, "role", None)

    if role not in DOCUMENT_UPLOAD_ROLES:
        raise PermissionDenied(
            "You are not authorised to upload reference documents."
        )

    if request.method == "POST":
        form = ReferenceDocumentUploadForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            reference_document = form.save(commit=False)
            reference_document.uploaded_by = request.user
            reference_document.updated_by = request.user

            older_document = form.cleaned_data.get("supersedes")

            if older_document:
                older_document.status = "SUPERSEDED"
                older_document.updated_by = request.user
                older_document.save(
                    update_fields=[
                        "status",
                        "updated_by",
                        "updated_at",
                    ]
                )

            reference_document.save()

            messages.success(
                request,
                f'"{reference_document.document_name}" uploaded successfully.',
            )

            return redirect("documentation:dashboard")
    else:
        form = ReferenceDocumentUploadForm()

    return render(
        request,
        "documentation/document_upload.html",
        {"form": form, "role": role},
    )


@login_required
def reference_document_detail(request, pk):
    role = _ensure_documentation_access(request.user)

    document = get_object_or_404(
        ReferenceDocument.objects.select_related(
            "uploaded_by",
            "updated_by",
            "supersedes",
        ),
        pk=pk,
    )

    return render(
        request,
        "documentation/document_detail.html",
        {
            "role": role,
            "document": document,
            "can_preview": bool(document.preview_file),
        },
    )


@login_required
@xframe_options_exempt
def reference_document_inline(request, pk):
    _ensure_documentation_access(request.user)

    document = get_object_or_404(ReferenceDocument, pk=pk)
    preview_file = document.preview_file

    if not preview_file:
        raise Http404(
            "No browser preview is available for this document."
        )

    file_handle = _open_storage_file(preview_file)

    response = FileResponse(
        file_handle,
        content_type="application/pdf",
    )

    safe_filename = (
        Path(preview_file.name).name
        or f"{document.document_name}.pdf"
    )

    response["Content-Disposition"] = (
        f'inline; filename="{safe_filename}"'
    )
    response["X-Content-Type-Options"] = "nosniff"

    if "X-Frame-Options" in response:
        del response["X-Frame-Options"]

    return response


@login_required
def reference_document_download(request, pk):
    _ensure_documentation_access(request.user)

    document = get_object_or_404(ReferenceDocument, pk=pk)

    if not document.document_file:
        raise Http404(
            "The requested document file is not available."
        )

    file_handle = _open_storage_file(document.document_file)

    filename = (
        Path(document.document_file.name).name
        or document.document_name
    )

    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )
    response["X-Content-Type-Options"] = "nosniff"

    return response
