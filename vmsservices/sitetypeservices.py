from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from .activitylog import write_log

from .models import SiteType, Site

LOG_MODULE = "site_type"

def _serialize(obj):
    return {
        "guid": str(obj.guid),
        "site_type": obj.site_type,
        "site_type_description": obj.site_type_description,
        "created_by": obj.created_by.login_id if obj.created_by else None,
        "created_at": obj.created_at,
        "updated_by": obj.updated_by.login_id if obj.updated_by else None,
        "updated_at": obj.updated_at,
    }


def _duplicate(site_type, exclude_pk=None):
    qs = SiteType.objects.filter(
        site_type__iexact=site_type
    )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def _duplicate_description(site_type_description, exclude_pk=None):
    # Blank descriptions are allowed to repeat (many site types can have no
    # description) — only a non-empty description is checked for duplicates.
    if not site_type_description or not site_type_description.strip():
        return False

    qs = SiteType.objects.filter(
        site_type_description__iexact=site_type_description.strip()
    )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def create_site_type(site_type, site_type_description, user):

    if _duplicate(site_type):
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed: site type '{site_type}' already exists",
                  status="FAILED")
        return {
            "success": False,
            "message": "Site type already exists",
            "status_code": 409,
        }

    if _duplicate_description(site_type_description):
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed for '{site_type}': description already used by another site type",
                  status="FAILED")
        return {
            "success": False,
            "message": "This description is already used by another site type",
            "status_code": 409,
        }

    try:
        obj = SiteType.objects.create(
            site_type=site_type,
            site_type_description=site_type_description,
            created_by=user,
            updated_by=user,
        )
    except IntegrityError:
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed: site type '{site_type}' already exists",
                  status="FAILED")
        return {
            "success": False,
            "message": "Site type already exists",
            "status_code": 409,
        }
    write_log(LOG_MODULE, "Created", user,
              f"Created site type '{obj.site_type}'",
              ref=str(obj.guid))

    return {
        "success": True,
        "message": "Site type created",
        "data": _serialize(obj),
    }


def update_site_type(guid, site_type, site_type_description, user):

    obj = SiteType.objects.filter(guid=guid).first()

    if obj is None:
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed: site type {guid} not found",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site type not found",
            "status_code": 404,
        }

    if _duplicate(site_type, exclude_pk=obj.pk):
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed: site type '{site_type}' already exists",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site type already exists",
            "status_code": 409,
        }

    if _duplicate_description(site_type_description, exclude_pk=obj.pk):
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed for '{obj.site_type}': description already used by another site type",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "This description is already used by another site type",
            "status_code": 409,
        }

    old_name = obj.site_type
    old_desc = obj.site_type_description

    obj.site_type = site_type
    obj.site_type_description = site_type_description
    obj.updated_by = user
    obj.save()

    changes = []
    if old_name != site_type:
        changes.append(f"name '{old_name}' -> '{site_type}'")
    if old_desc != site_type_description:
        changes.append(f"description '{old_desc}' -> '{site_type_description}'")

    write_log(LOG_MODULE, "Updated", user,
              f"Updated site type '{old_name}': " + (", ".join(changes) or "no field changes"),
              ref=str(obj.guid))

    return {
        "success": True,
        "message": "Site type updated",
        "data": _serialize(obj),
    }


# def delete_site_type(guid):

#     deleted, _ = SiteType.objects.filter(guid=guid).delete()

#     if not deleted:
#         return {
#             "success": False,
#             "message": "Site type not found",
#             "status_code": 404,
#         }

#     return {
#         "success": True,
#         "message": "Site type deleted",
#     }


def delete_site_type(guid, user=None):
    site_type = SiteType.objects.filter(guid=guid).first()

    if site_type is None:
        write_log(LOG_MODULE, "Failed", user,
                  f"Delete failed: site type {guid} not found",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site type not found",
            "status_code": 404,
        }
    name = site_type.site_type
    related_sites = Site.objects.filter(site_type=site_type)

    if related_sites.exists():
        site_names = list(
            related_sites.values_list("site_name", flat=True)
        )
        write_log(LOG_MODULE, "Failed", user,
                  f"Delete failed for '{name}': used by sites {', '.join(site_names)}",
                  status="FAILED", ref=str(guid))

        return {
            "success": False,
            "message": (
                f"Cannot delete site type '{site_type.site_type}' "
                f"because it is used by these sites: "
                f"{', '.join(site_names)}. "
                "Please reassign or delete those sites first."
            ),
            "status_code": 409,
        }

    try:
        site_type.delete()
    except ProtectedError:
        write_log(LOG_MODULE, "Failed", user,
                  f"Delete failed for '{name}': other records still use it",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": (
                "Cannot delete this site type because "
                "other records are still using it."
            ),
            "status_code": 409,
        }

    write_log(LOG_MODULE, "Deleted", user,
              f"Deleted site type '{name}'",
              ref=str(guid))

    return {
        "success": True,
        "message": "Site type deleted successfully",
    }



def list_site_types(page=None, page_size=None):

    qs = (
        SiteType.objects
        .select_related("created_by", "updated_by")
        .order_by("-created_at", "-id")
    )

    # --------------------------------
    # FULL DATA
    # --------------------------------
    if page is None and page_size is None:

        return {
            "success": True,
            "message": "Site types fetched",
            "data": {
                "results": [
                    _serialize(obj)
                    for obj in qs
                ]
            },
        }

    # --------------------------------
    # PAGINATION
    # --------------------------------
    paginator = Paginator(qs, page_size)

    if page > paginator.num_pages and paginator.num_pages > 0:
        return {
            "success": False,
            "message": "Page number out of range",
            "status_code": 404,
        }

    page_obj = paginator.page(page)

    return {
        "success": True,
        "message": "Site types fetched",
        "data": {
            "results": [
                _serialize(obj)
                for obj in page_obj.object_list
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            },
        },
    }