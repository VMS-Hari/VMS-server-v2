from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.db.models.functions import Lower

from .models import Contractor, Pass, Site,Visitor, VisitorType
from .rolepermissionservices import user_can_view_site

# must match the menu_key stored in RolePermission for the Pass page
PASS_MENU_KEY = "/property-management/pass"


def _serialize(obj , assigned=None):
    return {
        "guid": str(obj.guid),
        "pass_no": obj.pass_no,
        "pass_name": obj.pass_name,
        "status": obj.status,
        # "source": assigned["source"] if assigned else None,
        "source": assigned["source"] if assigned else None,
        "assigned_to": assigned,
        "site": {
            "guid": str(obj.site.guid),
            "name": obj.site.site_name,
            "site_code": obj.site.site_code,
        },
        "visitor_type": {
            "guid": str(obj.visitor_type.guid),
            "name": obj.visitor_type.name,
        } if obj.visitor_type else None,
        "created_by": obj.created_by.login_id if obj.created_by else None,
        "created_at": obj.created_at,
        "updated_by": obj.updated_by.login_id if obj.updated_by else None,
        "updated_at": obj.updated_at,
    }

def _assigned_map(pass_objs):
    """Find who is currently checked in with each Assigned pass.
    Returns {(site_id, lower pass_no): {...}}"""
    wanted = [o for o in pass_objs if o.status == "Assigned"]
    if not wanted:
        return {}

    site_ids = {o.site_id for o in wanted}
    pass_nos = {o.pass_no.lower() for o in wanted}

    result = {}

    for kind, model in (("Visitor", Visitor), ("Contractor", Contractor)):
        rows = (
            model.objects
            .filter(
                site_id__in=site_ids,
                check_in__isnull=False,
                check_out__isnull=True,
            )
            .annotate(p=Lower("pass_no"))
            .filter(p__in=pass_nos)
            .select_related("person")
            .order_by("check_in")
        )

        for r in rows:
            key = (r.site_id, r.p)
            current = result.get(key)

            if current and current["check_in"] > r.check_in:
                continue

            result[key] = {
                "kind": kind,
                "source": r.source,
                "person_name": r.person.person_name,
                "check_in": r.check_in,
            }

    return result

def _forbidden():
    return {
        "success": False,
        "message": "You are not allowed to manage passes for this site",
        "status_code": 403,
    }


def _can_access_site(user, site_obj):
    """Super admin: any site. Others: own site, or a sub-site they may view."""

    if user is None or user.is_super_admin():
        return True

    own = user.site
    if own is None:
        return False

    if site_obj.pk == own.pk:
        return True

    return user_can_view_site(user, PASS_MENU_KEY, str(site_obj.guid))


def _resolve_site(site_guid):
    site_obj = Site.objects.filter(guid=site_guid).first()

    if site_obj is None:
        return None, {
            "success": False,
            "message": "Selected site does not exist",
            "status_code": 400,
        }

    return site_obj, None


def _resolve_visitor_type(visitor_type_guid):
    if not visitor_type_guid:
        return None, None

    vt_obj = VisitorType.objects.filter(guid=visitor_type_guid).first()

    if vt_obj is None:
        return None, {
            "success": False,
            "message": "Selected visitor type does not exist",
            "status_code": 400,
        }

    return vt_obj, None


def _duplicate_pass_no(site_obj, pass_no, exclude_pk=None):
    qs = Pass.objects.filter(site=site_obj, pass_no__iexact=pass_no)

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def _duplicate_response():
    return {
        "success": False,
        "message": "Pass number already exists for this site",
        "status_code": 409,
    }


def create_passes(items, user):
    """Create many passes in one request. All-or-nothing, but reports every bad row."""

    if not items:
        return {"success": False, "message": "At least one pass is required", "status_code": 400}

    site_cache = {}
    visitor_type_cache = {}
    seen = set()            # (site_pk, lower pass_no) inside this request
    prepared = []            # (row_no, site_obj, pass_no, pass_name, visitor_type_obj, status)
    errors = []

    def add_error(idx, pass_no, message):
        errors.append({"row": idx, "pass_no": pass_no, "message": message})

    for idx, item in enumerate(items, start=1):
        pass_no = item["pass_no"].strip()
        pass_name = item["pass_name"].strip()
        status = item.get("status", "Active")
        site_guid = str(item["site"])
        visitor_type_guid = str(item.get("visitor_type") or "")

        if site_guid not in site_cache:
            site_obj, error = _resolve_site(site_guid)
            if error:
                error["message"] = f"Row {idx}: {error['message']}"
                return error
            if not _can_access_site(user, site_obj):
                err = _forbidden()
                err["message"] = f"Row {idx}: {err['message']}"
                return err
            site_cache[site_guid] = site_obj

        site_obj = site_cache[site_guid]

        if visitor_type_guid and visitor_type_guid not in visitor_type_cache:
            vt_obj, error = _resolve_visitor_type(visitor_type_guid)
            if error:
                error["message"] = f"Row {idx}: {error['message']}"
                return error
            visitor_type_cache[visitor_type_guid] = vt_obj

        visitor_type_obj = visitor_type_cache.get(visitor_type_guid)

        marker = (site_obj.pk, pass_no.lower())
        if marker in seen:
            add_error(idx, pass_no, "Repeated in the file")
            continue
        seen.add(marker)
        prepared.append((idx, site_obj, pass_no, pass_name, visitor_type_obj, status))

    # duplicates already in the database (one query per site)
    for site_obj in site_cache.values():
        wanted = {p for (pk, p) in seen if pk == site_obj.pk}
        existing = set(
            Pass.objects.filter(site=site_obj)
            .annotate(p=Lower("pass_no"))
            .filter(p__in=wanted)
            .values_list("p", flat=True)
        )
        if existing:
            for idx, s, pass_no, _pt, _vt, _st in prepared:
                if s.pk == site_obj.pk and pass_no.lower() in existing:
                    add_error(idx, pass_no, "Already exists for this site")

    if errors:
        errors.sort(key=lambda e: e["row"])
        return {
            "success": False,
            "message": f"{len(errors)} row(s) have errors",
            "errors": errors,
            "status_code": 409,
        }

    objs = [
        Pass(
            pass_no=pass_no,
            pass_name=pass_name,
            site=site_obj,
            visitor_type=visitor_type_obj,
            status=status,
            created_by=user,
            updated_by=user,
        )
        for (_idx, site_obj, pass_no, pass_name, visitor_type_obj, status) in prepared
    ]

    try:
        with transaction.atomic():
            Pass.objects.bulk_create(objs)
    except IntegrityError:
        return _duplicate_response()

    return {
        "success": True,
        "message": f"{len(objs)} pass(es) created",
        "data": {"results": [_serialize(o) for o in objs]},
    }


