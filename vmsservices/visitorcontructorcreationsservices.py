from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Contractor, Key, Pass, Site, Tenant, Visitor, VisitorDetail
from .rolepermissionservices import can_view_subsites, user_can_view_site
from .bancreationservices import is_person_banned
VISITOR_MENU_KEY = "/visitor"

KIND_MODELS = {
    "Visitor": Visitor,
    "Contractor": Contractor,
}

# rows created by pre-registration are shown on the Pre-Registration Approved page only
PRE_REG_SOURCES = ("PRE_REGISTRATION", "PRE_REGISTRATION_BULK")

def _fail(message, status_code=400):
    return {"success": False, "message": message, "status_code": status_code}


# ----------------------------------------------------------------------
# serializers
# ----------------------------------------------------------------------

def _status(rec):
    if rec.check_out:
        return "Checked Out"
    if rec.check_in:
        return "Checked In"
    return "Pending"  # pre-registration waiting for its visit date / approval


def _serialize_person(p):
    return {
        "id": p.id,
        "person_name": p.person_name,
        "identity_type": p.identity_type,
        "identity_number": p.identity_number,
        "phone_number": p.phone_number,
        "email": p.email,
        "currently_checked_in": p.currently_checked_in,
        "is_banned": p.is_banned,
    }

    # return pass_names, key_names



# def _serialize(rec, kind):
def _serialize(rec, kind, pass_names=None, key_names=None):
    if pass_names is None or key_names is None:
        pass_names, key_names = _asset_names([rec])
    return {
        "guid": str(rec.guid),
        "id": rec.id,
        "visitor_type": {
            "guid": str(rec.visitor_type.guid),
            "name": rec.visitor_type.name,
        } if rec.visitor_type_id else {"guid": None, "name": kind},
        "kind": kind,
        "person": _serialize_person(rec.person),
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
        "requester_email": rec.requester_email,
        "from_date": rec.from_date,
        "to_date": rec.to_date,
        "from_time": rec.from_time,
        "to_time": rec.to_time,
        "check_in": rec.check_in,
        "check_out": rec.check_out,
        "pass_no": rec.pass_no,
        "pass_name": pass_names.get((rec.site_id, rec.pass_no)),
        "key_no": rec.key_no,
        "key_name": key_names.get((rec.site_id, rec.key_no)),
        "vehicle_number": rec.vehicle_number,
        "remark": rec.remark,
        "status": _status(rec),
        "created_at": rec.created_at,
    }


def _asset_names(records):
    """
    Build {(site_id, pass_no): pass_name} and {(site_id, key_no): key_name}
    for the given visit records, using one query each.
    """
    site_ids = {rec.site_id for rec in records}
    pass_nos = {rec.pass_no for rec in records if rec.pass_no}
    key_nos = {rec.key_no for rec in records if rec.key_no}

    pass_names = {}
    if pass_nos:
        for site_id, no, name in Pass.objects.filter(
            site_id__in=site_ids, pass_no__in=pass_nos
        ).values_list("site_id", "pass_no", "pass_name"):
            pass_names[(site_id, no)] = name

    # key_names = {}
    # if key_nos:
    #     for site_id, no, name in Key.objects.filter(
    #         site_id__in=site_ids, key_no__in=key_nos
    #     ).values_list("site_id", "key_no", "key_name"):
    #         key_names[(site_id, no)] = name

    key_names = {}
    if key_nos:
        for site_id, no, name in Key.objects.filter(
            site_id__in=site_ids, key_no__in=key_nos
        ).values_list("site_id", "key_no", "key_name"):
            key_names[(site_id, no)] = name

    return pass_names, key_names


# ----------------------------------------------------------------------
# site scoping (same rules as list_sites)
# ----------------------------------------------------------------------

def _site_scope(user, site_guid):
    """Returns (Q for the site filter, error_dict_or_None)."""
    # include_children = True

    if user is not None and not user.is_super_admin():
        own = user.site

        if own is None:
            return None, _fail("No site is assigned to your account", 403)

        if not site_guid:
            site_guid = str(own.guid)

        if str(site_guid) != str(own.guid) and not user_can_view_site(
            user, VISITOR_MENU_KEY, site_guid
        ):
            return None, _fail("You are not allowed to view this site", 403)

        # include_children = can_view_subsites(user, VISITOR_MENU_KEY)

    # if not site_guid:
    #     return Q(), None

    # condition = Q(site__guid=site_guid)
    # if include_children:
    #     condition |= Q(site__parent__guid=site_guid)
    # return condition, None

    if not site_guid:
        return Q(), None

    return Q(site__guid=site_guid), None


# ----------------------------------------------------------------------
# list
# ----------------------------------------------------------------------

