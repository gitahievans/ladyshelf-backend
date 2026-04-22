from django.urls import path

from orders.views import OrderDetailView, OrderListView

urlpatterns = [
    path("orders", OrderListView.as_view(), name="orders-list"),
    path("orders/<str:order_number>", OrderDetailView.as_view(), name="orders-detail"),
]
