from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    SiteTypeCreateSerializer,
    SiteTypeDeleteSerializer,
    SiteTypeListSerializer,
    SiteTypeUpdateSerializer,
)
from .sitetypeservices import (
    create_site_type,
    delete_site_type,
    list_site_types,
    update_site_type,
)


def _invalid(serializer):
    return Response(
        {"success": False, "message": "Validation failed", "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _respond(result, ok_status=status.HTTP_200_OK):
    if result["success"]:
        return Response(result, status=ok_status)
    code = result.pop("status_code", status.HTTP_400_BAD_REQUEST)
    return Response(result, status=code)


@extend_schema(tags=["Site Type"], summary="Create site type", request=SiteTypeCreateSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def site_type_create_api(request):
    s = SiteTypeCreateSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = create_site_type(user=request.user, **s.validated_data)
    return _respond(result, status.HTTP_201_CREATED)


@extend_schema(tags=["Site Type"], summary="Update site type", request=SiteTypeUpdateSerializer)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def site_type_update_api(request):
    s = SiteTypeUpdateSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = update_site_type(user=request.user, **s.validated_data)
    return _respond(result)


@extend_schema(tags=["Site Type"], summary="Delete site type", request=SiteTypeDeleteSerializer)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def site_type_delete_api(request):
    s = SiteTypeDeleteSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = delete_site_type(guid=s.validated_data["guid"], user=request.user)
    return _respond(result)


@extend_schema(tags=["Site Type"], summary="List site types", request=SiteTypeListSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def site_type_list_api(request):
    s = SiteTypeListSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = list_site_types(
        page=s.validated_data.get("page"),
        page_size=s.validated_data.get("page_size"),
    )
    return _respond(result)