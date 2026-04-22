from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from checkout.serializers import (
    CheckoutOrderCreateRequestSerializer,
    CheckoutQuoteRequestSerializer,
    PickupLocationSerializer,
)
from checkout.services import get_active_pickup_location
from orders.serializers import OrderSerializer
from orders.services import build_checkout_quote_data, create_order_from_checkout


class CheckoutQuoteView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_quote"

    def post(self, request):
        serializer = CheckoutQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_lines = serializer.validated_data["cart"]
        delivery_details = serializer.validated_data["deliveryDetails"]
        payment_selection = serializer.validated_data.get("paymentSelection")
        quote_data = build_checkout_quote_data(
            cart_lines=cart_lines,
            delivery_details=delivery_details,
            payment_selection=payment_selection,
        )

        return Response(quote_data)


class PickupInfoView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_info"

    def get(self, request):
        pickup_location = get_active_pickup_location()
        serializer = PickupLocationSerializer(pickup_location)
        return Response(serializer.data)


class CheckoutOrderCreateView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "checkout_order"

    def post(self, request):
        serializer = CheckoutOrderCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = request.user if getattr(request.user, "is_authenticated", False) else None
        order = create_order_from_checkout(
            cart_lines=serializer.validated_data["cart"],
            delivery_details=serializer.validated_data["deliveryDetails"],
            payment_selection=serializer.validated_data["paymentSelection"],
            customer=customer,
        )

        response_serializer = OrderSerializer(order)
        return Response(response_serializer.data, status=201)
