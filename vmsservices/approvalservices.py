# from .models import Site, User
# from .rolepermissionservices import user_can_view_site

# # menu_key of the "Approval" page, exactly as it is stored in
# # RolePermission.menu_key (the key your sidebar / role-permission screen uses).
# # CHANGE THIS if your approval page uses a different key.
# APPROVAL_MENU_KEY = "/approval"

# # menu_key of the Pre-Registration page (used for the sub-site access check)
# PRE_REGISTRATION_MENU_KEY = "/pre-registration"


# def _serialize(obj):
#     return {
#         "id": obj.id,
#         "full_name": f"{obj.first_name} {obj.last_name}".strip(),
#         "email": obj.email,
#         "role": {
#             "guid": str(obj.role.guid),
#             "name": obj.role.name,
#         } if obj.role_id else None,
#         "site": {
#             "guid": str(obj.site.guid),
#             "name": obj.site.site_name,
#         } if obj.site_id else None,
#     }


# def list_site_approvers(site_guid, user):
#     """Users of the given site whose role has the Approval menu enabled."""

#     site_obj = Site.objects.filter(guid=site_guid).first()

#     if site_obj is None:
#         return {
#             "success": False,
#             "message": "Selected site does not exist",
#             "status_code": 400,
#         }

#     # Super admin can ask for any site. Everyone else: own site, or a
#     # sub-site they are allowed to view on the Pre-Registration page.
#     if not user.is_super_admin():
#         own = user.site

#         if own is None:
#             return {
#                 "success": False,
#                 "message": "No site is assigned to your account",
#                 "status_code": 403,
#             }

#         if own.pk != site_obj.pk and not user_can_view_site(
#             user, PRE_REGISTRATION_MENU_KEY, str(site_obj.guid)
#         ):
#             return {
#                 "success": False,
#                 "message": "You are not allowed to view this site",
#                 "status_code": 403,
#             }

#     # Both role__permissions__ conditions sit in ONE filter() call, so they
#     # must match the same RolePermission row (right menu AND enabled).
#     qs = (
#         User.objects
#         .filter(
#             is_active=True,
#             is_superuser=False,
#             site=site_obj,
#             role__is_active=True,
#             role__permissions__menu_key=APPROVAL_MENU_KEY,
#             role__permissions__menu_enabled=True,
#         )
#         .select_related("role", "site")
#         .distinct()
#         .order_by("first_name", "last_name", "email")
#     )

#     return {
#         "success": True,
#         "message": "Approvers fetched",
#         "data": {
#             "results": [_serialize(obj) for obj in qs],
#         },
#     }




from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .bancreationservices import is_person_banned
from .models import Contractor, Site, User, Visitor, VisitorType
from .preregistrationmailservices import send_pre_registration_decision_mail
from .rolepermissionservices import can_view_subsites, user_can_view_site

# menu_key of the "Approval" page, exactly as it is stored in
# RolePermission.menu_key. CHANGE THIS if your approval page uses another key.
APPROVAL_MENU_KEY = "/approval"

# menu_key of the Pre-Registration page (sub-site access check)
PRE_REGISTRATION_MENU_KEY = "/pre-registration"

# Rows that belong to the pre-registration / approval flow
PRE_REG_SOURCES = ["PRE_REGISTRATION", "PRE_REGISTRATION_BULK"]

KIND_MODELS = {
    "Visitor": Visitor,
    "Contractor": Contractor,
}

# True  -> only the approver chosen on the request (or a super admin) can decide.
# False -> any user who can access the Approval page for that site can decide.
ASSIGNED_APPROVER_ONLY = False

# False -> a requester cannot approve / reject their own request
#          (super admin is exempt).
# ALLOW_SELF_APPROVAL = False

# NEW: visitor types that live in the Contractor table
COMPANY_VISITOR_TYPES = ("contractor", "contructor")