def update_pass(guid, pass_no, pass_name, site, user, visitor_type=None, status="Active"):

    obj = Pass.objects.select_related("site", "visitor_type").filter(guid=guid).first()

    if obj is None:
        return {
            "success": False,
            "message": "Pass not found",
            "status_code": 404,
        }

    # the user must be allowed to touch the pass's current site ...
    if not _can_access_site(user, obj.site):
        return _forbidden()

    pass_no = pass_no.strip()
    pass_name = pass_name.strip()

    site_obj, error = _resolve_site(site)
    if error:
        return error

    # ... and the site it is being moved to
    if not _can_access_site(user, site_obj):
        return _forbidden()

    visitor_type_obj, error = _resolve_visitor_type(visitor_type)
    if error:
        return error

    if _duplicate_pass_no(site_obj, pass_no, exclude_pk=obj.pk):
        return _duplicate_response()

    obj.pass_no = pass_no
    obj.pass_name = pass_name
    obj.site = site_obj
    obj.visitor_type = visitor_type_obj
    obj.status = status
    obj.updated_by = user

    try:
        obj.save()
    except IntegrityError:
        return _duplicate_response()

    return {
        "success": True,
        "message": "Pass updated",
        "data": _serialize(obj),
    }


def delete_pass(guid, user=None):

    obj = Pass.objects.select_related("site").filter(guid=guid).first()

    if obj is None:
        return {
            "success": False,
            "message": "Pass not found",
            "status_code": 404,
        }

    if not _can_access_site(user, obj.site):
        return _forbidden()

    try:
        obj.delete()
    except ProtectedError:
        return {
            "success": False,
            "message": "Pass is in use and cannot be deleted",
            "status_code": 409,
        }

    return {
        "success": True,
        "message": "Pass deleted",
    }


def list_passes(page=None, page_size=None, search="", site_guid=None, status="", visitor_type_guid=None, user=None):

    qs = (
        Pass.objects
        .select_related("site", "visitor_type", "created_by", "updated_by")
        .order_by("-created_at", "-id")
    )

    if user is not None and not user.is_super_admin():
        own = user.site

        if own is None:
            return {
                "success": False,
                "message": "No site is assigned to your account",
                "status_code": 403,
            }

        # default to the user's own site
        if not site_guid:
            site_guid = str(own.guid)

        if str(site_guid) != str(own.guid) and not user_can_view_site(
            user, PASS_MENU_KEY, site_guid
        ):
            return {
                "success": False,
                "message": "You are not allowed to view this site",
                "status_code": 403,
            }

    if site_guid:
        qs = qs.filter(site__guid=site_guid)

    if status:
        qs = qs.filter(status=status)

    if visitor_type_guid:
        qs = qs.filter(visitor_type__guid=visitor_type_guid)

    search = (search or "").strip()
    if search:
        qs = qs.filter(
            Q(pass_no__icontains=search)
            | Q(pass_name__icontains=search)
            | Q(site__site_name__icontains=search)
            | Q(visitor_type__name__icontains=search)
        )

    # --------------------------------
    # FULL DATA
    # --------------------------------
    # if page is None and page_size is None:

    #     return {
    #         "success": True,
    #         "message": "Passes fetched",
    #         "data": {
    #             "results": [_serialize(obj) for obj in qs]
    #         },
    #     }

    if page is None and page_size is None:
        objs = list(qs)
        assigned = _assigned_map(objs)

        return {
            "success": True,
            "message": "Passes fetched",
            "data": {
                "results": [
                    _serialize(o, assigned.get((o.site_id, o.pass_no.lower())))
                    for o in objs
                ]
            },
        }
    # --------------------------------
    # PAGINATION
    # --------------------------------
    page = page or 1
    page_size = page_size or 10

    paginator = Paginator(qs, page_size)

    if page > paginator.num_pages and paginator.num_pages > 0:
        return {
            "success": False,
            "message": "Page number out of range",
            "status_code": 404,
        }

    page_obj = paginator.page(page)
    objs = list(page_obj.object_list)
    assigned = _assigned_map(objs)

    return {
        "success": True,
        "message": "Passes fetched",
        "data": {
            # "results": [_serialize(obj) for obj in page_obj.object_list],
            "results": [
                _serialize(o, assigned.get((o.site_id, o.pass_no.lower())))
                for o in objs
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            },
        },
    }