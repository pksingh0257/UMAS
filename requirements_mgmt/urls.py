from django.urls import path
from . import views

urlpatterns = [
    path('', views.requirement_list, name='requirement_list'),
    path('new/', views.requirement_create, name='requirement_create'),
    path('<int:pk>/', views.requirement_detail, name='requirement_detail'),
    path('<int:pk>/edit/', views.requirement_edit, name='requirement_edit'),
    path('<int:pk>/submit-ao/', views.requirement_submit_to_ao, name='requirement_submit_to_ao'),
]