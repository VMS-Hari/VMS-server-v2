from django.urls import path
from . import views,roleviews, rolepermissionviews, usercreationviews, sitetypeviews, sitemodelviews, categoryviews, sitecreationviews, tenantcreationviews, identitytypeviews, keycreationviews, visitortypeviews, passcreationviews,tenantnotificationviews,visitorcontructorcreationsviews,bancreationviews, approvalviews, preregistrationcreationviews, preregistrationapprovedviews, reportviews, bulkpreregistrationviews,  dashboardviews, logviews

urlpatterns = [
    path("accounts/login/", views.login_api, name="login"),
    path("accounts/logout/",views.logout_api,name="logout"),
    path("accounts/my-permissions/", rolepermissionviews.my_permissions_api, name="my-permissions"),

    path("roles/create/", roleviews.role_create_api, name="role-create"),
    path("roles/list/", roleviews.role_list_api, name="role-list"),
    path("roles/update/", roleviews.role_update_api, name="role-update"),
    path("roles/delete/", roleviews.role_delete_api, name="role-delete"),

    path("role-permissions/get/", rolepermissionviews.role_permission_get_api, name="role-permission-get"),
    path("role-permissions/save/", rolepermissionviews.role_permission_save_api, name="role-permission-save"),


    path("users/create/", usercreationviews.user_create_api, name="user-create"),
    path("users/list/", usercreationviews.user_list_api, name="user-list"),
    path("users/update/", usercreationviews.user_update_api, name="user-update"),
    path("users/delete/", usercreationviews.user_delete_api, name="user-delete"),


    path("site-types/create/", sitetypeviews.site_type_create_api, name="site-type-create"),
    path("site-types/list/", sitetypeviews.site_type_list_api, name="site-type-list"),
    path("site-types/update/", sitetypeviews.site_type_update_api, name="site-type-update"),
    path("site-types/delete/", sitetypeviews.site_type_delete_api, name="site-type-delete"),

    path("site-models/create/", sitemodelviews.site_model_create_api, name="site-model-create"),
    path("site-models/list/", sitemodelviews.site_model_list_api, name="site-model-list"),
    path("site-models/update/", sitemodelviews.site_model_update_api, name="site-model-update"),
    path("site-models/delete/", sitemodelviews.site_model_delete_api, name="site-model-delete"),

    path("categories/create/", categoryviews.category_create_api, name="category-create"),
    path("categories/list/", categoryviews.category_list_api, name="category-list"),
    path("categories/update/", categoryviews.category_update_api, name="category-update"),
    path("categories/delete/", categoryviews.category_delete_api, name="category-delete"),

    path("sites/create/", sitecreationviews.site_create_api, name="site-create"),
    path("sites/list/", sitecreationviews.site_list_api, name="site-list"),
    path("sites/update/", sitecreationviews.site_update_api, name="site-update"),
    path("sites/delete/", sitecreationviews.site_delete_api, name="site-delete"),
    path("sites/parent-list/", sitecreationviews.site_parent_list_api, name="site-parent-list"),
    path("sites/dropdown/", sitecreationviews.site_dropdown_api, name="site-dropdown"),


    path("tenants/create/", tenantcreationviews.tenant_create_api, name="tenant-create"),
    path("tenants/list/", tenantcreationviews.tenant_list_api, name="tenant-list"),
    path("tenants/update/", tenantcreationviews.tenant_update_api, name="tenant-update"),
    path("tenants/delete/", tenantcreationviews.tenant_delete_api, name="tenant-delete"),


    path("tenant-notifications/create/", tenantnotificationviews.tenant_notification_create_api, name="tenant-notification-create"),
    path("tenant-notifications/list/", tenantnotificationviews.tenant_notification_list_api, name="tenant-notification-list"),
    path("tenant-notifications/update/", tenantnotificationviews.tenant_notification_update_api, name="tenant-notification-update"),
    path("tenant-notifications/delete/", tenantnotificationviews.tenant_notification_delete_api, name="tenant-notification-delete"),
    path("tenant-notifications/check-availability/", tenantnotificationviews.tenant_availability_check_api, name="tenant-notification-check-availability"),

    path("identity-types/create/", identitytypeviews.identity_type_create_api, name="identity-type-create"),
    path("identity-types/list/", identitytypeviews.identity_type_list_api, name="identity-type-list"),
    path("identity-types/update/", identitytypeviews.identity_type_update_api, name="identity-type-update"),
    path("identity-types/delete/", identitytypeviews.identity_type_delete_api, name="identity-type-delete"),


    path("keys/create/", keycreationviews.key_create_api, name="key-create"),
    path("keys/list/", keycreationviews.key_list_api, name="key-list"),
    path("keys/update/", keycreationviews.key_update_api, name="key-update"),
    path("keys/delete/", keycreationviews.key_delete_api, name="key-delete"),


    path("visitor-types/create/", visitortypeviews.visitor_type_create_api, name="visitor-type-create"),
    path("visitor-types/update/", visitortypeviews.visitor_type_update_api, name="visitor-type-update"),
    path("visitor-types/list/", visitortypeviews.visitor_type_list_api, name="visitor-type-list"),
    path("visitor-types/delete/", visitortypeviews.visitor_type_delete_api, name="visitor-type-delete"),


    path("passes/create/", passcreationviews.pass_create_api, name="pass-create"),
    path("passes/update/", passcreationviews.pass_update_api, name="pass-update"),
    path("passes/delete/", passcreationviews.pass_delete_api, name="pass-delete"),
    path("passes/list/", passcreationviews.pass_list_api, name="pass-list"),


    path("visitors/check-in/", visitorcontructorcreationsviews.visitor_check_in_api, name="visitor-check-in"),
    path("visitors/list/", visitorcontructorcreationsviews.visitor_list_api, name="visitor-list"),
    path("visitors/check-out/", visitorcontructorcreationsviews.visitor_check_out_api, name="visitor-check-out"),
    path("visitors/identity-search/", visitorcontructorcreationsviews.visitor_identity_search_api, name="visitor-identity-search"),
    path("visitors/pass-lookup/", visitorcontructorcreationsviews.visitor_pass_lookup_api, name="visitor-pass-lookup"),


    path("bans/create/", bancreationviews.ban_create_api, name="ban-create"),
    path("bans/list/", bancreationviews.ban_list_api, name="ban-list"),
    path("bans/update/", bancreationviews.ban_update_api, name="ban-update"),
    path("bans/lift/", bancreationviews.ban_lift_api, name="ban-lift"),
    path("bans/delete/", bancreationviews.ban_delete_api, name="ban-delete"),


    # approvers of a site (users whose role has the Approval menu enabled)
    path("approvals/approvers/", approvalviews.approver_list_api, name="approver-list"),



    # pre-registration
    path("pre-registrations/create/", preregistrationcreationviews.pre_registration_create_api, name="pre-registration-create"),
    path("pre-registrations/list/", preregistrationcreationviews.pre_registration_list_api, name="pre-registration-list"),
    path("pre-registrations/update/", preregistrationcreationviews.pre_registration_update_api, name="pre-registration-update"),
    path("pre-registrations/delete/", preregistrationcreationviews.pre_registration_delete_api, name="pre-registration-delete"),
    path("pre-registrations/approved-list/", preregistrationapprovedviews.pre_registration_approved_list_api, name="pre-registration-approved-list"),
    path("pre-registrations/approved-check-in/", preregistrationapprovedviews.pre_registration_check_in_api, name="pre-registration-approved-check-in"),
    path("pre-registrations/bulk-check-in/", preregistrationapprovedviews.pre_registration_bulk_check_in_api, name="pre-registration-bulk-check-in"),
    path("pre-registrations/bulk-check-out/", preregistrationapprovedviews.pre_registration_bulk_check_out_api, name="pre-registration-bulk-check-out"),

    # approval
    path("approvals/approvers/", approvalviews.approver_list_api, name="approver-list"),
    path("approvals/list/", approvalviews.approval_list_api, name="approval-list"),
    path("approvals/history/", approvalviews.approval_history_api, name="approval-history"),
    path("approvals/action/", approvalviews.approval_action_api, name="approval-action"),
    path("approvals/bulk-action/", approvalviews.approval_bulk_action_api, name="approval-bulk-action"),

    # report
    path("reports/list/", reportviews.report_list_api, name="report-list"),

    # bulk pre-registration
    path("bulk-pre-registrations/validate/", bulkpreregistrationviews.bulk_pre_registration_validate_api, name="bulk-pre-registration-validate"),
    path("bulk-pre-registrations/create/", bulkpreregistrationviews.bulk_pre_registration_create_api, name="bulk-pre-registration-create"),
    path("bulk-pre-registrations/approved-list/", bulkpreregistrationviews.bulk_pre_registration_approved_list_api, name="bulk-pre-registration-approved-list"),
    path("bulk-pre-registrations/bulk-ids/", bulkpreregistrationviews.bulk_id_list_api, name="bulk-pre-registration-bulk-ids"),


    # ---------------- dashboard ----------------
    path("dashboard/summary/", dashboardviews.dashboard_summary_api, name="dashboard-summary"),
    path("dashboard/not-checked-out/", dashboardviews.dashboard_not_checked_out_api, name="dashboard-not-checked-out"),

    # log details api
    path("logs/list/", logviews.log_list_api, name="log-list"),
]