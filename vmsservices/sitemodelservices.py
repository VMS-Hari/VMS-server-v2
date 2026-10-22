from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from .activitylog import write_log

from .models import SiteModel, Site
LOG_MODULE = "site_model"


def _serialize(obj):
    return {
        "guid": str(obj.guid),
        "site_model": obj.site_model,
        "site_model_description": obj.site_model_description,
        "created_by": obj.created_by.login_id if obj.created_by else None,
        "created_at": obj.created_at,
        "updated_by": obj.updated_by.login_id if obj.updated_by else None,
        "updated_at": obj.updated_at,
    }


def _duplicate(site_model, exclude_pk=None):
    qs = SiteModel.objects.filter(
        site_model__iexact=site_model
    )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def _duplicate_description(site_model_description, exclude_pk=None):
    # Blank descriptions are allowed to repeat (many site models can have no
    # description) — only a non-empty description is checked for duplicates.
    if not site_model_description or not site_model_description.strip():
        return False

    qs = SiteModel.objects.filter(
        site_model_description__iexact=site_model_description.strip()
    )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def create_site_model(site_model, site_model_description, user):

    if _duplicate(site_model):
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed: site model '{site_model}' already exists",
                  status="FAILED")
        return {
            "success": False,
            "message": "Site model already exists",
            "status_code": 409,
        }

    if _duplicate_description(site_model_description):
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed for '{site_model}': description already used by another site model",
                  status="FAILED")
        return {
            "success": False,
            "message": "This description is already used by another site model",
            "status_code": 409,
        }

    try:
        obj = SiteModel.objects.create(
            site_model=site_model,
            site_model_description=site_model_description,
            created_by=user,
            updated_by=user,
        )
    except IntegrityError:
        write_log(LOG_MODULE, "Failed", user,
                  f"Create failed: site model '{site_model}' already exists",
                  status="FAILED")
        return {
            "success": False,
            "message": "Site model already exists",
            "status_code": 409,
        }
    write_log(LOG_MODULE, "Created", user,
              f"Created site model '{obj.site_model}'",
              ref=str(obj.guid))
    return {
        "success": True,
        "message": "Site model created",
        "data": _serialize(obj),
    }


def update_site_model(guid, site_model, site_model_description, user):

    obj = SiteModel.objects.filter(guid=guid).first()

    if obj is None:
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed: site model {guid} not found",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site model not found",
            "status_code": 404,
        }

    if _duplicate(site_model, exclude_pk=obj.pk):
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed: site model '{site_model}' already exists",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site model already exists",
            "status_code": 409,
        }

    if _duplicate_description(site_model_description, exclude_pk=obj.pk):
        write_log(LOG_MODULE, "Failed", user,
                  f"Update failed for '{obj.site_model}': description already used by another site model",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "This description is already used by another site model",
            "status_code": 409,
        }
    old_name = obj.site_model
    old_desc = obj.site_model_description

    obj.site_model = site_model
    obj.site_model_description = site_model_description
    obj.updated_by = user
    obj.save()

    changes = []
    if old_name != site_model:
        changes.append(f"name '{old_name}' -> '{site_model}'")
    if old_desc != site_model_description:
        changes.append(f"description '{old_desc}' -> '{site_model_description}'")

    write_log(LOG_MODULE, "Updated", user,
              f"Updated site model '{old_name}': " + (", ".join(changes) or "no field changes"),
              ref=str(obj.guid))

    return {
        "success": True,
        "message": "Site model updated",
        "data": _serialize(obj),
    }


# def delete_site_model(guid):

#     deleted, _ = SiteModel.objects.filter(guid=guid).delete()

#     if not deleted:
#         return {
#             "success": False,
#             "message": "Site model not found",
#             "status_code": 404,
#         }

#     return {
#         "success": True,
#         "message": "Site model deleted",
#     }



def delete_site_model(guid, user=None):
    site_model = SiteModel.objects.filter(guid=guid).first()

    if site_model is None:
        write_log(LOG_MODULE, "Failed", user,
                  f"Delete failed: site model {guid} not found",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": "Site model not found",
            "status_code": 404,
        }
    name = site_model.site_model
    # Find sites using this site model.
    related_sites = Site.objects.filter(site_model=site_model)

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
                f"Cannot delete site model '{site_model.site_model}' "
                f"because it is used by these sites: "
                f"{', '.join(site_names)}. "
                "Please reassign or delete those sites first."
            ),
            "status_code": 409,
        }

    try:
        site_model.delete()
    except ProtectedError:
        write_log(LOG_MODULE, "Failed", user,
                  f"Delete failed for '{name}': other records still use it",
                  status="FAILED", ref=str(guid))
        return {
            "success": False,
            "message": (
                "Cannot delete this site model because "
                "other records are still using it."
            ),
            "status_code": 409,
        }
    write_log(LOG_MODULE, "Deleted", user,
              f"Deleted site model '{name}'",
              ref=str(guid))

    return {
        "success": True,
        "message": "Site model deleted successfully",
    }



def list_site_models(page=None, page_size=None):

    qs = (
        SiteModel.objects
        .select_related("created_by", "updated_by")
        .order_by("-created_at", "-id")
    )

    # --------------------------------
    # FULL DATA
    # --------------------------------
    if page is None and page_size is None:

        return {
            "success": True,
            "message": "Site models fetched",
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

    return {
        "success": True,
        "message": "Site models fetched",
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