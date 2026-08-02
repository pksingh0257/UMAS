from django.urls import path

from . import views


app_name = "finance"


urlpatterns = [
    # Funds Dashboard / Detail pages
    path(
        "funds/",
        views.fund_dashboard,
        name="fund-dashboard",
    ),
    path(
        "funds/<uuid:pk>/",
        views.fund_head_detail,
        name="fund-head-detail",
    ),
    path(
        "funds/sub-head/<uuid:pk>/",
        views.sub_head_detail,
        name="sub-head-detail",
    ),

    # Fund Entries (workflow: create -> submit -> CFA decision)
    path(
        "fund-entries/",
        views.fund_entry_list,
        name="fund-entry-list",
    ),
    path(
        "fund-entries/create/",
        views.fund_entry_create,
        name="fund-entry-create",
    ),
    path(
        "fund-entries/<uuid:pk>/",
        views.fund_entry_detail,
        name="fund-entry-detail",
    ),
    path(
        "fund-entries/<uuid:pk>/submit/",
        views.fund_entry_submit,
        name="fund-entry-submit",
    ),
    path(
        "fund-entries/<uuid:pk>/cfa-decision/",
        views.fund_entry_cfa_decision,
        name="fund-entry-cfa-decision",
    ),
]