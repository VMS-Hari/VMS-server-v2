from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    SiteModelCreateSerializer,
    SiteModelDeleteSerializer,
    SiteModelListSerializer,
    SiteModelUpdateSerializer,
)
from .sitemodelservices import (
    create_site_model,
    delete_site_model,
    list_site_models,
    update_site_model,
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


@extend_schema(tags=["Site Model"], summary="Create site model", request=SiteModelCreateSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def site_model_create_api(request):
    s = SiteModelCreateSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = create_site_model(user=request.user, **s.validated_data)
    return _respond(result, status.HTTP_201_CREATED)


@extend_schema(tags=["Site Model"], summary="Update site model", request=SiteModelUpdateSerializer)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def site_model_update_api(request):
    s = SiteModelUpdateSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = update_site_model(user=request.user, **s.validated_data)
    return _respond(result)


@extend_schema(tags=["Site Model"], summary="Delete site model", request=SiteModelDeleteSerializer)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def site_model_delete_api(request):
    s = SiteModelDeleteSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = delete_site_model(guid=s.validated_data["guid"], user=request.user)
    return _respond(result)


@extend_schema(tags=["Site Model"], summary="List site models", request=SiteModelListSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def site_model_list_api(request):
    s = SiteModelListSerializer(data=request.data)
    if not s.is_valid():
        return _invalid(s)
    result = list_site_models(
        page=s.validated_data.get("page"),
        page_size=s.validated_data.get("page_size"),
    )
    return _respond(result)