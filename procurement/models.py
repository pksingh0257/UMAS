import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
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
    Rebuilt to match the official Noting Sheet document format (File No,
    Branch, Sheet No, Dated, Financial Year, two narrative paragraphs, a
    repeatable item table via NotingSheetItem, fund figures, and a
    For-Approval block). Approval stays CFA-ONLY, matching your real
    design — submit_for_approval() sends straight to PENDING_CFA.
    ao_decide()/PENDING_AO/AO_DENIED are kept only as legacy/unused, same
    as your EAS model already does, for consistency.
    """

    WORKFLOW_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING_AO", "Pending Account Officer"),   # legacy, unreachable
        ("AO_DENIED", "Returned by Account Officer"),  # legacy, unreachable
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

    # ---- File Details ----
    file_no = models.CharField(max_length=100)
    branch = models.CharField(max_length=100, default="Acct Branch")
    sheet_no = models.CharField(max_length=50, default="One of One")
    dated = models.DateField()

    # ---- Branch & Financial Year ----
    financial_year = models.CharField(max_length=20, help_text="e.g. 2026-27")

    # ---- Noting / Details ----
    paragraph_1 = models.CharField(max_length=500, verbose_name="Paragraph 1 (Purport / Subject)")
    paragraph_2 = models.TextField(max_length=1000, verbose_name="Paragraph 2 (Requirement / Justification)")

    # ---- Fund Details ----
    amount_allotted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_released = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_expended = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    remarks = models.CharField(max_length=500, blank=True)

    approval_recipient = models.CharField(
        max_length=100, blank=True,
        help_text='Free text, e.g. "CFA (CO)" — who this is being sent to.',
    )

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

    @property
    def item_name(self):
        first_item = self.items.first()
        return first_item.description if first_item else self.requirement.item_name

    @property
    def total_amount(self):
        return sum((item.approx_amount or 0) for item in self.items.all())

    @property
    def balance_amount(self):
        # CHANGED: was `amount_allotted - amount_expended`. Per
        # finance_utils.get_fund_balance()'s own docstring, `released` —
        # not `allotted` — represents the current available balance
        # (allotted is the gross total ever credited, before subtracting
        # anything already spent). Balance Held should reflect what's
        # actually still available, so it's Released minus what this
        # sheet expends.
        return self.amount_released - self.amount_expended

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

    # ---- Workflow transitions — CFA-only, matches your real design ----

    def submit_for_approval(self):
        if not self.is_editable:
            raise ValidationError("This noting sheet is not currently submittable.")
        self.workflow_status = "PENDING_CFA"
        self.cfa_status = "PENDING"
        self.cfa_remarks = None
        self.cfa_acted_by = None
        self.cfa_acted_at = None
        self.save()

    def ao_decide(self, user, decision, remarks=""):
        # LEGACY — unreachable from the current flow.
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


class NotingSheetItem(models.Model):
    """A single row in the Item Details table — repeatable, unlike the
    old single-item version tied directly to the Requirement."""

    noting_sheet = models.ForeignKey(NotingSheet, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=250, verbose_name="Item Description")
    au = models.CharField(max_length=50, verbose_name="A/U")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "proc_noting_sheet_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    @property
    def approx_amount(self):
        return self.quantity * self.unit_price


class EAS(models.Model):
    """
    Expenditure/Approval Sanction sheet — created once a NotingSheet is
    fully CFA-approved (mirrors your mockup: "Create EAS" only appears
    then). One NotingSheet -> at most one EAS (OneToOne). Uses the
    identical CFA-only workflow as NotingSheet, on purpose, for
    consistency.

    file_no / eas_id are plain EDITABLE TEXT for now, not auto-generated —
    switch these to an auto-numbering save() (like Requirement/NotingSheet
    use) once the exact numbering scheme is confirmed.
    """

    WORKFLOW_CHOICES = NotingSheet.WORKFLOW_CHOICES
    DECISION_CHOICES = NotingSheet.DECISION_CHOICES

    noting_sheet = models.OneToOneField(
        NotingSheet, on_delete=models.PROTECT, related_name="eas"
    )

    file_no = models.CharField(max_length=100, verbose_name="File No")
    eas_id = models.CharField(max_length=100, verbose_name="EAS ID")

    dsc_goods = models.CharField(max_length=250, verbose_name="DSC (Description) of Goods")
    name_supplier = models.CharField(max_length=250, verbose_name="Name of Supplier")
    purpose_broad = models.CharField(max_length=250, verbose_name="Purpose - Broad")
    designation_cfa = models.CharField(max_length=150, verbose_name="Designation of CFA")
    qty_sanctioned = models.PositiveIntegerField(verbose_name="Qty Sanctioned")
    amount_sanction = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Amount Sanction")
    cost_per_unit = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Cost Per Unit")
    other_charges = models.CharField(
        max_length=250, blank=True, null=True,
        verbose_name="Other Associated Charges (e.g. freight)",
    )
    total_amount_words = models.CharField(max_length=500, verbose_name="Total Amount (in words)")

    availability_fund = models.CharField(max_length=250, verbose_name="Availability of Fund")
    sub_details_heads = models.CharField(max_length=250, verbose_name="Sub Details / Heads")

    # NEW: plain text, filled in by the user — no choices/lookup, just
    # free entry per your instruction.
    major = models.CharField(max_length=150, blank=True, null=True, verbose_name="Major")
    minor = models.CharField(max_length=150, blank=True, null=True, verbose_name="Minor")

    reference_no = models.CharField(max_length=150, verbose_name="Reference No")
    name_paying_agent = models.CharField(max_length=250, verbose_name="Name of Paying Agency")
    date_time = models.DateField(verbose_name="Date")
    station = models.CharField(max_length=150)

    unit = models.CharField(max_length=150, verbose_name="Unit")

    type_id = models.CharField(max_length=50, blank=True, default="")
    status_id = models.IntegerField(default=0)

    sanction_document = models.FileField(
        upload_to="eas_documents/sanction/", null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    contract_document = models.FileField(
        upload_to="eas_documents/contract/", null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    invoice_document = models.FileField(
        upload_to="eas_documents/invoice/", null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )

    created_by = models.ForeignKey(
        "authentication.User", on_delete=models.PROTECT, related_name="eas_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    workflow_status = models.CharField(max_length=20, choices=WORKFLOW_CHOICES, default="DRAFT")

    ao_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    ao_remarks = models.TextField(blank=True, null=True)
    ao_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="eas_ao_reviewed",
    )
    ao_acted_at = models.DateTimeField(null=True, blank=True)

    cfa_status = models.CharField(max_length=10, choices=DECISION_CHOICES, default="PENDING")
    cfa_remarks = models.TextField(blank=True, null=True)
    cfa_acted_by = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="eas_cfa_reviewed",
    )
    cfa_acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "proc_eas"
        ordering = ["-created_at"]
        verbose_name = "EAS"
        verbose_name_plural = "EAS"

    def __str__(self):
        return self.eas_id or f"EAS #{self.pk}"

    @property
    def case_file_no(self):
        return self.file_no

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

    def submit_for_approval(self):
        if not self.is_editable:
            raise ValidationError("This EAS is not currently submittable.")
        self.workflow_status = "PENDING_CFA"
        self.cfa_status = "PENDING"
        self.cfa_remarks = None
        self.cfa_acted_by = None
        self.cfa_acted_at = None
        self.save()

    def ao_decide(self, user, decision, remarks=""):
        # LEGACY — unreachable from the current flow.
        if self.workflow_status != "PENDING_AO":
            raise ValidationError("This EAS is not awaiting Account Officer review.")
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
            raise ValidationError("This EAS is not awaiting CFA review.")
        self.cfa_status = decision
        self.cfa_remarks = remarks
        self.cfa_acted_by = user
        self.cfa_acted_at = timezone.now()
        if decision == "APPROVED":
            self.workflow_status = "APPROVED"
        elif decision == "DENIED":
            self.workflow_status = "CFA_DENIED"
        self.save()

class ConveningOrder(models.Model):
    convening_order_id = models.CharField(max_length=30, unique=True, editable=False)

    procurement_case = models.OneToOneField(
        ProcurementCase,
        on_delete=models.PROTECT,
        related_name="convening_order",
    )

    description = models.TextField(verbose_name="Convening Order Description")

    presiding_officer = models.CharField(max_length=250)
    member_1 = models.CharField(max_length=250)
    member_2 = models.CharField(max_length=250)

    completion_date = models.DateField(null=True, blank=True)

    two_ic_name = models.CharField(max_length=150)
    two_ic_rank = models.CharField(max_length=100)
    two_ic_appointment = models.CharField(max_length=100, default="2IC")

    order_date = models.DateField(default=timezone.localdate, verbose_name="Date")

    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="convening_orders_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "proc_convening_orders"
        ordering = ["-created_at"]

    def __str__(self):
        return self.convening_order_id

    def save(self, *args, **kwargs):
        if not self.convening_order_id:
            yr = timezone.now().year
            last = (
                ConveningOrder.objects
                .filter(convening_order_id__startswith=f"CO-{yr}-")
                .order_by("-convening_order_id")
                .first()
            )
            seq = 1
            if last:
                try:
                    seq = int(last.convening_order_id.split("-")[-1]) + 1
                except (TypeError, ValueError):
                    seq = 1
            self.convening_order_id = f"CO-{yr}-{seq:05d}"
        super().save(*args, **kwargs)

    @property
    def requirement(self):
        return self.procurement_case.requirement_item

    @property
    def eas(self):
        try:
            return self.requirement.noting_sheet.eas
        except AttributeError:
            return None

    @property
    def file_no(self):
        return self.eas.file_no if self.eas else ""

    @property
    def requirement_id_text(self):
        return getattr(self.requirement, "requirement_id", "")
