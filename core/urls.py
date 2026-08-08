from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('procurement/', include('procurement.urls')),
    path('requirements/', include('requirements_mgmt.urls')),
    path('', include('authentication.urls')),
    path('finance/', include('finance.urls')),
    path("documentation/", include("documentation.urls")),
]

# Serves uploaded files (Attachments, Sanction/Contract/Invoice PDFs) in
# development. MUST come after urlpatterns is defined above — Python
# reads top to bottom, so `+=` needs the list to already exist.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)