from django.urls import path

from . import views


app_name = "documentation"


urlpatterns = [
    path(
        "",
        views.documentation_dashboard,
        name="dashboard",
    ),
    path(
        "upload/",
        views.reference_document_upload,
        name="upload",
    ),
    path(
        "<uuid:pk>/",
        views.reference_document_detail,
        name="detail",
    ),
    path(
        "<uuid:pk>/view/",
        views.reference_document_inline,
        name="view",
    ),
    path(
        "<uuid:pk>/download/",
        views.reference_document_download,
        name="download",
    ),
]
