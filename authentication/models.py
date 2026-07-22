from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    ROLE_CHOICES = [
        ('HEAD_CLERK', 'Head Clerk'),
        ('ACCOUNTS_CLERK', 'Accounts Clerk'),
        ('ACCOUNTS_JCO', 'Accounts JCO'),
        ('ACCOUNTS_OFFICER', 'Accounts Officer'),
        ('CFA', 'Competent Financial Authority (CFA)'),
        ('ADMINISTRATOR', 'Administrator'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('INACTIVE', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='ACCOUNTS_CLERK')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    class Meta:
        db_table = 'uams_users'