def _build_qs(model, scope_q, search, from_date, to_date):
    qs = (
        model.objects
        .select_related("person", "site", "tenant", "visitor_type")
        .filter(scope_q)
    )

    if search:
        qs = qs.filter(
            Q(person__identity_number__icontains=search)
            | Q(person__person_name__icontains=search)
            | Q(person__phone_number__icontains=search)
            | Q(person__email__icontains=search)
            | Q(tenant__tenant_name__icontains=search)
            | Q(vehicle_number__icontains=search)
            | Q(company__icontains=search)
            | Q(company_phone__icontains=search)
        )

    # The "visit date" is the check-in date; pre-registrations that have not
    # checked in yet use their from_date instead.
    if from_date:
        qs = qs.filter(
            Q(check_in__date__gte=from_date)
            | Q(check_in__isnull=True, from_date__gte=from_date)
        )
    if to_date:
        qs = qs.filter(
            Q(check_in__date__lte=to_date)
            | Q(check_in__isnull=True, from_date__lte=to_date)
        )

    return qs.order_by("-created_at", "-id")


def list_visits(
    page=None,
    page_size=None,
    search="",
    site_guid=None,
    kind="",
    from_date=None,
    to_date=None,
    user=None,
):
    scope_q, error = _site_scope(user, site_guid)
    if error:
        return error

    search = (search or "").strip()
    kinds = [kind] if kind else list(KIND_MODELS.keys())

    # rows = []
    # for k in kinds:
    #     for rec in _build_qs(KIND_MODELS[k], scope_q, search, from_date, to_date):
    #         rows.append((rec.created_at, k, rec))

    rows = []
    for k in kinds:
        qs = _build_qs(KIND_MODELS[k], scope_q, search, from_date, to_date).exclude(
            source__in=PRE_REG_SOURCES
        )
        for rec in qs:
            rows.append((rec.created_at, k, rec))
            
    rows.sort(key=lambda r: r[0], reverse=True)

    # if page is None and page_size is None:
    #     return {
    #         "success": True,
    #         "message": "Visits fetched",
    #         "data": {"results": [_serialize(rec, k) for _, k, rec in rows]},
    #     }
    if page is None and page_size is None:
        pass_names, key_names = _asset_names([rec for _, _, rec in rows])
        return {
            "success": True,
            "message": "Visits fetched",
            "data": {
                "results": [
                    _serialize(rec, k, pass_names, key_names) for _, k, rec in rows
                ]
            },
        }

    page = page or 1
    page_size = page_size or 10
    paginator = Paginator(rows, page_size)

    if page > paginator.num_pages and paginator.num_pages > 0:
        return _fail("Page number out of range", 404)

    page_obj = paginator.page(page)
    page_rows = page_obj.object_list
    pass_names, key_names = _asset_names([rec for _, _, rec in page_rows])

    return {
        "success": True,
        "message": "Visits fetched",
        "data": {
            # "results": [_serialize(rec, k) for _, k, rec in page_obj.object_list],
            "results": [_serialize(rec, k, pass_names, key_names) for _, k, rec in page_rows],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            },
        },
    }


# ----------------------------------------------------------------------
# identity search (fills the "Visitors" dropdown in the check-in modal)
# ----------------------------------------------------------------------

# def search_persons(identity_type, identity_number):
#     qs = VisitorDetail.objects.filter(
#         identity_type__iexact=identity_type.strip(),
#         identity_number__iexact=identity_number.strip(),
#     ).order_by("person_name", "id")

#     return {
#         "success": True,
#         "message": "Persons fetched",
#         "data": {"results": [_serialize_person(p) for p in qs]},
#     }

def _open_visit_sites(person_ids):
    """person_id -> {guid, name} of the site where they are checked in right now."""
    sites = {}
    if not person_ids:
        return sites

    for model in KIND_MODELS.values():
        rows = (
            model.objects
            .select_related("site")
            .filter(
                person_id__in=person_ids,
                check_in__isnull=False,
                check_out__isnull=True,
            )
            .order_by("check_in")
        )
        for rec in rows:
            sites[rec.person_id] = {
                "guid": str(rec.site.guid),
                "name": rec.site.site_name,
            }
    return sites


# def search_persons(identity_type, identity_number):
#     persons = list(
#         VisitorDetail.objects.filter(
#             identity_type__iexact=identity_type.strip(),
#             identity_number__iexact=identity_number.strip(),
#         ).order_by("person_name", "id")
#     )

#     open_sites = _open_visit_sites([p.id for p in persons if p.currently_checked_in])

