from django.contrib import admin
from django.urls import path, include
urlpatterns = [
    path('admin/', admin.site.urls),
    path('procurement/', include('procurement.urls')),
    path('requirements/', include('requirements_mgmt.urls')),
    path('', include('authentication.urls')),
]