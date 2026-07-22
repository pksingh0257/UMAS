from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('procurement/', include('procurement.urls')),
    path('', include('authentication.urls')),
]