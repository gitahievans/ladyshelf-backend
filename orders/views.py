from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.serializers import OrderCancellationCreateSerializer, OrderSerializer
from orders.services import cancel_order_items


class OrderQuerysetMixin:
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = "account_orders"

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related(
                "items",
                "items__product",
                "cancellations",
                "cancellations__items",
                "cancellations__items__order_item",
            )
            .select_related("customer")
        )


class AccountOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = "account_orders"

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related(
                "items",
                "items__product",
                "cancellations",
                "cancellations__items",
                "cancellations__items__order_item",
            )
            .select_related("customer")
        )


class OrderListView(OrderQuerysetMixin, generics.ListAPIView):
    pass


class OrderDetailView(OrderQuerysetMixin, generics.RetrieveAPIView):
    lookup_field = "order_number"


class AccountOrderCancellationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "account_orders"

    def post(self, request, order_number):
        input_serializer = OrderCancellationCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        order = generics.get_object_or_404(
            Order.objects.filter(customer=request.user),
            order_number=order_number,
        )
        updated_order = cancel_order_items(
            order=order,
            customer=request.user,
            cancellation_items=input_serializer.validated_data["items"],
            reason=input_serializer.validated_data["reason"],
            note=input_serializer.validated_data.get("note", ""),
        )
        serializer = OrderSerializer(updated_order)
        return Response(serializer.data)