def _kind_for_visitor_type(visitor_type_guid):
    """NEW: visitor type -> which table holds it. None if the guid is unknown."""
    vt = VisitorType.objects.filter(guid=visitor_type_guid).first()
    if vt is None:
        return None
    return "Contractor" if vt.name.strip().lower() in COMPANY_VISITOR_TYPES else "Visitor"


def _fail(message, status_code=400, field=None):
    result = {"success": False, "message": message, "status_code": status_code}
    if field:
        result["errors"] = {field: [message]}
    return result


# ----------------------------------------------------------------------
# shared helpers (also imported by preregistrationcreationservices.py)
# ----------------------------------------------------------------------

def serialize_request(rec, kind):
    p = rec.person
    return {
        "guid": str(rec.guid),
        "id": rec.id,
        "kind": kind,
        # CHANGED: the type comes from the table, not from a column
        # "visitor_type": {"guid": None, "name": kind},
        "visitor_type": {
            "guid": str(rec.visitor_type.guid),
            "name": rec.visitor_type.name,
        } if rec.visitor_type_id else {"guid": None, "name": kind},
        "person": {
            "id": p.id,
            "person_name": p.person_name,
            "identity_type": p.identity_type,
            "identity_number": p.identity_number,
            "phone_number": p.phone_number,
            "email": p.email,
            "currently_checked_in": p.currently_checked_in,
            "is_banned": p.is_banned,
        },
        "site": {"guid": str(rec.site.guid), "name": rec.site.site_name},
        "location": {
            "guid": str(rec.tenant.guid),
            "name": rec.tenant.tenant_name,
        } if rec.tenant_id else None,
        "company": rec.company,
        "company_phone": rec.company_phone,
        "source": rec.source,
        "bulk_id": rec.bulk_id,
        "approval_status": rec.approval_status,
        # "Pending" / "Approved" / "Rejected"
        "status": (rec.approval_status or "PENDING").title(),
        "requester_email": rec.requester_email,
        "approver_email": rec.approver_email,
        "approved_by": rec.approved_by.email if rec.approved_by_id else None,
        "approved_at": rec.approved_at,
        # CHANGED: model field is approval_remark (JSON key stays the same)
        "decision_remark": rec.approval_remark,
        "from_date": rec.from_date,
        "to_date": rec.to_date,
        "from_time": rec.from_time,
        "to_time": rec.to_time,
        "pass_no": rec.pass_no,
        "key_no": rec.key_no,
        "vehicle_number": rec.vehicle_number,
        "remark": rec.remark,
        "created_at": rec.created_at,
    }


def find_record(guid, lock=False):
    """Looks in the Visitor table, then the Contractor table.
    Returns (record, kind) or (None, None)."""
    for kind, model in KIND_MODELS.items():
        # CHANGED: "visitor_type" removed from select_related
        qs = model.objects.select_related(
            "person", "site", "tenant", "approved_by", "visitor_type"
        )
        if lock:
            qs = qs.select_for_update(of=("self",))
        rec = qs.filter(guid=guid).first()
        if rec is not None:
            return rec, kind
    return None, None


# def site_scope(user, site_guid, menu_key):
def site_scope(user, site_guid, menu_key, include_children_of_selected=True):
    """Returns (Q for the site filter, error_dict_or_None). Same rules as list_visits."""
    include_children = True

    if user is not None and not user.is_super_admin():
        own = user.site

        if own is None:
            return None, _fail("No site is assigned to your account", 403)

        if not site_guid:
            site_guid = str(own.guid)

        if str(site_guid) != str(own.guid) and not user_can_view_site(
            user, menu_key, site_guid
        ):
            return None, _fail("You are not allowed to view this site", 403)

        include_children = can_view_subsites(user, menu_key)

    # if not site_guid:
    #     return Q(), None

    # condition = Q(site__guid=site_guid)
    # if include_children:
    #     condition |= Q(site__parent__guid=site_guid)
    # return condition, None
    if not site_guid:
        return Q(), None

    return Q(site__guid=site_guid), None


