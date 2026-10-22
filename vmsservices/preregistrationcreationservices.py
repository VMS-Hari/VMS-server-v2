import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from .approvalservices import (
    KIND_MODELS,
    PRE_REG_SOURCES,
    PRE_REGISTRATION_MENU_KEY,
    collect_rows,
    find_record,
    paginate_rows,
    serialize_request,
    site_approvers_qs,
    site_scope,
)
from .bancreationservices import is_person_banned
from .models import (
    IdentityType,
    Key,
    Pass,
    Site,
    Tenant,
    TenantNotification,
    VisitorDetail,
    VisitorType,
)
from .preregistrationmailservices import send_pre_registration_request_mail
from .rolepermissionservices import user_can_view_site

SOURCE = "PRE_REGISTRATION"

# Visitor types that belong in the Contractor table ("contructor" matches the
# spelling currently in the data).
COMPANY_VISITOR_TYPES = ("contractor", "contructor")

COMPANY_PHONE_RE = re.compile(r"^[0-9]{10}$")


def _fail(message, status_code=400, field=None):
    result = {"success": False, "message": message, "status_code": status_code}
    if field:
        result["errors"] = {field: [message]}
    return result


# ----------------------------------------------------------------------
# identity / phone rules  (same rules the frontend applies on check-in)
# ----------------------------------------------------------------------

def _identity_number_error(it, value):
    validation = it.identity_number_validation
    if validation == "Not Required":
        return None
    if not value:
        return None if validation == "Optional" else \
            "Identity Number is required for this identity type"

    digits, alphabets = it.identity_number_digits, it.identity_number_alphabets
    if digits is None and alphabets is None:
        return None

    pattern = "^"
    if digits is not None:
        pattern += "[0-9]{%d}" % digits
    if alphabets is not None:
        pattern += "[A-Za-z]{%d}" % alphabets
    pattern += "$"

    if re.match(pattern, value):
        return None
    if it.identity_number_format:
        return f"Identity Number must match the format {it.identity_number_format}"

    parts = []
    if digits is not None:
        parts.append(f"{digits} digit(s)")
    if alphabets is not None:
        parts.append(f"{alphabets} letter(s)")
    return f"Identity Number must be {' followed by '.join(parts)}"


def _phone_error(it, value):
    validation = it.phone_number_validation
    if validation == "Not Required":
        return None
    if not value:
        return None if validation == "Optional" else \
            "Contact number is required for this identity type"

    if not re.fullmatch(r"[0-9]+", value):
        return "Contact number must contain digits only"

    low, high = it.phone_number_min, it.phone_number_max
    parts = []
    if low is not None and high is not None and low == high:
        if len(value) != low:
            parts.append(f"{low} digits")
    else:
        if low is not None and len(value) < low:
            parts.append(f"at least {low} digits")
        if high is not None and len(value) > high:
            parts.append(f"at most {high} digits")

    starting = it.phone_number_starting_with
    if starting and value[0] not in set(starting):
        parts.append(f"starting with {starting}")

    return f"Contact number must be {', '.join(parts)}" if parts else None


# ----------------------------------------------------------------------
# permissions
# ----------------------------------------------------------------------

def _can_pre_register_at(user, site_obj):
    if user.is_super_admin():
        return True
    own = user.site
    if own is None:
        return False
    if own.pk == site_obj.pk:
        return True
    return user_can_view_site(user, PRE_REGISTRATION_MENU_KEY, str(site_obj.guid))


def _can_manage(user, rec):
    """Who may edit / delete a request: super admin, its creator, or
    anyone working at the same site."""
    if user.is_super_admin():
        return True
    if rec.created_by_id == user.id:
        return True
    return bool(user.site_id) and user.site_id == rec.site_id


def _check_manageable(user, rec, action):
    if rec.source != SOURCE:
        return _fail("Bulk pre-registrations cannot be changed here", 409)

    if action == "edit" and rec.approval_status != "PENDING":
        return _fail("Only pending requests can be edited", 409)

    if action == "delete" and rec.approval_status == "APPROVED":
        return _fail("Approved requests cannot be deleted", 409)

    if not _can_manage(user, rec):
        return _fail("You are not allowed to change this request", 403)

    return None


# ----------------------------------------------------------------------
# shared validation for create + update
# ----------------------------------------------------------------------

