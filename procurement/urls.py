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
    path('noting/<int:pk>/submit/', views.noting_sheet_submit_for_approval, name='noting_sheet_submit_for_approval'),
    path('noting/<int:pk>/download/', views.noting_sheet_download_pdf, name='noting_sheet_download_pdf'),

    # NEW: EAS flow (created from an APPROVED noting sheet)
    path('eas/new/<int:noting_sheet_pk>/', views.eas_create, name='eas_create'),
    path('eas/<int:pk>/', views.eas_detail, name='eas_detail'),
    path('eas/<int:pk>/edit/', views.eas_edit, name='eas_edit'),
    path('eas/<int:pk>/download/', views.eas_download_pdf, name='eas_download_pdf'),
    path('eas/<int:pk>/upload/<str:doc_type>/', views.eas_upload_document, name='eas_upload_document'),

    # UNCHANGED
    path('audit-trail/', views.audit_trail, name='audit_trail'),
    path('case/<str:case_number>/', views.case_detail, name='case_detail'),
    path("convening-order/create/<int:eas_pk>/",views.convening_order_create,name="convening_order_create",),
    path("convening-order/<int:pk>/",views.convening_order_detail,name="convening_order_detail",),
    path("convening-order/<int:pk>/docx/",views.convening_order_download_docx,name="convening_order_download_docx",),

]