def _build_qs(model, scope_q, search, status, from_date, to_date,
              statuses=None, decided_from=None, decided_to=None):
    # CHANGED: "visitor_type" removed from select_related, and the
    # visitor_type_guid filter removed (collect_rows picks the table instead)
    qs = (
        model.objects
        .select_related("person", "site", "tenant", "approved_by", "visitor_type")
        .filter(scope_q, source__in=PRE_REG_SOURCES)
    )

    if status:
        qs = qs.filter(approval_status=status)

    if statuses:
        qs = qs.filter(approval_status__in=statuses)

    if search:
        qs = qs.filter(
            Q(person__identity_number__icontains=search)
            | Q(person__person_name__icontains=search)
            | Q(person__phone_number__icontains=search)
            | Q(person__email__icontains=search)
            | Q(tenant__tenant_name__icontains=search)
            | Q(company__icontains=search)
            | Q(requester_email__icontains=search)
            | Q(approver_email__icontains=search)
        )

    # the visit period overlaps the filter range
    if from_date:
        qs = qs.filter(to_date__gte=from_date)
    if to_date:
        qs = qs.filter(from_date__lte=to_date)

    # the day the request was approved / rejected (history)
    if decided_from:
        qs = qs.filter(approved_at__date__gte=decided_from)
    if decided_to:
        qs = qs.filter(approved_at__date__lte=decided_to)

    return qs.order_by("-created_at", "-id")


def collect_rows(scope_q, search="", status="", visitor_type_guid=None,
                 from_date=None, to_date=None, statuses=None,
                 decided_from=None, decided_to=None):
    """Rows of both tables as (created_at, kind, record), newest first."""
    search = (search or "").strip()

    # NEW: the visitor type filter decides which table to read
    wanted_kind = _kind_for_visitor_type(visitor_type_guid) if visitor_type_guid else None

    rows = []
    for kind, model in KIND_MODELS.items():
        if wanted_kind and kind != wanted_kind:
            continue
        for rec in _build_qs(
            model, scope_q, search, status, from_date, to_date,
            statuses, decided_from, decided_to,
        ):
            rows.append((rec.created_at, kind, rec))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def paginate_rows(rows, page, page_size, serialize, message):
    """serialize(record, kind) -> dict"""
    if page is None and page_size is None:
        return {
            "success": True,
            "message": message,
            "data": {"results": [serialize(rec, k) for _, k, rec in rows]},
        }

    page = page or 1
    page_size = page_size or 10
    paginator = Paginator(rows, page_size)

    if page > paginator.num_pages and paginator.num_pages > 0:
        return _fail("Page number out of range", 404)

    page_obj = paginator.page(page)

    return {
        "success": True,
        "message": message,
        "data": {
            "results": [serialize(rec, k) for _, k, rec in page_obj.object_list],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            },
        },
    }


# ----------------------------------------------------------------------
# approvers of a site (pre-registration form dropdown)
# ----------------------------------------------------------------------

def site_approvers_qs(site_obj):
    """Active users of the site whose role has the Approval menu enabled.
    Both role__permissions__ conditions sit in ONE filter() call, so they
    must match the same RolePermission row (right menu AND enabled)."""
    return (
        User.objects
        .filter(
            is_active=True,
            is_superuser=False,
            site=site_obj,
            role__is_active=True,
            role__permissions__menu_key=APPROVAL_MENU_KEY,
            role__permissions__menu_enabled=True,
        )
        .select_related("role", "site")
        .distinct()
        .order_by("first_name", "last_name", "email")
    )


def _serialize_approver(obj):
    return {
        "id": obj.id,
        "full_name": f"{obj.first_name} {obj.last_name}".strip(),
        "email": obj.email,
        "role": {
            "guid": str(obj.role.guid),
            "name": obj.role.name,
        } if obj.role_id else None,
        "site": {
            "guid": str(obj.site.guid),
            "name": obj.site.site_name,
        } if obj.site_id else None,
    }


