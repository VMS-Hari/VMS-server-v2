from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .approvalservices import KIND_MODELS, PRE_REG_SOURCES, site_approvers_qs
from .bancreationservices import is_person_banned
from .bulkpreregistrationmailservices import send_bulk_pre_registration_request_mail
from .models import (
    IdentityType,
    Site,
    Tenant,
    TenantNotification,
    VisitorDetail,
    VisitorType,
)
from .preregistrationcreationservices import (
    COMPANY_PHONE_RE,
    COMPANY_VISITOR_TYPES,
    _can_pre_register_at,
    _fail,
    _identity_number_error,
    _phone_error,
    _record_fields,
    _upsert_person,
)
from .visitorcontructorcreationsservices import (
    _build_qs,
    _open_visit_sites,
    _serialize,
    _site_scope,
)

BULK_SOURCE = "PRE_REGISTRATION_BULK"

ROW_FIELDS = (
    "person_name", "identity_type", "identity_number", "phone_number",
    "email", "company", "company_phone", "vehicle_number", "remark",
)

LIMITS = {
    "person_name": 150, "identity_type": 150, "identity_number": 100,
    "phone_number": 20, "email": 254, "company": 150,
    "company_phone": 20, "vehicle_number": 50,
}

# True  -> an existing person who is checked in at ANOTHER site cannot be pre-registered
BLOCK_IF_CHECKED_IN_ELSEWHERE = True


# ----------------------------------------------------------------------
# shared (once per upload): site / location / visitor type / dates / approver
# ----------------------------------------------------------------------

def _prepare_batch(user, d):
    site_obj = Site.objects.filter(guid=d["site"]).first()
    if site_obj is None:
        return None, _fail("Selected site does not exist", field="site")

    if not _can_pre_register_at(user, site_obj):
        return None, _fail("You are not allowed to pre-register at this site", 403)

    tenant_obj = Tenant.objects.filter(guid=d["location"], site=site_obj).first()
    if tenant_obj is None:
        return None, _fail("Selected location does not belong to this site", field="location")

    vtype = VisitorType.objects.filter(guid=d["visitor_type"], is_active=True).first()
    if vtype is None:
        return None, _fail("Selected visitor type does not exist", field="visitor_type")

    kind = "Contractor" if vtype.name.strip().lower() in COMPANY_VISITOR_TYPES else "Visitor"

    from_date, to_date = d["from_date"], d["to_date"]
    if from_date < timezone.localdate():
        return None, _fail("From Date cannot be in the past", field="from_date")

    if TenantNotification.objects.filter(
        tenant=tenant_obj, from_date__lte=to_date, to_date__gte=from_date
    ).exists():
        return None, _fail(
            "This location is not available for the selected dates", 409, "location"
        )

    approver_email = d["approver_email"].strip().lower()
    if not site_approvers_qs(site_obj).filter(email__iexact=approver_email).exists():
        return None, _fail(
            "Selected approver is not an approver of this site", field="approver_email"
        )

    return {
        "kind": kind,
        "visitor_type": vtype,
        "model": KIND_MODELS[kind],
        "site": site_obj,
        "tenant": tenant_obj,
        "from_date": from_date,
        "to_date": to_date,
        "from_time": d.get("from_time"),
        "to_time": d.get("to_time"),
        "approver_email": approver_email,
        "pass_no": "",
        "key_no": "",
    }, None


# ----------------------------------------------------------------------
# one row
# ----------------------------------------------------------------------

def _clean(raw):
    return {f: (raw.get(f) or "").strip() for f in ROW_FIELDS}


