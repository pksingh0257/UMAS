from django.urls import path
from . import views

urlpatterns = [
    path('', views.case_list, name='case_list'),
    path('audit-trail/', views.audit_trail, name='audit_trail'),
    path('case/<str:case_number>/', views.case_detail, name='case_detail'),
]