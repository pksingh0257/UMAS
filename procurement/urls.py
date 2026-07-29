from django.urls import path
from . import views

urlpatterns = [
    # NEW: "Procurement" in the sidebar now lands here (dashboard with
    # Total/Pending/Completed cards + noting sheet table), per your mockup.
    path('', views.procurement_dashboard, name='procurement_dashboard'),

    # MOVED from '' to 'cases/'. Still works anywhere referenced via
    # {% url 'case_list' %} since Django resolves by name, not path.
    path('cases/', views.case_list, name='case_list'),

    # NEW: noting sheet flow
    path('select/', views.procurement_select, name='procurement_select'),
    path('noting/new/<int:requirement_pk>/', views.noting_sheet_create, name='noting_sheet_create'),
    path('noting/<int:pk>/', views.noting_sheet_detail, name='noting_sheet_detail'),
    path('noting/<int:pk>/submit-ao/', views.noting_sheet_submit_to_ao, name='noting_sheet_submit_to_ao'),

    # NEW: EAS flow (created from an APPROVED noting sheet)
    path('eas/new/<int:noting_sheet_pk>/', views.eas_create, name='eas_create'),
    path('eas/<int:pk>/', views.eas_detail, name='eas_detail'),
    path('eas/<int:pk>/edit/', views.eas_edit, name='eas_edit'),

    # UNCHANGED
    path('audit-trail/', views.audit_trail, name='audit_trail'),
    path('case/<str:case_number>/', views.case_detail, name='case_detail'),
]