def list_site_approvers(site_guid, user):
    """Users of the given site whose role has the Approval menu enabled."""

    site_obj = Site.objects.filter(guid=site_guid).first()

    if site_obj is None:
        return _fail("Selected site does not exist")

    # Super admin can ask for any site. Everyone else: own site, or a
    # sub-site they are allowed to view on the Pre-Registration page.
    if not user.is_super_admin():
        own = user.site

        if own is None:
            return _fail("No site is assigned to your account", 403)

        if own.pk != site_obj.pk and not user_can_view_site(
            user, PRE_REGISTRATION_MENU_KEY, str(site_obj.guid)
        ):
            return _fail("You are not allowed to view this site", 403)

    return {
        "success": True,
        "message": "Approvers fetched",
        "data": {
            "results": [_serialize_approver(o) for o in site_approvers_qs(site_obj)],
        },
    }


# ----------------------------------------------------------------------
# approval list (site wise)
# ----------------------------------------------------------------------

def _can_act(user, rec):
    """Returns (allowed, message)."""
    if user.is_super_admin():
        return True, ""

    me = (user.email or "").strip().lower()

    if ASSIGNED_APPROVER_ONLY and (rec.approver_email or "").strip().lower() != me:
        return False, "This request is assigned to another approver"

    # if not ALLOW_SELF_APPROVAL and (rec.requester_email or "").strip().lower() == me:
    #     return False, "You cannot approve or reject your own request"

    own = user.site
    if own is None:
        return False, "No site is assigned to your account"

    if own.pk == rec.site_id:
        return True, ""

    if user_can_view_site(user, APPROVAL_MENU_KEY, str(rec.site.guid)):
        return True, ""

    return False, "You are not allowed to action requests of this site"


def _pending_count(scope_q):
    return sum(
        model.objects.filter(
            scope_q, source__in=PRE_REG_SOURCES, approval_status="PENDING"
        ).count()
        for model in KIND_MODELS.values()
    )


def list_approvals(
    user,
    page=None,
    page_size=None,
    search="",
    site_guid=None,
    visitor_type_guid=None,
    from_date=None,
    to_date=None,
):
    """Approval page: ONLY the requests still waiting for a decision."""
    scope_q, error = site_scope(user, site_guid, APPROVAL_MENU_KEY)
    if error:
        return error

    rows = collect_rows(
        scope_q, search, "PENDING", visitor_type_guid, from_date, to_date
    )

    def serialize(rec, kind):
        data = serialize_request(rec, kind)
        data["can_act"] = _can_act(user, rec)[0]
        return data

    result = paginate_rows(rows, page, page_size, serialize, "Pending approvals fetched")

    if result["success"]:
        result["data"]["summary"] = {"pending": _pending_count(scope_q)}
    return result


# ----------------------------------------------------------------------
# approval history (approved + rejected requests)
# ----------------------------------------------------------------------

def list_approval_history(
    user,
    page=None,
    page_size=None,
    search="",
    site_guid=None,
    visitor_type_guid=None,
    decision="",
    decided_from=None,
    decided_to=None,
):
    """History tab: requests that were approved or rejected, newest decision first.
    Read straight from the Visitor / Contractor tables, no separate table."""
    scope_q, error = site_scope(user, site_guid, APPROVAL_MENU_KEY)
    if error:
        return error

    rows = collect_rows(
        scope_q,
        search,
        "",
        visitor_type_guid,
        statuses=["APPROVED", "REJECTED"],
        decided_from=decided_from,
        decided_to=decided_to,
    )

    # counts ignore the decision filter so the tabs / chips stay stable
    summary = {
        "approved": sum(1 for r in rows if r[2].approval_status == "APPROVED"),
        "rejected": sum(1 for r in rows if r[2].approval_status == "REJECTED"),
        "pending": _pending_count(scope_q),
    }

    if decision:
        rows = [r for r in rows if r[2].approval_status == decision]

    rows.sort(key=lambda r: r[2].approved_at or r[0], reverse=True)

    def serialize(rec, kind):
        data = serialize_request(rec, kind)
        by = rec.approved_by
        data["approved_by_name"] = (
            f"{by.first_name} {by.last_name}".strip() or by.email
        ) if by else None
        data["can_act"] = False
        return data

    result = paginate_rows(rows, page, page_size, serialize, "Approval history fetched")

    if result["success"]:
        result["data"]["summary"] = summary
    return result