def _prepare(user, d, exclude=None):
    """Validates a pre-registration payload.
    exclude = (model, pk) of the record being edited (skipped in the overlap check).
    Returns (ctx, error). Must be called inside transaction.atomic()."""

    # ---- site / location / visitor type ----
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

    # ---- dates ----
    from_date, to_date = d["from_date"], d["to_date"]
    if from_date < timezone.localdate():
        return None, _fail("From Date cannot be in the past", field="from_date")

    # the location is blocked while a tenant notification covers the dates
    if TenantNotification.objects.filter(
        tenant=tenant_obj, from_date__lte=to_date, to_date__gte=from_date
    ).exists():
        return None, _fail(
            "This location is not available for the selected dates", 409, "location"
        )

    # ---- identity type, identity number, phone ----
    identity_type = d["identity_type"].strip()
    identity_number = d["identity_number"].strip()
    phone_number = (d.get("phone_number") or "").strip()

    it = IdentityType.objects.filter(identity_type_name__iexact=identity_type).first()
    if it is None:
        return None, _fail("Selected identity type does not exist", field="identity_type")

    msg = _identity_number_error(it, identity_number)
    if msg:
        return None, _fail(msg, field="identity_number")

    msg = _phone_error(it, phone_number)
    if msg:
        return None, _fail(msg, field="phone_number")

    # ---- contractor needs a company ----
    company = (d.get("company") or "").strip()
    company_phone = (d.get("company_phone") or "").strip()
    if kind == "Contractor":
        if not company:
            return None, _fail("Company name is required for a contractor", field="company")
        if not COMPANY_PHONE_RE.match(company_phone):
            return None, _fail(
                "Company phone number must be 10 digits", field="company_phone"
            )
    else:
        company, company_phone = "", ""

    # ---- person ----
    person = None
    person_id = d.get("person_id")
    person_name = d["person_name"].strip()

    if person_id:
        person = VisitorDetail.objects.select_for_update().filter(pk=person_id).first()
        if person is None:
            return None, _fail("Selected person not found", 404)

        if (
            person.identity_type.strip().lower() != identity_type.lower()
            or person.identity_number.strip().lower() != identity_number.lower()
        ):
            return None, _fail(
                "Selected person does not match the identity details", 409
            )

        if person.phone_number and person.phone_number.strip() != phone_number:
            return None, _fail(
                "Phone number does not match this person's saved number.", 409,
                "phone_number",
            )
    else:
        person = (
            VisitorDetail.objects.select_for_update()
            .filter(
                identity_type__iexact=identity_type,
                identity_number__iexact=identity_number,
                person_name__iexact=person_name,
                phone_number=phone_number,
            )
            .first()
        )

        if person is None:
            # same identity + name but a different phone: do not create a duplicate
            if VisitorDetail.objects.filter(
                identity_type__iexact=identity_type,
                identity_number__iexact=identity_number,
                person_name__iexact=person_name,
            ).exclude(phone_number=phone_number).exists():
                return None, _fail(
                    "This person already exists with a different phone number. "
                    "Search the identity number and select the existing record.",
                    409,
                )

            # same identity + same phone, but a different name: phone already taken
            if phone_number and VisitorDetail.objects.filter(
                identity_type__iexact=identity_type,
                identity_number__iexact=identity_number,
                phone_number=phone_number,
            ).exists():
                return None, _fail(
                    "This phone number is already used by another person "
                    "with the same identity.",
                    409,
                    "phone_number",
                )

    if person is not None and is_person_banned(person, site_obj):
        return None, _fail(
            "This person is banned at this site and cannot be pre-registered", 403
        )

    # ---- email must be unique across persons ----
    email = (d.get("email") or "").strip().lower() or None
    if email:
        clash = VisitorDetail.objects.filter(email__iexact=email)
        if person is not None:
            clash = clash.exclude(pk=person.pk)
        if clash.exists():
            return None, _fail("This email is already used by another person", 409, "email")

    # ---- same person cannot hold two overlapping requests at one site ----
    if person is not None:
        for model in KIND_MODELS.values():
            overlap = model.objects.filter(
                person=person,
                site=site_obj,
                source__in=PRE_REG_SOURCES,
                approval_status__in=["PENDING", "APPROVED"],
                check_out__isnull=True, 
                from_date__lte=to_date,
                to_date__gte=from_date,
            )
            if exclude and exclude[0] is model:
                overlap = overlap.exclude(pk=exclude[1])
            if overlap.exists():
                return None, _fail(
                    "This person already has a pre-registration for these dates "
                    "at this site",
                    409,
                )

    # ---- pass / key must exist at this site (they are assigned at check-in) ----
    pass_no = (d.get("pass_no") or "").strip()
    if pass_no and not Pass.objects.filter(
        site=site_obj, pass_no=pass_no, status="Active", visitor_type=vtype
    ).exists():
        return None, _fail("Selected pass is not available", field="pass_no")

    key_no = (d.get("key_no") or "").strip()
    if key_no and not Key.objects.filter(
        site=site_obj, key_no=key_no, status="Available"
    ).exists():
        return None, _fail("Selected key is not available", field="key_no")

    # ---- approver must be an approver of this site ----
    approver_email = d["approver_email"].strip().lower()
    if not site_approvers_qs(site_obj).filter(email__iexact=approver_email).exists():
        return None, _fail(
            "Selected approver is not an approver of this site", field="approver_email"
        )

    return {
        "kind": kind,
        "model": KIND_MODELS[kind],
        "site": site_obj,
        "tenant": tenant_obj,
        "visitor_type": vtype,
        "person": person,
        "person_name": person_name,
        "identity_type": identity_type,
        "identity_number": identity_number,
        "phone_number": phone_number,
        "email": email,
        "company": company,
        "company_phone": company_phone,
        "from_date": from_date,
        "to_date": to_date,
        "from_time": d.get("from_time"),
        "to_time": d.get("to_time"),
        "pass_no": pass_no,
        "key_no": key_no,
        "vehicle_number": (d.get("vehicle_number") or "").strip(),
        "remark": (d.get("remark") or "").strip(),
        "approver_email": approver_email,
    }, None


