import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from core_base.models import CoreModel
from masterdata.models import FundHead
from requirements_mgmt.models import Requirement   # CHANGED: RequirementItem no longer exists


class ProcurementCase(CoreModel):
    """
    The central entity of Project Nexus (Section 16). Exactly one case is
    generated per Requirement (flattened model - previously per Requirement
    Item, back when Requirements had multiple items). The current_stage
    field IS the Workflow Engine's state (Section 17) - implemented here
    as a service layer on the model rather than as separate user-facing
    screens.
    """

    STAGE_CHOICES = [
        ("SURVEY", "Survey"),
        ("BID_BOQ", "Bid / BOQ"),
        ("NOTING", "Noting"),
        ("APPROVAL", "Approval"),
        ("EAS", "EAS"),
        ("SANCTION", "Sanction"),
        ("GEM_ORDER", "GeM Order / Contract"),
        ("INSPECTION", "Inspection"),
        ("CRAC", "CRAC"),
        ("CRV", "CRV"),
        ("PAYMENT_TRACKING", "Payment Tracking"),
        ("CASE_CLOSED", "Case Closed"),
        ("RETURNED", "Returned for Correction"),
    ]

    STAGE_SEQUENCE = [
        "SURVEY",
        "BID_BOQ",
        "NOTING",
        "APPROVAL",
        "EAS",
        "SANCTION",
        "GEM_ORDER",
        "INSPECTION",
        "CRAC",
        "CRV",
        "PAYMENT_TRACKING",
        "CASE_CLOSED",
    ]

    CFA_ONLY_STAGES = {"APPROVAL", "EAS", "SANCTION"}

    case_number = models.CharField(max_length=30, unique=True, editable=False)

    # CHANGED: was OneToOneField(RequirementItem, ...). requirements_mgmt
    # flattened RequirementRequest+RequirementItem into a single
    # `Requirement` model, so this now points there instead. Field NAME
    # is left as `requirement_item` on purpose, to avoid breaking any
    # other code in the project that already references
    # `case.requirement_item` — rename it to `requirement` later if you
    # do a project-wide search/replace.
    requirement_item = models.OneToOneField(
        Requirement, on_delete=models.PROTECT, related_name="procurement_case"
    )

    current_stage = models.CharField(
        max_length=20, choices=STAGE_CHOICES, default="SURVEY"
    )

    fund_head = models.ForeignKey(
        FundHead,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="procurement_cases",
    )
    sanctioned_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )

    survey_notes = models.TextField(blank=True, null=True)
    bid_boq_details = models.TextField(blank=True, null=True)
    comparative_statement = models.TextField(blank=True, null=True)
    noting_text = models.TextField(blank=True, null=True)
    approval_decision = models.TextField(blank=True, null=True)
    eas_reference = models.CharField(max_length=100, blank=True, null=True)
    sanction_order_number = models.CharField(max_length=100, blank=True, null=True)
    gem_order_reference = models.CharField(max_length=100, blank=True, null=True)
    inspection_notes = models.TextField(blank=True, null=True)
    crac_reference = models.CharField(max_length=100, blank=True, null=True)
    crv_reference = models.CharField(max_length=100, blank=True, null=True)

    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "proc_procurement_cases"
        ordering = ["-created_at"]
        verbose_name = "Procurement Case"
        verbose_name_plural = "Procurement Cases"

    def __str__(self):
        return self.case_number

    def save(self, *args, **kwargs):
        if not self.case_number:
            yr = timezone.now().year
            last = (
                ProcurementCase.all_objects.filter(case_number__startswith=f"PC-{yr}-")
                .order_by("-case_number")
                .first()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.case_number.split("-")[-1]) + 1
                except ValueError:
                    seq = 1
            self.case_number = f"PC-{yr}-{seq:05d}"
        super().save(*args, **kwargs)

    STAGE_REQUIRED_FIELDS = {
        "SURVEY": ["survey_notes"],
        "BID_BOQ": ["bid_boq_details", "comparative_statement"],
        "NOTING": ["noting_text"],
        "APPROVAL": ["approval_decision"],
        "EAS": ["eas_reference"],
        "SANCTION": ["sanction_order_number", "fund_head", "sanctioned_amount"],
        "GEM_ORDER": ["gem_order_reference"],
        "INSPECTION": ["inspection_notes"],
        "CRAC": ["crac_reference"],
        "CRV": ["crv_reference"],
    }

    def _check_stage_complete(self, stage):
        required = self.STAGE_REQUIRED_FIELDS.get(stage, [])
        missing = [f for f in required if not getattr(self, f)]
        if missing:
            raise ValidationError(
                f"Cannot leave stage '{stage}': missing mandatory field(s) {', '.join(missing)}."
            )

    def advance(self, user, remarks=None):
        """
        Move the case to the next stage in STAGE_SEQUENCE. Enforces:
        - mandatory data for the current stage must exist (Section 16/17)
        - transitions cannot skip stages (Section 17)
        - CFA-only stages can only be advanced INTO by a CFA user (Section 11/17)
        """
        if self.current_stage == "CASE_CLOSED":
            raise ValidationError("This case is already closed.")

        self._check_stage_complete(self.current_stage)

        idx = self.STAGE_SEQUENCE.index(self.current_stage)
        next_stage = self.STAGE_SEQUENCE[idx + 1]

        if next_stage in self.CFA_ONLY_STAGES and getattr(user, "role", None) != "CFA":
            raise ValidationError(
                f"Only a user with the CFA role may advance a case into '{next_stage}'."
            )

        if next_stage == "SANCTION" and not self.fund_head_id:
            raise ValidationError(
                "A Fund must be linked before a case can enter Sanction."
            )

        from_stage = self.current_stage
        self.current_stage = next_stage
        if next_stage == "CASE_CLOSED":
            self.is_closed = True
            self.closed_at = timezone.now()
        self.modified_by = user
        self.save()

        CaseStageHistory.objects.create(
            case=self,
            from_stage=from_stage,
            to_stage=next_stage,
            action="ADVANCE",
            performed_by=user,
            remarks=remarks or "",
        )

    def return_to_stage(self, user, target_stage, reason):
        """
        A returned/rejected case reverts to a specified earlier stage, with
        the reason permanently recorded (Section 17) - never silently overwritten.
        """
        if target_stage not in self.STAGE_SEQUENCE:
            raise ValidationError("Invalid target stage for return.")
        if not reason:
            raise ValidationError("A reason is required when returning a case.")

        from_stage = self.current_stage
        self.current_stage = target_stage
        self.modified_by = user
        self.save()

        CaseStageHistory.objects.create(
            case=self,
            from_stage=from_stage,
            to_stage=target_stage,
            action="RETURN",
            performed_by=user,
            remarks=reason,
        )


