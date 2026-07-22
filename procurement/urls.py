from django.urls import path
from . import views

urlpatterns = [
    path('case/<str:case_number>/', views.case_detail, name='case_detail'),
]