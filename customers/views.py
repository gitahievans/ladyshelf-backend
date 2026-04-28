from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import Address
from customers.serializers import (
    AddressSerializer,
    CustomerProfileSerializer,
    CustomerProfileUpdateSerializer,
)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "account"

    def get(self, request):
        serializer = CustomerProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = CustomerProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = CustomerProfileSerializer(request.user)
        return Response(response_serializer.data)


class AddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer
    throttle_scope = "account"

    def get_queryset(self):
        return Address.objects.filter(customer=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["customer"] = self.request.user
        return context


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer
    throttle_scope = "account"

    def get_queryset(self):
        return Address.objects.filter(customer=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["customer"] = self.request.user
        return context