def _check_row(batch, r, idtypes, lock, seen, row_no):
    """Returns {error, field, ctx, person_status, person_id}. First problem wins."""

    def bad(msg, field=""):
        return {"error": msg, "field": field, "ctx": None,
                "person_status": "", "person_id": None}

    site = batch["site"]

    # ---- required + length ----
    if not r["person_name"]:
        return bad("Full Name is required", "person_name")
    if not r["identity_type"]:
        return bad("Identity Type is required", "identity_type")
    for f, limit in LIMITS.items():
        if len(r[f]) > limit:
            return bad(f"{f.replace('_', ' ').title()} is too long (max {limit})", f)

    # ---- identity type / number / phone rules ----
    it = idtypes.get(r["identity_type"].lower())
    if it is None:
        return bad(f'Unknown Identity Type "{r["identity_type"]}"', "identity_type")

    msg = _identity_number_error(it, r["identity_number"])
    if msg:
        return bad(msg, "identity_number")

    msg = _phone_error(it, r["phone_number"])
    if msg:
        return bad(msg, "phone_number")

    # ---- email format ----
    email = r["email"].lower()
    if email:
        try:
            validate_email(email)
        except DjangoValidationError:
            return bad("Invalid Email", "email")

    # ---- company (contractor type only) ----
    company, company_phone = "", ""
    if batch["kind"] == "Contractor":
        company, company_phone = r["company"], r["company_phone"]
        if not company:
            return bad("Company Name is required for this visitor type", "company")
        if not COMPANY_PHONE_RE.match(company_phone):
            return bad("Company Phone must be 10 digits", "company_phone")

    # ---- duplicates inside the same file ----
    t = it.identity_type_name.lower()
    n = r["identity_number"].lower()
    nm = r["person_name"].lower()
    ph = r["phone_number"]
    pkey = (t, n, nm, ph)

    if pkey in seen["people"]:
        return bad(f"Duplicate of Excel row {seen['people'][pkey]}", "person_name")

    if ph and (t, n, ph) in seen["phones"]:
        other_name, other_row = seen["phones"][(t, n, ph)]
        if other_name != nm:
            return bad(
                f"Phone number is already used by another person with the same "
                f"identity in Excel row {other_row}", "phone_number"
            )

    if email and email in seen["emails"] and seen["emails"][email][0] != pkey:
        return bad(f"Email is already used in Excel row {seen['emails'][email][1]}", "email")

    # ---- new person or existing person? ----
    base = VisitorDetail.objects.select_for_update() if lock else VisitorDetail.objects
    people = list(
        base.filter(
            identity_type__iexact=it.identity_type_name,
            identity_number__iexact=r["identity_number"],
        )
    )
    person = next(
        (p for p in people
         if p.person_name.strip().lower() == nm and (p.phone_number or "").strip() == ph),
        None,
    )

    if person is None:
        if any(p.person_name.strip().lower() == nm for p in people):
            return bad(
                "This person already exists with a different phone number",
                "phone_number",
            )
        if ph and any((p.phone_number or "").strip() == ph for p in people):
            return bad(
                "This phone number is already used by another person with the "
                "same identity", "phone_number",
            )

    # ---- existing person: ban / checked in elsewhere ----
    if person is not None:
        if is_person_banned(person, site):
            return bad("This person is banned at this site", "identity_number")

        if BLOCK_IF_CHECKED_IN_ELSEWHERE and person.currently_checked_in:
            open_site = _open_visit_sites([person.id]).get(person.id)
            # checked in at this same site is fine; anywhere else is blocked
            if open_site is None or open_site.get("name") != site.site_name:
                where = f" at {open_site['name']}" if open_site else ""
                return bad(f"This person is already checked in{where}", "identity_number")

    # ---- email must be unique across persons ----
    if email:
        clash = VisitorDetail.objects.filter(email__iexact=email)
        if person is not None:
            clash = clash.exclude(pk=person.pk)
        if clash.exists():
            return bad("This email is already used by another person", "email")

    # ---- existing person: no overlapping request at this site ----
    if person is not None:
        for model in KIND_MODELS.values():
            if model.objects.filter(
                person=person,
                site=site,
                source__in=PRE_REG_SOURCES,
                approval_status__in=["PENDING", "APPROVED"],
                check_out__isnull=True,
                from_date__lte=batch["to_date"],
                to_date__gte=batch["from_date"],
            ).exists():
                return bad(
                    "This person already has a pre-registration for these dates "
                    "at this site"
                )

    # ---- row is clean: remember it for in-file duplicate checks ----
    seen["people"][pkey] = row_no
    if ph:
        seen["phones"].setdefault((t, n, ph), (nm, row_no))
    if email:
        seen["emails"].setdefault(email, (pkey, row_no))

    ctx = {
        **batch,
        "person": person,
        "person_name": r["person_name"],
        "identity_type": it.identity_type_name,
        "identity_number": r["identity_number"],
        "phone_number": ph,
        "email": email or None,
        "company": company,
        "company_phone": company_phone,
        "vehicle_number": r["vehicle_number"],
        "remark": r["remark"],
    }
    return {
        "error": "", "field": "", "ctx": ctx,
        "person_status": "EXISTING" if person else "NEW",
        "person_id": person.id if person else None,
    }