# ----------------------------------------------------------------------
# approve / reject
# ----------------------------------------------------------------------

def act_on_request(user, guid, action, remark=""):
    remark = (remark or "").strip()

    with transaction.atomic():
        rec, kind = find_record(guid, lock=True)
        if rec is None:
            return _fail("Request not found", 404)

        if rec.source not in PRE_REG_SOURCES:
            return _fail("This record is not a pre-registration request", 409)

        if rec.approval_status != "PENDING":
            return _fail(
                f"This request is already {rec.approval_status.lower()}", 409
            )

        allowed, message = _can_act(user, rec)
        if not allowed:
            return _fail(message, 403)

        if action == "APPROVE":
            # the person may have been banned after the request was raised
            if is_person_banned(rec.person, rec.site):
                return _fail(
                    "This person is banned at this site and cannot be approved", 409
                )
            rec.approval_status = "APPROVED"
        else:
            rec.approval_status = "REJECTED"

        rec.approved_by = user
        rec.approved_at = timezone.now()
        # CHANGED: model field is approval_remark
        rec.approval_remark = remark
        rec.save()

        # mail the requester only after the decision is saved
        approved = action == "APPROVE"
        transaction.on_commit(
            lambda: send_pre_registration_decision_mail(rec, kind, user, approved)
        )

    return {
        "success": True,
        "message": "Request approved" if action == "APPROVE" else "Request rejected",
        "data": serialize_request(rec, kind),
    }

# ----------------------------------------------------------------------
# approve / reject a whole bulk upload
# ----------------------------------------------------------------------

def act_on_bulk(user, bulk_id, action, remark=""):
    """Approve / reject every PENDING request of one bulk upload in a single
    transaction. Rows the user cannot act on (or banned people on approve)
    are skipped and reported back."""
    remark = (remark or "").strip()
    approved = action == "APPROVE"

    done = []      # (record, kind)
    skipped = []   # {"guid", "person_name", "reason"}
    found = False

    with transaction.atomic():
        for kind, model in KIND_MODELS.items():
            qs = (
                model.objects
                .select_related("person", "site", "tenant", "approved_by", "visitor_type")
                .select_for_update(of=("self",))
                .filter(bulk_id=bulk_id, source__in=PRE_REG_SOURCES)
            )
            for rec in qs:
                found = True

                if rec.approval_status != "PENDING":
                    continue  # already decided

                allowed, message = _can_act(user, rec)
                if not allowed:
                    skipped.append({
                        "guid": str(rec.guid),
                        "person_name": rec.person.person_name,
                        "reason": message,
                    })
                    continue

                if approved and is_person_banned(rec.person, rec.site):
                    skipped.append({
                        "guid": str(rec.guid),
                        "person_name": rec.person.person_name,
                        "reason": "Person is banned at this site",
                    })
                    continue

                rec.approval_status = "APPROVED" if approved else "REJECTED"
                rec.approved_by = user
                rec.approved_at = timezone.now()
                rec.approval_remark = remark
                rec.save()
                done.append((rec, kind))

        if not found:
            return _fail("Bulk upload not found", 404)

        if not done:
            return _fail("No pending requests could be actioned in this bulk", 409)

        for rec, kind in done:
            transaction.on_commit(
                lambda rec=rec, kind=kind: send_pre_registration_decision_mail(
                    rec, kind, user, approved
                )
            )

    return {
        "success": True,
        "message": f"{len(done)} request(s) " + ("approved" if approved else "rejected"),
        "data": {
            "bulk_id": bulk_id,
            "processed": len(done),
            "skipped": skipped,
        },
    }