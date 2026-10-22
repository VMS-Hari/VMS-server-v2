from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.db.models import Q
# from .rolepermissionservices import user_can_view_site
from .rolepermissionservices import user_can_view_site, can_view_subsites

from .models import Category, Site, SiteModel, SiteType


def _serialize(obj):
    return {
        "guid": str(obj.guid),
        "site_code": obj.site_code,
        "site_name": obj.site_name,
        "site_model": {
            "guid": str(obj.site_model.guid),
            "name": obj.site_model.site_model,
        },
        "site_type": {
            "guid": str(obj.site_type.guid),
            "name": obj.site_type.site_type,
        },
        "category": {
            "guid": str(obj.category.guid),
            "name": obj.category.category_name,
        },
         "parent": {
            "guid": str(obj.parent.guid),
            "name": obj.parent.site_name,
        } if obj.parent_id else None,
        "contact": obj.contact,
        # relative URL, e.g. /media/site_images/2026/09/x.jpg
        "site_image": obj.site_image.url if obj.site_image else None,
        "address": obj.address,
        "created_by": obj.created_by.login_id if obj.created_by else None,
        "created_at": obj.created_at,
        "updated_by": obj.updated_by.login_id if obj.updated_by else None,
        "updated_at": obj.updated_at,
    }


def _duplicate_code(site_code, exclude_pk=None):
    qs = Site.objects.filter(site_code__iexact=site_code)

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def _resolve_refs(site_model, site_type, category):
    """Look up the three referenced records by guid.

    Returns (site_model_obj, site_type_obj, category_obj, error_dict_or_None).
    """
    site_model_obj = SiteModel.objects.filter(guid=site_model).first()
    if site_model_obj is None:
        return None, None, None, {
            "success": False,
            "message": "Selected site model does not exist",
            "status_code": 400,
        }

    site_type_obj = SiteType.objects.filter(guid=site_type).first()
    if site_type_obj is None:
        return None, None, None, {
            "success": False,
            "message": "Selected site type does not exist",
            "status_code": 400,
        }

    category_obj = Category.objects.filter(guid=category).first()
    if category_obj is None:
        return None, None, None, {
            "success": False,
            "message": "Selected category does not exist",
            "status_code": 400,
        }

    return site_model_obj, site_type_obj, category_obj, None


def _resolve_parent(parent_guid, exclude_pk=None):
    
    if not parent_guid:
        return None, None
 
    parent_obj = Site.objects.filter(guid=parent_guid).first()
    if parent_obj is None:
        return None, {
            "success": False,
            "message": "Selected parent site does not exist",
            "status_code": 400,
        }
 
    if exclude_pk and parent_obj.pk == exclude_pk:
        return None, {
            "success": False,
            "message": "A site cannot be its own parent",
            "status_code": 400,
        }

    if parent_obj.site_model.site_model.lower() != PARENT_SITE_MODEL_NAME.lower():
        return None, {
            "success": False,
            "message": "Selected parent must be a Parent site",
            "status_code": 400,
        }

    return parent_obj, None


def create_site(
    site_code,
    site_name,
    site_model,
    site_type,
    category,
    contact,
    site_image,
    address,
    user,
    parent=None,
):

    if _duplicate_code(site_code):
        return {
            "success": False,
            "message": "Site code already exists",
            "status_code": 409,
        }

    site_model_obj, site_type_obj, category_obj, error = _resolve_refs(
        site_model, site_type, category
    )
    if error:
        return error
    
    parent_obj, error = _resolve_parent(parent)
    if error:
        return error

    try:
        obj = Site.objects.create(
            site_code=site_code,
            site_name=site_name,
            site_model=site_model_obj,
            site_type=site_type_obj,
            category=category_obj,
            parent=parent_obj,
            contact=contact,
            site_image=site_image,
            address=address,
            created_by=user,
            updated_by=user,
        )
    except IntegrityError:
        return {
            "success": False,
            "message": "Site code already exists",
            "status_code": 409,
        }

    return {
        "success": True,
        "message": "Site created",
        "data": _serialize(obj),
    }


def update_site(
    guid,
    site_code,
    site_name,
    site_model,
    site_type,
    category,
    contact,
    address,
    user,
    site_image=None,
    parent=None,
):

    obj = Site.objects.filter(guid=guid).first()

    if obj is None:
        return {
            "success": False,
            "message": "Site not found",
            "status_code": 404,
        }

    if _duplicate_code(site_code, exclude_pk=obj.pk):
        return {
            "success": False,
            "message": "Site code already exists",
            "status_code": 409,
        }

    site_model_obj, site_type_obj, category_obj, error = _resolve_refs(
        site_model, site_type, category
    )
    if error:
        return error

    parent_obj, error = _resolve_parent(parent, exclude_pk=obj.pk)
    if error:
        return error

    obj.site_code = site_code
    obj.site_name = site_name
    obj.site_model = site_model_obj
    obj.site_type = site_type_obj
    obj.category = category_obj
    obj.parent = parent_obj
    obj.contact = contact
    obj.address = address
    obj.updated_by = user

    # Only replace the image when a new one was uploaded.
    if site_image:
        if obj.site_image:
            obj.site_image.delete(save=False)  # remove the old file from disk
        obj.site_image = site_image

    obj.save()

    return {
        "success": True,
        "message": "Site updated",
        "data": _serialize(obj),
    }