#     results = []
#     for p in persons:
#         data = _serialize_person(p)
#         data["checked_in_site"] = open_sites.get(p.id) if p.currently_checked_in else None
#         results.append(data)

def search_persons(identity_type, identity_number, site=None):
    site_obj = Site.objects.filter(guid=site).first() if site else None

    persons = list(
        VisitorDetail.objects.filter(
            identity_type__iexact=identity_type.strip(),
            identity_number__iexact=identity_number.strip(),
        ).order_by("person_name", "id")
    )

    open_sites = _open_visit_sites([p.id for p in persons if p.currently_checked_in])

    results = []
    for p in persons:
        data = _serialize_person(p)
        data["is_banned"] = is_person_banned(p, site_obj)
        data["checked_in_site"] = open_sites.get(p.id) if p.currently_checked_in else None
        results.append(data)

    return {
        "success": True,
        "message": "Persons fetched",
        "data": {"results": results},
    }


# ----------------------------------------------------------------------
# check-in
# ----------------------------------------------------------------------

def _can_check_in_at(user, site_obj):
    if user.is_super_admin():
        return True
    own = user.site
    return own is not None and own.pk == site_obj.pk


def create_check_in(
    user,
    kind,
    site,
    location,
    person_name,
    identity_type,
    identity_number,
    phone_number,
    person_id=None,
    email="",
    company="",
    company_phone="",
    pass_no="",
    key_no="",
    vehicle_number="",
    remark="",
):
    model = KIND_MODELS[kind]

    site_obj = Site.objects.filter(guid=site).first()
    if site_obj is None:
        return _fail("Selected site does not exist")

    if not _can_check_in_at(user, site_obj):
        return _fail("You can only check in visitors at your own site", 403)

    tenant_obj = Tenant.objects.filter(guid=location, site=site_obj).first()
    if tenant_obj is None:
        return _fail("Selected location does not belong to this site")

    with transaction.atomic():
        # ---- person ----
        if person_id:
            person = (
                VisitorDetail.objects.select_for_update().filter(pk=person_id).first()
            )
            if person is None:
                return _fail("Selected person not found", 404)

            if person.phone_number and person.phone_number.strip() != phone_number.strip():
                return _fail(
                    "Phone number does not match this person's saved number.", 409
                )
        else:
            person = (
                VisitorDetail.objects.select_for_update()
                .filter(
                    identity_type__iexact=identity_type.strip(),
                    identity_number__iexact=identity_number.strip(),
                    person_name__iexact=person_name.strip(),
                    phone_number=phone_number.strip(),
                )
                .first()
            )

            # same identity + name but a different phone: do not create a duplicate
            # if person is None:
            #     phone_clash = VisitorDetail.objects.filter(
            #         identity_type__iexact=identity_type.strip(),
            #         identity_number__iexact=identity_number.strip(),
            #         person_name__iexact=person_name.strip(),
            #     ).exclude(phone_number=phone_number.strip())
            #     if phone_clash.exists():
            #         return _fail(
            #             "This person already exists with a different phone number. "
            #             "Search the identity number and select the existing record.",
            #             409,
            #         )

            if person is None:
                # same identity + name but a different phone: do not create a duplicate
                phone_clash = VisitorDetail.objects.filter(
                    identity_type__iexact=identity_type.strip(),
                    identity_number__iexact=identity_number.strip(),
                    person_name__iexact=person_name.strip(),
                ).exclude(phone_number=phone_number.strip())
                if phone_clash.exists():
                    return _fail(
                        "This person already exists with a different phone number. "
                        "Search the identity number and select the existing record.",
                        409,
                    )

                # same identity + same phone, but a different name: phone already taken
                same_phone = VisitorDetail.objects.filter(
                    identity_type__iexact=identity_type.strip(),
                    identity_number__iexact=identity_number.strip(),
                    phone_number=phone_number.strip(),
                )
                if same_phone.exists():
                    return _fail(
                        "This phone number is already used by another person "
                        "with the same identity.",
                        409,
                    )

        if person is not None:
            if is_person_banned(person, site_obj):
                return _fail("This person is banned at this site and cannot be checked in", 403)
            # if person.currently_checked_in:
            #     return _fail("This person is already checked in", 409)

            if person.currently_checked_in:
                open_site = _open_visit_sites([person.id]).get(person.id)
                where = f" at {open_site['name']}" if open_site else ""
                return _fail(f"This person is already checked in{where}", 409)

        email = (email or "").strip().lower() or None
        if email:
            email_clash = VisitorDetail.objects.filter(email__iexact=email)
            if person is not None:
                email_clash = email_clash.exclude(pk=person.pk)
            if email_clash.exists():
                return _fail("This email is already used by another person", 409)

        # ---- pass / key must be free at this site ----
        pass_obj = None
        if pass_no:
            pass_obj = (
                Pass.objects.select_for_update()
                .filter(site=site_obj, pass_no=pass_no, status="Active")
                .first()
            )
            if pass_obj is None:
                return _fail("Selected pass is not available")

        key_obj = None
        if key_no:
            key_obj = (
                Key.objects.select_for_update()
                .filter(site=site_obj, key_no=key_no, status="Available")
                .first()
            )
            if key_obj is None:
                return _fail("Selected key is not available")

        # ---- create / update person ----
        # email = (email or "").strip() or None
        # if person is None:
        #     person = VisitorDetail.objects.create(
        #         person_name=person_name.strip(),
        #         identity_type=identity_type.strip(),
        #         identity_number=identity_number.strip(),
        #         phone_number=phone_number.strip(),
        #         email=email,
        #     )
        # elif email and not person.email:
        #     person.email = email

        # person.currently_checked_in = True
        # person.save()
                # ---- create / update person ----
        try:
            with transaction.atomic():
                if person is None:
                    person = VisitorDetail.objects.create(
                        person_name=person_name.strip(),
                        identity_type=identity_type.strip(),
                        identity_number=identity_number.strip(),
                        phone_number=phone_number.strip(),
                        email=email,
                    )
                elif email and not person.email:
                    person.email = email

                person.currently_checked_in = True
                person.save()
        except IntegrityError:
            return _fail("This email is already used by another person", 409)

        # ---- visit row ----
        rec = model.objects.create(
            person=person,
            site=site_obj,
            tenant=tenant_obj,
            company=company.strip() if kind == "Contractor" else "",
            company_phone=company_phone.strip() if kind == "Contractor" else "",
            source="WALK_IN",
            check_in=timezone.now(),
            pass_no=pass_no,
            key_no=key_no,
            vehicle_number=vehicle_number.strip(),
            remark=remark.strip(),
            created_by=user,
        )

        if pass_obj:
            pass_obj.status = "Assigned"
            pass_obj.updated_by = user
            pass_obj.save()
        if key_obj:
            key_obj.status = "Assigned"
            key_obj.updated_by = user
            key_obj.save()

    return {
        "success": True,
        "message": "Checked in",
        "data": _serialize(rec, kind),
    }


