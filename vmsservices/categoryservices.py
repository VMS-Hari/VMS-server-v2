from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from .models import Category, Site


def _serialize(obj):
    return {
        "guid": str(obj.guid),
        "category_name": obj.category_name,
        "created_by": obj.created_by.login_id if obj.created_by else None,
        "created_at": obj.created_at,
        "updated_by": obj.updated_by.login_id if obj.updated_by else None,
        "updated_at": obj.updated_at,
    }


def _duplicate(category_name, exclude_pk=None):
    qs = Category.objects.filter(
        category_name__iexact=category_name
    )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return qs.exists()


def create_category(category_name, user):

    if _duplicate(category_name):
        return {
            "success": False,
            "message": "Category already exists",
            "status_code": 409,
        }

    try:
        obj = Category.objects.create(
            category_name=category_name,
            created_by=user,
            updated_by=user,
        )
    except IntegrityError:
        return {
            "success": False,
            "message": "Category already exists",
            "status_code": 409,
        }

    return {
        "success": True,
        "message": "Category created",
        "data": _serialize(obj),
    }


def update_category(guid, category_name, user):

    obj = Category.objects.filter(guid=guid).first()

    if obj is None:
        return {
            "success": False,
            "message": "Category not found",
            "status_code": 404,
        }

    if _duplicate(category_name, exclude_pk=obj.pk):
        return {
            "success": False,
            "message": "Category already exists",
            "status_code": 409,
        }

    obj.category_name = category_name
    obj.updated_by = user
    obj.save()

    return {
        "success": True,
        "message": "Category updated",
        "data": _serialize(obj),
    }

# def delete_category(guid):

#     deleted, _ = Category.objects.filter(guid=guid).delete()

#     if not deleted:
#         return {
#             "success": False,
#             "message": "Category not found",
#             "status_code": 404,
#         }

#     return {
#         "success": True,
#         "message": "Category deleted",
#     }



def delete_category(guid):
    category = Category.objects.filter(guid=guid).first()

    if category is None:
        return {
            "success": False,
            "message": "Category not found",
            "status_code": 404,
        }

    # Find sites using this category.
    related_sites = Site.objects.filter(category=category)

    if related_sites.exists():
        site_names = list(
            related_sites.values_list("site_name", flat=True)
        )

        return {
            "success": False,
            "message": (
                f"Cannot delete category '{category.category_name}' "
                f"because it is used by these sites: "
                f"{', '.join(site_names)}. "
                "Please reassign or delete those sites first."
            ),
            "status_code": 409,
        }

    try:
        category.delete()
    except ProtectedError:
        return {
            "success": False,
            "message": (
                "Cannot delete this category because "
                "other records are still using it."
            ),
            "status_code": 409,
        }

    return {
        "success": True,
        "message": "Category deleted successfully",
    }


def list_categories(page=None, page_size=None):

    qs = (
        Category.objects
        .select_related("created_by", "updated_by")
        .order_by("-created_at", "-id")
    )

    # --------------------------------
    # FULL DATA
    # --------------------------------
    if page is None and page_size is None:

        return {
            "success": True,
            "message": "Categories fetched",
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
        "message": "Categories fetched",
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