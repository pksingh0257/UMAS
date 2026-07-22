import uuid
from django.db import models
from django.conf import settings


class SoftDeleteManager(models.Manager):
    """Default manager: excludes soft-deleted rows from every normal query."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Escape hatch manager: includes soft-deleted rows too, for admin/audit use."""

    def get_queryset(self):
        return super().get_queryset()


class CoreModel(models.Model):
    """
    Abstract base model. Every business model in Project Nexus inherits this
    so that audit timestamps and soft-delete are enforced uniformly, per the
    Software Design Blueprint (Section 14.1 - Core Module).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        related_name='%(class)s_created',
        on_delete=models.SET_NULL,
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        related_name='%(class)s_modified',
        on_delete=models.SET_NULL,
    )

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Never physically delete a row — mark it instead, per business rule (Section 6/9)."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None:
            self.modified_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'modified_by', 'modified_at'])