def _upsert_person(ctx):
    """Creates the VisitorDetail row for a new person, or fills in a missing
    email on an existing one. Returns (person, error)."""
    person = ctx["person"]
    try:
        with transaction.atomic():
            if person is None:
                person = VisitorDetail.objects.create(
                    person_name=ctx["person_name"],
                    identity_type=ctx["identity_type"],
                    identity_number=ctx["identity_number"],
                    phone_number=ctx["phone_number"],
                    email=ctx["email"],
                )
            elif ctx["email"] and not person.email:
                person.email = ctx["email"]
                person.save()
    except IntegrityError:
        return None, _fail("This email is already used by another person", 409, "email")
    return person, None


def _record_fields(ctx, person):
    return {
        "person": person,
        "visitor_type": ctx["visitor_type"],
        "site": ctx["site"],
        "tenant": ctx["tenant"],
        "company": ctx["company"],
        "company_phone": ctx["company_phone"],
        "approver_email": ctx["approver_email"],
        "from_date": ctx["from_date"],
        "to_date": ctx["to_date"],
        "from_time": ctx["from_time"],
        "to_time": ctx["to_time"],
        "pass_no": ctx["pass_no"],
        "key_no": ctx["key_no"],
        "vehicle_number": ctx["vehicle_number"],
        "remark": ctx["remark"],
    }


def _serialize_for(user):
    def serialize(rec, kind):
        data = serialize_request(rec, kind)
        manageable = rec.source == SOURCE and _can_manage(user, rec)
        data["can_edit"] = manageable and rec.approval_status == "PENDING"
        data["can_delete"] = manageable and rec.approval_status != "APPROVED"
        return data
    return serialize


# ----------------------------------------------------------------------
# create
# ----------------------------------------------------------------------

def create_pre_registration(user, data):
    with transaction.atomic():
        ctx, error = _prepare(user, data)
        if error:
            return error

        person, error = _upsert_person(ctx)
        if error:
            return error

        rec = ctx["model"].objects.create(
            **_record_fields(ctx, person),
            source=SOURCE,
            approval_status="PENDING",
            requester_email=user.email,
            created_by=user,
        )

        # send the mail only after the request is saved
        kind = ctx["kind"]
        transaction.on_commit(lambda: send_pre_registration_request_mail(rec, kind))

    return {
        "success": True,
        "message": "Pre-registration request created",
        "data": _serialize_for(user)(rec, ctx["kind"]),
    }


# ----------------------------------------------------------------------
# update (only while PENDING)
# ----------------------------------------------------------------------

def update_pre_registration(user, data):
    with transaction.atomic():
        rec, old_kind = find_record(data["guid"], lock=True)
        if rec is None:
            return _fail("Request not found", 404)

        error = _check_manageable(user, rec, "edit")
        if error:
            return error

        ctx, error = _prepare(user, data, exclude=(type(rec), rec.pk))
        if error:
            return error

        person, error = _upsert_person(ctx)
        if error:
            return error

        fields = _record_fields(ctx, person)

        if ctx["kind"] == old_kind:
            for name, value in fields.items():
                setattr(rec, name, value)
            rec.save()
        else:
            # visitor type moved the request to the other table
            new_rec = ctx["model"].objects.create(
                **fields,
                source=SOURCE,
                approval_status="PENDING",
                requester_email=rec.requester_email,
                created_by=rec.created_by,
            )
            rec.delete()
            rec = new_rec

        kind = ctx["kind"]
        transaction.on_commit(lambda: send_pre_registration_request_mail(rec, kind))

    return {
        "success": True,
        "message": "Pre-registration request updated",
        "data": _serialize_for(user)(rec, ctx["kind"]),
    }


# ----------------------------------------------------------------------
# delete (PENDING or REJECTED)
# ----------------------------------------------------------------------

def delete_pre_registration(user, guid):
    with transaction.atomic():
        rec, _ = find_record(guid, lock=True)
        if rec is None:
            return _fail("Request not found", 404)

        error = _check_manageable(user, rec, "delete")
        if error:
            return error

        rec.delete()

    return {"success": True, "message": "Pre-registration request deleted"}


# ----------------------------------------------------------------------
# list
# ----------------------------------------------------------------------

def list_pre_registrations(
    user,
    page=None,
    page_size=None,
    search="",
    site_guid=None,
    visitor_type_guid=None,
    status="",
    from_date=None,
    to_date=None,
):
    # scope_q, error = site_scope(user, site_guid, PRE_REGISTRATION_MENU_KEY)
    # if error:
    #     return error

    scope_q, error = site_scope(
        user,
        site_guid,
        PRE_REGISTRATION_MENU_KEY,
        include_children_of_selected=False,
    )
    if error:
        return error

    rows = collect_rows(scope_q, search, status, visitor_type_guid, from_date, to_date)

    return paginate_rows(
        rows, page, page_size, _serialize_for(user), "Pre-registrations fetched"
    )