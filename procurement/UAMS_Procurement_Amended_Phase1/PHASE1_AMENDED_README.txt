UAMS PROCUREMENT — AMENDED PHASE 1
==================================

THIS PACKAGE REPLACES THE EARLIER PHASE 1 DATABASE ASSUMPTIONS.

WHY THIS VERSION
----------------
The earlier models were sufficient for workflow testing but were not
sufficient to reproduce the official Noting Sheet and EAS Word formats.

This amended phase implements the correct data foundation for:

1. Approved Requirement / Procurement Case
2. Structured GeM Survey and repeatable survey items
3. Official Noting Sheet data requirements
4. Official EAS data requirements
5. Account Officer review followed by CFA approval
6. Finance-ledger fund-position snapshots
7. Future DOCX/PDF generation fields

IMPORTANT
---------
Do not copy phase1_models.py directly over models.py.

It contains:
- Complete NEW classes: GeMSurvey, GeMSurveyItem, EASItem.
- A reusable approval mixin.
- Clearly labelled field blocks to MERGE into existing NotingSheet and EAS.

Your existing NotingSheet and EAS contain old fields and existing data.
They must be extended, not blindly replaced.

INSTALLATION ORDER
------------------
1. Back up the complete project and db.sqlite3.
2. Merge the model additions into procurement/models.py.
3. Merge forms_phase1.py into procurement/forms.py.
4. Merge services_phase1.py into procurement/services.py.
5. Copy migration 0006 only after models.py matches it.
6. Append the CSS to static/css/style.css.
7. Run:

   python manage.py check
   python manage.py makemigrations --check
   python manage.py migrate
   python manage.py check

8. Do not continue if makemigrations --check reports model differences.
   Send the output before proceeding.

MIGRATION SAFETY
----------------
The migration adds compatibility fields as nullable/blank for existing
records. It does not delete existing Noting Sheet or EAS data.

A later hardening migration will make mandatory fields non-null after
existing records are completed.

PHASE 1 USER FLOW
-----------------
Approved Requirement
→ Procurement Case
→ GeM Survey
→ Select Survey Item
→ Noting Sheet
→ AO Review
→ CFA Approval
→ EAS
→ AO Review
→ CFA Approval

NOT INCLUDED YET
----------------
Phase 2:
- Purchase document registry
- Convening Order
- Inspection Note
- CRAC
- CRV

Phase 3:
- Contingent Bill
- Payment
- Automatic fund posting
- Reports
- Case closure
- Full audit actions

SOURCE-OF-TRUTH RULE
--------------------
Requirement data is reused by Procurement Case.
Survey data is reused by Noting Sheet.
Noting Sheet and Survey data are reused by EAS.
Financial figures are captured from the ledger as a dated snapshot.
Approved document data must not be silently changed.