def delete_site(guid):

    obj = Site.objects.filter(guid=guid).first()

    if obj is None:
        return {
            "success": False,
            "message": "Site not found",
            "status_code": 404,
        }

    # image = obj.site_image
    # obj.delete()
    image = obj.site_image

    try:
        obj.delete()
    except ProtectedError:
        return {
            "success": False,
            "message": "Site has sub-sites or Tenant assigned so cannot be deleted",
            "status_code": 409,
        }

    # Clean the uploaded file off disk after the row is gone.
    if image:
        image.delete(save=False)

    return {
        "success": True,
        "message": "Site deleted",
    }


def list_sites(page=None, page_size=None, search="", site_guid=None, user=None):

    qs = (
        Site.objects
        .select_related(
            "site_model", "site_type", "category", "created_by", "updated_by"
        )
        .order_by("-created_at", "-id")
    )


    # if site_guid:
    #     if user is None or not user_can_view_site(
    #         user, "/system-config/site", site_guid
    #     ):
    #         return {
    #             "success": False,
    #             "message": "You are not allowed to view this site",
    #             "status_code": 403,
    #         }
    #     qs = qs.filter(Q(guid=site_guid) | Q(parent__guid=site_guid))


        # Super admin sees everything; everyone else is limited to own site
    # # (+ its sub-sites) or a sub-site they are allowed to view.
    # if user is not None and not user.is_super_admin():
    #     own = user.site

    #     if own is None:
    #         return {
    #             "success": False,
    #             "message": "No site is assigned to your account",
    #             "status_code": 403,
    #         }

    #     if not site_guid:
    #         site_guid = str(own.guid)

    #     if str(site_guid) != str(own.guid) and not user_can_view_site(
    #         user, "/system-config/site", site_guid
    #     ):
    #         return {
    #             "success": False,
    #             "message": "You are not allowed to view this site",
    #             "status_code": 403,
    #         }

    # if site_guid:
    #     qs = qs.filter(Q(guid=site_guid) | Q(parent__guid=site_guid))

    include_children = True  # super admin / no user: unchanged behaviour

    if user is not None and not user.is_super_admin():
        own = user.site

        if own is None:
            return {
                "success": False,
                "message": "No site is assigned to your account",
                "status_code": 403,
            }

        if not site_guid:
            site_guid = str(own.guid)

        if str(site_guid) != str(own.guid) and not user_can_view_site(
            user, "/system-config/site", site_guid
        ):
            return {
                "success": False,
                "message": "You are not allowed to view this site",
                "status_code": 403,
            }

        # Sub-sites are listed only when "view" is true for this menu
        include_children = can_view_subsites(user, "/system-config/site")

    if site_guid:
        condition = Q(guid=site_guid)
        if include_children:
            condition |= Q(parent__guid=site_guid)
        qs = qs.filter(condition)

    search = (search or "").strip()
    if search:
        qs = qs.filter(site_name__icontains=search)

    # --------------------------------
    # FULL DATA
    # --------------------------------
    if page is None and page_size is None:

        return {
            "success": True,
            "message": "Sites fetched",
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
        "message": "Sites fetched",
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


PARENT_SITE_MODEL_NAME = "Parent site"


def list_parent_sites(exclude_guid=None):

    qs = (
        Site.objects
        .filter(site_model__site_model__iexact=PARENT_SITE_MODEL_NAME)
        .order_by("site_name")
    )
 
    if exclude_guid:
        qs = qs.exclude(guid=exclude_guid)
 
    return {
        "success": True,
        "message": "Parent sites fetched",
        "data": {
            "results": [
                {
                    "guid": str(obj.guid),
                    "site_name": obj.site_name,
                }
                for obj in qs
            ]
        },
    }


def list_site_dropdown():
    """All sites for a dropdown: guid, site_name, site_model."""

    qs = (
        Site.objects
        .select_related("site_model")
        .order_by("site_name")
    )

    return {
        "success": True,
        "message": "Sites fetched",
        "data": {
            "results": [
                {
                    "guid": str(obj.guid),
                    "site_name": obj.site_name,
                    "site_model": {
                        "guid": str(obj.site_model.guid),
                        "name": obj.site_model.site_model,
                    },
                }
                for obj in qs
            ]
        },
    }