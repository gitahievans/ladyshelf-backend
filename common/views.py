from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = "health"

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "wahi-fashion-backend",
                "version": "0.1.0",
            }
        )