def _run_rows(batch, rows, lock):
    idtypes = {t.identity_type_name.strip().lower(): t for t in IdentityType.objects.all()}
    seen = {"people": {}, "phones": {}, "emails": {}}

    results = []
    for i, raw in enumerate(rows):
        row_no = raw.get("row_no") or i + 1
        res = _check_row(batch, _clean(raw), idtypes, lock, seen, row_no)
        res["row_no"] = row_no
        results.append(res)
    return results


def _public_rows(results):
    return [
        {
            "row_no": r["row_no"],
            "valid": not r["error"],
            "error": r["error"],
            "field": r["field"],
            "person_status": r["person_status"],
            "person_id": r["person_id"],
        }
        for r in results
    ]


def _summary(results):
    ok = [r for r in results if not r["error"]]
    return {
        "total": len(results),
        "valid": len(ok),
        "invalid": len(results) - len(ok),
        "new_persons": sum(1 for r in ok if r["person_status"] == "NEW"),
        "existing_persons": sum(1 for r in ok if r["person_status"] == "EXISTING"),
    }


# ----------------------------------------------------------------------
# 1) validate (read only, nothing is saved)
# ----------------------------------------------------------------------

def validate_bulk_pre_registration(user, data):
    batch, error = _prepare_batch(user, data)
    if error:
        return error

    results = _run_rows(batch, data["rows"], lock=False)

    summary = _summary(results)
    return {
        "success": True,
        "message": "Validation completed",
        "data": {
            "valid": summary["invalid"] == 0,
            "summary": summary,
            "rows": _public_rows(results),
        },
    }


# ----------------------------------------------------------------------
# 2) create (validates again, then saves everything or nothing)
# ----------------------------------------------------------------------

