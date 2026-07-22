from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Category, Product, ProductVariant
from catalog.serializers import CategorySerializer, ProductSerializer, ProductVariantSerializer
from checkout.models import DeliverySettings, DeliveryZone, PickupLocation
from admin_portal.access import get_staff_access
from admin_portal.models import (
    AdminStaffAccess,
    ImageGenerationBatch,
    ProductImageCandidate,
    ProductImageGeneration,
)
from admin_portal.permissions import IsAdminOwner, IsAdminStaff
from admin_portal.serializers import (
    AdminCategoryWriteSerializer,
    AdminCustomerDetailSerializer,
    AdminCustomerListItemSerializer,
    AdminDashboardSummarySerializer,
    AdminDeliveryZoneSerializer,
    AdminDeliverySettingsSerializer,
    AdminInventoryRowSerializer,
    AdminManualPaymentSerializer,
    AdminOrderDetailSerializer,
    AdminOrderListItemSerializer,
    AdminOrderUpdateSerializer,
    AdminPaymentDetailSerializer,
    AdminPaymentListItemSerializer,
    AdminPickupLocationSerializer,
    AdminProductWriteSerializer,
    AdminStaffCreateSerializer,
    AdminStaffRecordSerializer,
    AdminStaffUpdateSerializer,
    AdminStockUpdateSerializer,
    AdminVariantWriteSerializer,
    CandidateRegenerationSerializer,
    ImageGenerationBatchCreateSerializer,
    ImageGenerationPublishSerializer,
    ImageGenerationBatchSerializer,
    ProductImageCandidateSerializer,
    ProductImageGenerationSerializer,
    AdminStaffUserSerializer,
    serialize_permission_set,
)
from admin_portal.image_generation.services import (
    ImageGenerationWorkflowError,
    approve_candidate,
    create_batch,
    publish_generation,
    recompute_batch,
    regenerate_candidate,
    reject_candidate,
    restore_previous_gallery,
)
from admin_portal.image_generation.storage import ImageStorageError
from customers.models import CustomerProfile
from orders.models import Order
from payments.receipts import issue_receipt_for_paid_order, resend_receipt_for_order
from payments.models import PaymentTransaction


class AdminMeView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    def get(self, request):
        staff_access = get_staff_access(request.user)
        serializer = AdminStaffUserSerializer(staff_access)
        return Response(serializer.data)


class AdminPermissionsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    def get(self, request):
        staff_access = get_staff_access(request.user)
        return Response(serialize_permission_set(staff_access))


class AdminStaffListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def get_queryset(self):
        return AdminStaffAccess.objects.select_related("customer").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminStaffCreateSerializer

        return AdminStaffRecordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff_access = serializer.save()
        record_serializer = AdminStaffRecordSerializer(staff_access)

        return Response(record_serializer.data, status=status.HTTP_201_CREATED)


class AdminStaffDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    serializer_class = AdminStaffUpdateSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return AdminStaffAccess.objects.select_related("customer").all()

    def retrieve(self, request, *args, **kwargs):
        serializer = AdminStaffRecordSerializer(self.get_object())
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        serializer = AdminStaffRecordSerializer(self.get_object())
        response.data = serializer.data
        return response


class AdminDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    def get(self, request):
        fulfillment_statuses = [
            Order.OrderStatus.NEW,
            Order.OrderStatus.PAID,
            Order.OrderStatus.AWAITING_DELIVERY_FEE_CONFIRMATION,
            Order.OrderStatus.READY_FOR_DISPATCH,
            Order.OrderStatus.OUT_FOR_DELIVERY,
            Order.OrderStatus.READY_FOR_PICKUP,
        ]
        payment_issue_statuses = [
            PaymentTransaction.Status.INITIATED,
            PaymentTransaction.Status.PENDING,
            PaymentTransaction.Status.FAILED,
        ]

        recent_paid_orders = Order.objects.select_related("customer").filter(
            payment_status=Order.PaymentStatus.PAID,
        )[:5]
        payment_issues = PaymentTransaction.objects.select_related("order").filter(
            status__in=payment_issue_statuses,
        )[:5]
        low_stock_items = ProductVariant.objects.select_related("product").filter(
            stock__lte=3,
        ).order_by("stock", "product__name")[:6]

        payload = {
            "awaitingPaymentOrders": Order.objects.filter(
                order_status=Order.OrderStatus.AWAITING_PAYMENT,
            ).count(),
            "fulfillmentActionOrders": Order.objects.filter(
                order_status__in=fulfillment_statuses,
            ).count(),
            "lowStockVariants": ProductVariant.objects.filter(stock__lte=3).count(),
            "recentPaidOrders": [
                {
                    "orderNumber": order.order_number,
                    "customerLabel": order.customer.email if order.customer else order.guest_email,
                    "total": order.total,
                    "currency": order.currency,
                    "paymentStatus": order.payment_status,
                    "orderStatus": order.order_status,
                    "deliveryMode": order.delivery_mode,
                    "createdAt": order.created_at,
                }
                for order in recent_paid_orders
            ],
            "paymentIssueCount": PaymentTransaction.objects.filter(
                status__in=payment_issue_statuses,
            ).count(),
            "paymentIssues": [
                {
                    "id": str(transaction.pk),
                    "orderNumber": transaction.order.order_number,
                    "status": transaction.status,
                    "amount": transaction.amount,
                    "currency": transaction.currency,
                    "provider": transaction.provider,
                    "createdAt": transaction.created_at,
                }
                for transaction in payment_issues
            ],
            "lowStockItems": [
                {
                    "id": str(variant.pk),
                    "productName": variant.product.name,
                    "sku": variant.sku,
                    "size": variant.size,
                    "color": variant.color,
                    "stock": variant.stock,
                }
                for variant in low_stock_items
            ],
        }
        serializer = AdminDashboardSummarySerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminOrderListItemSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        queryset = Order.objects.select_related("customer").all()
        order_status = self.request.query_params.get("orderStatus")
        payment_status = self.request.query_params.get("paymentStatus")
        delivery_mode = self.request.query_params.get("deliveryMode")
        manual_fee = self.request.query_params.get("manualFee")
        customer_type = self.request.query_params.get("customerType")
        query = self.request.query_params.get("q", "").strip()

        if order_status:
            queryset = queryset.filter(order_status=order_status)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if delivery_mode:
            queryset = queryset.filter(delivery_mode=delivery_mode)
        if manual_fee in {"true", "false"}:
            queryset = queryset.filter(
                manual_delivery_fee_confirmation_required=manual_fee == "true"
            )
        if customer_type == "guest":
            queryset = queryset.filter(customer__isnull=True)
        if customer_type == "account":
            queryset = queryset.filter(customer__isnull=False)
        if query:
            queryset = queryset.filter(
                Q(order_number__icontains=query)
                | Q(customer__email__icontains=query)
                | Q(guest_email__icontains=query)
            )

        return queryset[:100]


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    lookup_field = "order_number"
    throttle_scope = "admin"

    def get_queryset(self):
        return (
            Order.objects.select_related("customer")
            .prefetch_related(
                "items",
                "items__product",
                "payment_transactions",
                "cancellations",
                "cancellations__items",
                "cancellations__items__order_item",
            )
            .all()
        )

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return AdminOrderUpdateSerializer

        return AdminOrderDetailSerializer

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        serializer = AdminOrderDetailSerializer(self.get_object())
        response.data = serializer.data
        return response


