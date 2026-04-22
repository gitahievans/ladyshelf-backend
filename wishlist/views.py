from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from wishlist.models import WishlistItem
from wishlist.serializers import WishlistItemSerializer, WishlistMutationSerializer


class WishlistCollectionView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "wishlist"

    def get(self, request):
        items = WishlistItem.objects.filter(customer=request.user).select_related("product")
        serializer = WishlistItemSerializer(items, many=True)

        return Response(
            {
                "productIds": [item["productId"] for item in serializer.data],
            }
        )

    def post(self, request):
        serializer = WishlistMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, external_id=serializer.validated_data["productId"])
        WishlistItem.objects.get_or_create(customer=request.user, product=product)

        return Response({"productId": product.external_id}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        WishlistItem.objects.filter(customer=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistItemDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "wishlist"

    def delete(self, request, product_id: str):
        WishlistItem.objects.filter(
            customer=request.user,
            product__external_id=product_id,
        ).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
