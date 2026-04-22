from django.urls import path

from payments.views import SasaPayCallbackView, SasaPayCheckoutView, SasaPayStatusSyncView


urlpatterns = [
    path("sasapay/checkout", SasaPayCheckoutView.as_view(), name="sasapay-checkout"),
    path("sasapay/callback", SasaPayCallbackView.as_view(), name="sasapay-callback"),
    path("sasapay/status-sync", SasaPayStatusSyncView.as_view(), name="sasapay-status-sync"),
]
