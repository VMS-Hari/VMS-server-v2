from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .activitylog import read_logs
from .serializers import LogListSerializer


@extend_schema(tags=["Logs"], summary="List activity logs for a menu", request=LogListSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def log_list_api(request):
    s = LogListSerializer(data=request.data)
    if not s.is_valid():
        return Response(
            {"success": False, "message": "Validation failed", "errors": s.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    menu = s.validated_data["menu"]
    day = s.validated_data.get("date") or timezone.localdate()

    return Response({
        "success": True,
        "message": "Logs fetched",
        "data": {
            "menu": menu,
            "date": day.isoformat(),
            "results": read_logs(menu, day),
        },
    })