class CaseStageHistory(CoreModel):
    """
    The case's permanent timeline (Section 17). Append-only by convention -
    rows are never edited or deleted, only added, so the full history of
    every transition (including returns/rejections) is always preserved.
    """

    ACTION_CHOICES = [
        ("ADVANCE", "Advanced"),
        ("RETURN", "Returned"),
    ]

    case = models.ForeignKey(
        ProcurementCase, on_delete=models.PROTECT, related_name="history"
    )
    from_stage = models.CharField(max_length=20)
    to_stage = models.CharField(max_length=20)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        "authentication.User", on_delete=models.PROTECT, related_name="case_transitions"
    )
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "proc_case_stage_history"
        ordering = ["created_at"]
        verbose_name = "Case Stage History"
        verbose_name_plural = "Case Stage History"

    def __str__(self):
        return f"{self.case.case_number}: {self.from_stage} -> {self.to_stage}"


class NotingSheet(models.Model):
    """
    Created by a Clerk/Head Clerk against an APPROVED Requirement, to move
    it into procurement. One Requirement -> at most one Noting Sheet
    (OneToOne). Its own AO -> CFA approval mirrors requirements_mgmt's
    Requirement model exactly, on purpose, for consistency.

    Item Name / Qty / Unit Price are NOT duplicated here — they're read
    live off the linked Requirement via properties below, since they're
    locked once the Requirement is APPROVED anyway.
    """

    WORKFLOW_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING_AO", "Pending Account Officer"),
        ("AO_DENIED", "Returned by Account Officer"),
        ("PENDING_CFA", "Pending CFA"),
        ("CFA_DENIED", "Returned by CFA"),
        ("APPROVED", "Approved"),
    ]
    DECISION_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("DENIED", "Denied"),
    ]

    noting_id = models.CharField(max_length=30, unique=True, editable=False)

    requirement = models.OneToOneField(
        "requirements_mgmt.Requirement",
        on_delete=models.PROTECT,
        related_name="noting_sheet",
    )

    # A/U = unit of measure (Nos, Set, Kg, ...) — plain manual text entry.
    au = models.CharField(max_length=50, verbose_name="A/U")

    # Fund ledger snapshot — manually entered (no live Fund model wired in
    # yet). Balance is calculated, not stored, to avoid drift.
    amount_allotted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_released = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_expended = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.PROTECT, related_name="noting_sheets_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    workflow_status = models.CharField(max_length=20, choices=WORKFLOW_CHOICES, default="DRAFT")

    ao_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    ao_remarks = models.TextField(blank=True, null=True)
    ao_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="noting_sheets_ao_reviewed",
    )
    ao_acted_at = models.DateTimeField(null=True, blank=True)

    cfa_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    cfa_remarks = models.TextField(blank=True, null=True)
    cfa_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="noting_sheets_cfa_reviewed",
    )
    cfa_acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "proc_noting_sheets"
        ordering = ["-created_at"]
        verbose_name = "Noting Sheet"
        verbose_name_plural = "Noting Sheets"

    def __str__(self):
        return self.noting_id

    # ---- Read-only pass-through fields from the Requirement ----
    @property
    def item_name(self):
        return self.requirement.item_name

    @property
    def qty(self):
        return self.requirement.quantity

    @property
    def unit_price(self):
        return self.requirement.estimated_cost

    @property
    def approx_amount(self):
        """Qty * Unit Price. estimated_cost is stored as text, so this can
        fail if a non-numeric value was ever entered — returns None rather
        than crashing the page in that case."""
        try:
            return self.qty * float(self.unit_price)
        except (TypeError, ValueError):
            return None

    @property
    def balance_amount(self):
        return self.amount_allotted - self.amount_expended

    @property
    def is_editable(self):
        return self.workflow_status in ("DRAFT", "AO_DENIED", "CFA_DENIED")

    @property
    def simple_approval_status(self):
        if self.workflow_status == "APPROVED":
            return "Approved"
        if self.workflow_status in ("AO_DENIED", "CFA_DENIED"):
            return "Declined"
        return "Pending"

    def save(self, *args, **kwargs):
        if not self.noting_id:
            yr = timezone.now().year
            last = (
                NotingSheet.objects.filter(noting_id__startswith=f"NS-{yr}-")
                .order_by("-noting_id")
                .first()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.noting_id.split("-")[-1]) + 1
                except ValueError:
                    seq = 1
            self.noting_id = f"NS-{yr}-{seq:05d}"
        super().save(*args, **kwargs)

    # ---- Workflow transitions (identical pattern to Requirement) ----

    def submit_to_ao(self):
        if not self.is_editable:
            raise ValidationError("This noting sheet is not currently submittable.")
        self.workflow_status = "PENDING_AO"
        self.ao_status = "PENDING"
        self.ao_remarks = None
        self.ao_acted_by = None
        self.ao_acted_at = None
        self.save()

    def ao_decide(self, user, decision, remarks=""):
        if self.workflow_status != "PENDING_AO":
            raise ValidationError("This noting sheet is not awaiting Account Officer review.")
        self.ao_status = decision
        self.ao_remarks = remarks
        self.ao_acted_by = user
        self.ao_acted_at = timezone.now()
        if decision == "APPROVED":
            self.workflow_status = "PENDING_CFA"
        elif decision == "DENIED":
            self.workflow_status = "AO_DENIED"
        self.save()

    def cfa_decide(self, user, decision, remarks=""):
        if self.workflow_status != "PENDING_CFA":
            raise ValidationError("This noting sheet is not awaiting CFA review.")
        self.cfa_status = decision
        self.cfa_remarks = remarks
        self.cfa_acted_by = user
        self.cfa_acted_at = timezone.now()
        if decision == "APPROVED":
            self.workflow_status = "APPROVED"
        elif decision == "DENIED":
            self.workflow_status = "CFA_DENIED"
        self.save()