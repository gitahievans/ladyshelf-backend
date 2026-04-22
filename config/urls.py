from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

admin.site.site_header = "Wahi Fashion Admin"
admin.site.site_title = "Wahi Fashion Admin Portal"
admin.site.index_title = "Store Operations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("common.urls")),
    path("api/v1/account/", include("customers.urls")),
    path("api/v1/account/", include("orders.account_urls")),
    path("api/v1/", include("orders.urls")),
    path("api/v1/catalog/", include("catalog.urls")),
    path("api/v1/checkout/", include("checkout.urls")),
    path("api/v1/payments/", include("payments.urls")),
    path("api/v1/wishlist/", include("wishlist.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
