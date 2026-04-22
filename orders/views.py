from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from orders.models import Order
from orders.serializers import OrderSerializer


class OrderQuerysetMixin:
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = "account_orders"

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related("items", "items__product")
            .select_related("customer")
        )


class AccountOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    throttle_scope = "account_orders"

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related("items", "items__product")
            .select_related("customer")
        )


class OrderListView(OrderQuerysetMixin, generics.ListAPIView):
    pass


class OrderDetailView(OrderQuerysetMixin, generics.RetrieveAPIView):
    lookup_field = "order_number"
