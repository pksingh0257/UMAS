from django.db import models
from core_base.models import CoreModel


class Unit(CoreModel):
    """
    Internal unit/section that raises requirements and is referenced
    across Requirement, Procurement, and Fund modules. (Blueprint 14.4)
    """

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    contact_officer = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_units"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class FundHead(CoreModel):
    """
    Top-level fund classification (e.g. Public Fund, Regimental Fund).
    Referenced by SubHead, Requirement Items, and Fund Management.
    """

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_fund_heads"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SubHead(CoreModel):
    """
    Sub-classification under a FundHead (e.g. under 'Public Fund':
    'Stores', 'Equipment', 'Maintenance').
    """

    fund_head = models.ForeignKey(
        FundHead, on_delete=models.PROTECT, related_name="sub_heads"
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_sub_heads"
        ordering = ["fund_head__name", "name"]
        unique_together = ("fund_head", "code")
        verbose_name_plural = "Sub Heads"

    def __str__(self):
        return f"{self.fund_head.code} / {self.name}"


class ItemCategory(CoreModel):
    """
    Classification for Requirement Items (e.g. Stationery, IT Equipment,
    Vehicle Spares). Used for reporting and procurement grouping.
    """

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "md_item_categories"
        ordering = ["name"]
        verbose_name_plural = "Item Categories"

    def __str__(self):
        return self.name