def _next_bulk_id():
    """BLK-YYYYMMDD-001, 002 ... shared by the Visitor and Contractor tables."""
    prefix = f"BLK-{timezone.localdate():%Y%m%d}-"
    last = 0
    for model in KIND_MODELS.values():
        ids = (
            model.objects.filter(bulk_id__startswith=prefix)
            .values_list("bulk_id", flat=True)
            .distinct()
        )
        for b in ids:
            try:
                last = max(last, int(b.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                pass
    return f"{prefix}{last + 1:03d}"


def create_bulk_pre_registration(user, data):
    with transaction.atomic():
        batch, error = _prepare_batch(user, data)
        if error:
            return error

        results = _run_rows(batch, data["rows"], lock=True)
        summary = _summary(results)

        if summary["invalid"] > 0:
            return {
                "success": False,
                "message": f"{summary['invalid']} row(s) failed validation. Nothing was saved.",
                "status_code": 400,
                "data": {
                    "valid": False,
                    "summary": summary,
                    "rows": _public_rows(results),
                },
            }

        bulk_id = _next_bulk_id()
        created = []

        for res in results:
            ctx = res["ctx"]

            person, error = _upsert_person(ctx)
            if error:
                transaction.set_rollback(True)
                return _fail(f"Excel row {res['row_no']}: {error['message']}", 409)

            created.append(
                ctx["model"].objects.create(
                    **_record_fields(ctx, person),
                    source=BULK_SOURCE,
                    bulk_id=bulk_id,
                    approval_status="PENDING",
                    requester_email=user.email,
                    created_by=user,
                )
            )

        kind = batch["kind"]
        transaction.on_commit(
            lambda: send_bulk_pre_registration_request_mail(created, kind, bulk_id, user)
        )

    return {
        "success": True,
        "message": f"{len(created)} pre-registration request(s) created",
        "data": {
            "bulk_id": bulk_id,
            "kind": kind,
            "created": len(created),
            "new_persons": summary["new_persons"],
            "existing_persons": summary["existing_persons"],
        },
    }


# ----------------------------------------------------------------------
# 3) approved list (bulk uploads only, filter by bulk_id)
# ----------------------------------------------------------------------

def _serialize_row(rec, kind):
    data = _serialize(rec, kind)
    today = timezone.localdate()
    last_day = rec.to_date or rec.from_date
    data["bulk_id"] = rec.bulk_id
    data["can_check_in"] = bool(
        not rec.check_in and rec.from_date and rec.from_date <= today <= last_day
    )
    return data


def list_bulk_approved(
    user,
    page=None,
    page_size=None,
    search="",
    site_guid=None,
    bulk_id="",
    kind="",
    visit_status="",
    from_date=None,
    to_date=None,
):
    scope_q, error = _site_scope(user, site_guid)
    if error:
        return error

    search = (search or "").strip()
    bulk_id = (bulk_id or "").strip()
    kinds = [kind] if kind else list(KIND_MODELS.keys())

    rows = []
    for k in kinds:
        qs = _build_qs(KIND_MODELS[k], scope_q, search, from_date, to_date).filter(
            source=BULK_SOURCE,
            approval_status="APPROVED",
        )
        if bulk_id:
            qs = qs.filter(bulk_id=bulk_id)

        if visit_status == "Pending":
            qs = qs.filter(check_in__isnull=True)
        elif visit_status == "Checked In":
            qs = qs.filter(check_in__isnull=False, check_out__isnull=True)
        elif visit_status == "Checked Out":
            qs = qs.filter(check_out__isnull=False)

        for rec in qs:
            rows.append((rec.created_at, k, rec))

    rows.sort(key=lambda r: r[0], reverse=True)

    if page is None and page_size is None:
        return {
            "success": True,
            "message": "Approved bulk pre-registrations fetched",
            "data": {"results": [_serialize_row(rec, k) for _, k, rec in rows]},
        }

    page = page or 1
    page_size = page_size or 10
    paginator = Paginator(rows, page_size)

    if page > paginator.num_pages and paginator.num_pages > 0:
        return _fail("Page number out of range", 404)

    page_obj = paginator.page(page)
    return {
        "success": True,
        "message": "Approved bulk pre-registrations fetched",
        "data": {
            "results": [_serialize_row(rec, k) for _, k, rec in page_obj.object_list],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            },
        },
    }


# ----------------------------------------------------------------------
# 4) bulk id list (dropdown / summary: one entry per upload)
# ----------------------------------------------------------------------

def list_bulk_ids(user, site_guid=None, search=""):
    scope_q, error = _site_scope(user, site_guid)
    if error:
        return error

    search = (search or "").strip()
    groups = {}

    for kind, model in KIND_MODELS.items():
        qs = model.objects.select_related("site").filter(
            scope_q, source=BULK_SOURCE, bulk_id__isnull=False
        )
        if search:
            qs = qs.filter(bulk_id__icontains=search)

        for rec in qs:
            g = groups.setdefault(rec.bulk_id, {
                "bulk_id": rec.bulk_id,
                "kind": kind,
                "site": {"guid": str(rec.site.guid), "name": rec.site.site_name},
                "from_date": rec.from_date,
                "to_date": rec.to_date,
                "requester_email": rec.requester_email,
                "created_at": rec.created_at,
                "total": 0, "pending": 0, "approved": 0, "rejected": 0,
            })
            g["total"] += 1
            g[(rec.approval_status or "PENDING").lower()] += 1

    results = sorted(groups.values(), key=lambda g: g["created_at"], reverse=True)
    return {"success": True, "message": "Bulk uploads fetched", "data": {"results": results}}