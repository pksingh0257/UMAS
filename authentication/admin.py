from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'role', 'status', 'is_staff']
    list_filter = ['role', 'status']
    fieldsets = UserAdmin.fieldsets + (
        ('Internal Role Info', {'fields': ('role', 'status')}),
    )


admin.site.register(User, CustomUserAdmin)