class AdminOrderMarkPaidView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    @transaction.atomic
    def post(self, request, order_number):
        input_serializer = AdminManualPaymentSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        validated_data = input_serializer.validated_data

        order = get_object_or_404(
            Order.objects.select_for_update(of=("self",))
            .select_related("customer")
            .prefetch_related("items", "items__product", "payment_transactions"),
            order_number=order_number,
        )

        if order.payment_timing != Order.PaymentTiming.PAY_ON_DELIVERY:
            return Response(
                {"detail": "Only pay-on-delivery orders can be manually marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "This order has already been marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.order_status == Order.OrderStatus.CANCELLED or order.total <= 0:
            return Response(
                {"detail": "Cancelled orders cannot be marked as paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_collected = validated_data.get("amountCollected") or order.total
        payment_reference = validated_data.get("paymentReference", "").strip()
        staff_note = validated_data.get("staffNote", "").strip()
        payment_method = validated_data.get("paymentMethod", order.payment_method)

        order.payment_method = payment_method
        order.payment_status = Order.PaymentStatus.PAID
        order.order_status = Order.OrderStatus.PAID
        order.payment_expires_at = None
        if staff_note:
            note = f"Manual payment confirmed: {staff_note}"
            order.internal_notes = (
                f"{order.internal_notes.rstrip()}\n{note}"
                if order.internal_notes.strip()
                else note
            )
        order.save(
            update_fields=[
                "payment_method",
                "payment_status",
                "order_status",
                "payment_expires_at",
                "internal_notes",
                "updated_at",
            ]
        )

        issue_receipt_for_paid_order(
            order=order,
            payment_reference=payment_reference,
            total_paid=amount_collected,
            created_by=request.user,
        )

        order.refresh_from_db()
        serializer = AdminOrderDetailSerializer(order)
        return Response(serializer.data)


class AdminOrderReceiptResendView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    def post(self, request, order_number):
        order = get_object_or_404(
            Order.objects.select_related("customer")
            .prefetch_related("items", "items__product", "payment_transactions"),
            order_number=order_number,
        )
        resend_receipt_for_order(order)
        order.refresh_from_db()
        serializer = AdminOrderDetailSerializer(order)
        return Response(serializer.data)


class AdminPaymentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminPaymentListItemSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related("order").all()
        status_value = self.request.query_params.get("status")
        query = self.request.query_params.get("q", "").strip()

        if status_value:
            queryset = queryset.filter(status=status_value)
        if query:
            queryset = queryset.filter(
                Q(order__order_number__icontains=query)
                | Q(merchant_reference__icontains=query)
                | Q(merchant_request_id__icontains=query)
                | Q(checkout_request_id__icontains=query)
                | Q(transaction_code__icontains=query)
            )

        return queryset[:100]


class AdminPaymentDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminPaymentDetailSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return PaymentTransaction.objects.select_related("order").all()


class AdminCustomerListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminCustomerListItemSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        queryset = CustomerProfile.objects.annotate(orderCount=Count("orders"))
        query = self.request.query_params.get("q", "").strip()

        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(phone__icontains=query)
            )

        return queryset[:100]


class AdminCustomerDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminCustomerDetailSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return (
            CustomerProfile.objects.prefetch_related(
                "addresses",
                "orders",
                "wishlist_items",
                "wishlist_items__product",
            )
            .all()
        )


class OwnerMutationMixin:
    def get_permissions(self):
        if self.request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            return [IsAuthenticated(), IsAdminOwner()]

        return [IsAuthenticated(), IsAdminStaff()]


class AdminCategoryListCreateView(OwnerMutationMixin, generics.ListCreateAPIView):
    throttle_scope = "admin"

    def get_queryset(self):
        return Category.objects.annotate(product_count=Count("products")).order_by("name")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminCategoryWriteSerializer

        return CategorySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(CategorySerializer(category).data, status=status.HTTP_201_CREATED)


class AdminCategoryDetailView(OwnerMutationMixin, generics.RetrieveUpdateDestroyAPIView):
    throttle_scope = "admin"

    def get_queryset(self):
        return Category.objects.annotate(product_count=Count("products")).all()

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return AdminCategoryWriteSerializer

        return CategorySerializer

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        return Response(CategorySerializer(self.get_object()).data)


class AdminProductListCreateView(OwnerMutationMixin, generics.ListCreateAPIView):
    throttle_scope = "admin"

    def get_queryset(self):
        queryset = Product.objects.select_related("category").prefetch_related("variants")
        query = self.request.query_params.get("q", "").strip()
        category = self.request.query_params.get("category", "").strip()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(description__icontains=query)
                | Q(variants__sku__icontains=query)
            ).distinct()
        if category:
            queryset = queryset.filter(category__slug=category)

        return queryset[:100]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminProductWriteSerializer

        return ProductSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(OwnerMutationMixin, generics.RetrieveUpdateDestroyAPIView):
    throttle_scope = "admin"

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("variants")

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return AdminProductWriteSerializer

        return ProductSerializer

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        return Response(ProductSerializer(self.get_object()).data)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        active_generations = product.image_generations.filter(
            status__in=ProductImageGeneration.ACTIVE_STATUSES
        )
        if ProductImageCandidate.objects.filter(
            generation__in=active_generations,
            storage_path__gt="",
        ).exists():
            return Response(
                {"detail": "Resolve the active generated-image review before deleting this product."},
                status=status.HTTP_409_CONFLICT,
            )
        batch_ids = list(active_generations.values_list("batch_id", flat=True))
        active_generations.update(status=ProductImageGeneration.Status.CANCELLED)
        product.delete()
        for batch_id in batch_ids:
            recompute_batch(batch_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminProductVariantCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    serializer_class = AdminVariantWriteSerializer
    throttle_scope = "admin"

    def perform_create(self, serializer):
        product = generics.get_object_or_404(Product, pk=self.kwargs["pk"])
        serializer.save(product=product)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = generics.get_object_or_404(Product, pk=self.kwargs["pk"])
        variant = serializer.save(product=product)
        return Response(ProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)


class AdminVariantDetailView(OwnerMutationMixin, generics.RetrieveUpdateDestroyAPIView):
    throttle_scope = "admin"

    def get_queryset(self):
        return ProductVariant.objects.select_related("product")

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return AdminVariantWriteSerializer

        return ProductVariantSerializer

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        return Response(ProductVariantSerializer(self.get_object()).data)


class AdminInventoryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminInventoryRowSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        queryset = ProductVariant.objects.select_related("product").order_by("product__name", "sku")
        query = self.request.query_params.get("q", "").strip()
        low_stock = self.request.query_params.get("lowStock")

        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query)
                | Q(sku__icontains=query)
                | Q(color__icontains=query)
                | Q(size__icontains=query)
            )
        if low_stock == "true":
            queryset = queryset.filter(stock__lte=3)

        return queryset[:150]


class AdminVariantStockUpdateView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = AdminStockUpdateSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return ProductVariant.objects.select_related("product")

    def partial_update(self, request, *args, **kwargs):
        super().partial_update(request, *args, **kwargs)
        return Response(AdminInventoryRowSerializer(self.get_object()).data)


class AdminDeliveryZoneListCreateView(OwnerMutationMixin, generics.ListCreateAPIView):
    serializer_class = AdminDeliveryZoneSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return DeliveryZone.objects.all()


class AdminDeliveryZoneDetailView(OwnerMutationMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminDeliveryZoneSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return DeliveryZone.objects.all()


class AdminDeliverySettingsDetailView(OwnerMutationMixin, generics.RetrieveUpdateAPIView):
    serializer_class = AdminDeliverySettingsSerializer
    throttle_scope = "admin"

    def get_object(self):
        return DeliverySettings.objects.filter(is_active=True).first() or DeliverySettings.objects.first()


class AdminPickupLocationListCreateView(OwnerMutationMixin, generics.ListCreateAPIView):
    serializer_class = AdminPickupLocationSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return PickupLocation.objects.all()


class AdminPickupLocationDetailView(OwnerMutationMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminPickupLocationSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return PickupLocation.objects.all()


def image_generation_queryset():
    return ImageGenerationBatch.objects.select_related("requested_by").prefetch_related(
        "generations",
        "generations__product",
        "generations__candidates",
    )


def workflow_error_response(error: ImageGenerationWorkflowError) -> Response:
    conflict_codes = {"active_generation", "invalid_candidate_state", "incomplete_approval"}
    return Response(
        {"detail": error.safe_message, "code": error.code},
        status=(
            status.HTTP_409_CONFLICT
            if error.code in conflict_codes
            else status.HTTP_400_BAD_REQUEST
        ),
    )


def storage_error_response(error: ImageStorageError) -> Response:
    return Response(
        {"detail": error.safe_message, "code": error.code},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class ImageGenerationBatchListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    throttle_scope = "admin"

    def get(self, request):
        queryset = image_generation_queryset()
        if request.query_params.get("status") == "active":
            queryset = queryset.exclude(
                status__in={
                    ImageGenerationBatch.Status.COMPLETED,
                    ImageGenerationBatch.Status.CANCELLED,
                }
            )
        return Response(ImageGenerationBatchSerializer(queryset[:25], many=True).data)

    def post(self, request):
        if not IsAdminOwner().has_permission(request, self):
            return Response(
                {"detail": IsAdminOwner.message},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ImageGenerationBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = create_batch(
                product_ids=serializer.validated_data["productIds"],
                requested_by=request.user,
            )
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        batch = image_generation_queryset().get(pk=batch.pk)
        return Response(ImageGenerationBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class ImageGenerationBatchDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = ImageGenerationBatchSerializer
    throttle_scope = "admin"
    lookup_url_kwarg = "batch_id"

    def get_queryset(self):
        return image_generation_queryset()


class ProductImageGenerationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminStaff]
    serializer_class = ProductImageGenerationSerializer
    throttle_scope = "admin"

    def get_queryset(self):
        return ProductImageGeneration.objects.filter(
            product_id=self.kwargs["pk"]
        ).select_related("product").prefetch_related("candidates")


class CandidateApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def post(self, request, candidate_id):
        try:
            candidate = approve_candidate(candidate_id=candidate_id, reviewer=request.user)
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        return Response(ProductImageCandidateSerializer(candidate).data)


class CandidateRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def post(self, request, candidate_id):
        try:
            candidate = reject_candidate(candidate_id=candidate_id, reviewer=request.user)
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        except ImageStorageError as error:
            return storage_error_response(error)
        return Response(ProductImageCandidateSerializer(candidate).data)


class CandidateRegenerateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def post(self, request, candidate_id):
        candidate = get_object_or_404(
            ProductImageCandidate.objects.select_related("generation").prefetch_related(
                "generation__candidates"
            ),
            pk=candidate_id,
        )
        serializer = CandidateRegenerationSerializer(
            data=request.data,
            context={"candidate": candidate},
        )
        serializer.is_valid(raise_exception=True)
        try:
            candidate = regenerate_candidate(
                candidate_id=candidate_id,
                scope=serializer.validated_data["scope"],
                shots=serializer.validated_data["shots"],
            )
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        except ImageStorageError as error:
            return storage_error_response(error)
        return Response(ProductImageCandidateSerializer(candidate).data)


class GenerationPublishView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def post(self, request, generation_id):
        serializer = ImageGenerationPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            generation = publish_generation(
                generation_id=generation_id,
                publication_mode=serializer.validated_data["publicationMode"],
            )
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        except ImageStorageError as error:
            return storage_error_response(error)
        generation = ProductImageGeneration.objects.select_related("product").prefetch_related("candidates").get(pk=generation.pk)
        return Response(ProductImageGenerationSerializer(generation).data)


class GenerationRestorePreviousView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOwner]
    throttle_scope = "admin"

    def post(self, request, generation_id):
        try:
            generation = restore_previous_gallery(generation_id=generation_id)
        except ImageGenerationWorkflowError as error:
            return workflow_error_response(error)
        generation = ProductImageGeneration.objects.select_related("product").prefetch_related("candidates").get(pk=generation.pk)
        return Response(ProductImageGenerationSerializer(generation).data)