# ----------------------------------------------------------------------
# check-out
# ----------------------------------------------------------------------

def check_out(user, kind, guid):
    model = KIND_MODELS[kind]

    with transaction.atomic():
        rec = (
            model.objects.select_for_update(of=("self",))
            .select_related("person", "site", "tenant", "visitor_type")
            .filter(guid=guid)
            .first()
        )
        if rec is None:
            return _fail("Record not found", 404)

        if not _can_check_in_at(user, rec.site):
            return _fail("You can only check out visitors at your own site", 403)

        if not rec.check_in:
            return _fail("This visit has not been checked in yet", 409)
        if rec.check_out:
            return _fail("This visit is already checked out", 409)

        # lock the person row before updating it
        VisitorDetail.objects.select_for_update().filter(pk=rec.person_id).first()

        rec.check_out = timezone.now()
        rec.save()

        rec.person.currently_checked_in = False
        rec.person.save()

        # free the pass / key again
        if rec.pass_no:
            Pass.objects.filter(
                site=rec.site, pass_no=rec.pass_no, status="Assigned"
            ).update(status="Active", updated_by=user)
        if rec.key_no:
            Key.objects.filter(
                site=rec.site, key_no=rec.key_no, status="Assigned"
            ).update(status="Available", updated_by=user)

    return {
        "success": True,
        "message": "Checked out",
        "data": _serialize(rec, kind),
    }



# ----------------------------------------------------------------------
# find the currently checked-in visit for a pass (check-out modal)
# ----------------------------------------------------------------------

def find_checked_in_by_pass(user, site, pass_no):
    site_obj = Site.objects.filter(guid=site).first()
    if site_obj is None:
        return _fail("Selected site does not exist")

    if not _can_check_in_at(user, site_obj):
        return _fail("You can only check out visitors at your own site", 403)

    pass_no = (pass_no or "").strip()

    for kind, model in KIND_MODELS.items():
        rec = (
            model.objects
            .select_related("person", "site", "tenant", "visitor_type")
            .filter(
                site=site_obj,
                pass_no=pass_no,
                check_in__isnull=False,
                check_out__isnull=True,
            )
            .order_by("-check_in")
            .first()
        )
        if rec is not None:
            return {
                "success": True,
                "message": "Checked-in visit fetched",
                "data": _serialize(rec, kind),
            }

    return _fail("No checked-in person found for this pass", 404)