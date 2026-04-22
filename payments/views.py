from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.serializers import OrderSerializer
from payments.serializers import (
    PaymentTransactionSerializer,
    SasaPayCheckoutSerializer,
    SasaPayStatusSyncSerializer,
)
from payments.services import (
    create_sasapay_checkout,
    process_sasapay_callback,
    sync_sasapay_status,
)


class SasaPayCheckoutView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "payment_session"

    def post(self, request):
        serializer = SasaPayCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transaction_record = create_sasapay_checkout(
            order_number=serializer.validated_data["orderNumber"],
            redirect_url=serializer.validated_data["redirectUrl"],
            success_url=serializer.validated_data["successUrl"],
            failure_url=serializer.validated_data["failureUrl"],
        )
        transaction_record.refresh_from_db()

        return Response(
            {
                "order": OrderSerializer(transaction_record.order).data,
                "transaction": PaymentTransactionSerializer(transaction_record).data,
            },
            status=201,
        )


class SasaPayCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "payments_callback"

    def post(self, request):
        transaction_record = process_sasapay_callback(request.data)
        return Response(
            {
                "status": "ok",
                "orderNumber": transaction_record.order.order_number,
                "paymentStatus": transaction_record.order.payment_status,
            }
        )


class SasaPayStatusSyncView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "payment_status_sync"

    def post(self, request):
        serializer = SasaPayStatusSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transaction_record = sync_sasapay_status(
            order_number=serializer.validated_data["orderNumber"],
        )
        transaction_record.refresh_from_db()

        return Response(
            {
                "order": OrderSerializer(transaction_record.order).data,
                "transaction": PaymentTransactionSerializer(transaction_record).data,
            }
        )
