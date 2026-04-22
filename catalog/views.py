from django.db.models import Count, Q
from rest_framework import generics

from catalog.models import Category, Product
from catalog.serializers import CategorySerializer, ProductSerializer


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    authentication_classes = []
    permission_classes = []
    throttle_scope = "catalog"

    def get_queryset(self):
        return Category.objects.annotate(product_count=Count("products")).order_by("name")


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    authentication_classes = []
    permission_classes = []
    throttle_scope = "catalog"

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("category")
            .prefetch_related("variants")
            .all()
        )
        category_slug = self.request.query_params.get("category")
        query = self.request.query_params.get("q")
        featured = self.request.query_params.get("featured")
        new_arrival = self.request.query_params.get("new_arrival")
        sort = self.request.query_params.get("sort", "newest")
        limit = self.request.query_params.get("limit")

        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        if featured == "true":
            queryset = queryset.filter(is_featured=True)

        if new_arrival == "true":
            queryset = queryset.filter(is_new_arrival=True)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(category__slug__icontains=query)
                | Q(material__icontains=query)
                | Q(care_instructions__icontains=query)
                | Q(badge__icontains=query)
                | Q(tags__icontains=query)
                | Q(variants__color__icontains=query)
            ).distinct()

        if sort == "price-asc":
            queryset = queryset.order_by("price", "name")
        elif sort == "price-desc":
            queryset = queryset.order_by("-price", "name")
        elif sort == "rating":
            queryset = queryset.order_by("-rating", "-review_count", "name")
        elif sort == "bestseller":
            queryset = queryset.order_by("-review_count", "-rating", "name")
        else:
            queryset = queryset.order_by("-created_at", "name")

        if limit:
            try:
                limit_value = max(int(limit), 0)
            except ValueError:
                limit_value = 0

            if limit_value > 0:
                queryset = queryset[:limit_value]

        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    authentication_classes = []
    permission_classes = []
    lookup_field = "slug"
    throttle_scope = "catalog"

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("variants")
