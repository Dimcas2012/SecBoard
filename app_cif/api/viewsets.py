from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_cif.api.serializers import CIFObjectSerializer, CIFPassportSerializer, CIFProtectionPlanSerializer
from app_cif.models import CIFObject, CIFPassport, CIFProtectionMeasure, CIFProtectionPlan


class CIFObjectListCreateAPIView(generics.ListCreateAPIView):
    queryset = CIFObject.objects.select_related("sector", "company").all()
    serializer_class = CIFObjectSerializer
    permission_classes = [IsAuthenticated]


class CIFObjectRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    queryset = CIFObject.objects.select_related("sector", "company").all()
    serializer_class = CIFObjectSerializer
    permission_classes = [IsAuthenticated]


class CIFObjectPassportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cif_object = get_object_or_404(CIFObject, pk=pk)
        passport, _ = CIFPassport.objects.get_or_create(cif_object=cif_object)
        return Response(CIFPassportSerializer(passport).data)

    def put(self, request, pk):
        cif_object = get_object_or_404(CIFObject, pk=pk)
        passport, _ = CIFPassport.objects.get_or_create(cif_object=cif_object)
        serializer = CIFPassportSerializer(passport, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CIFObjectProtectionPlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cif_object = get_object_or_404(CIFObject, pk=pk)
        plan, _ = CIFProtectionPlan.objects.get_or_create(cif_object=cif_object)
        return Response(CIFProtectionPlanSerializer(plan).data)

    def put(self, request, pk):
        cif_object = get_object_or_404(CIFObject, pk=pk)
        plan, _ = CIFProtectionPlan.objects.get_or_create(cif_object=cif_object)
        serializer = CIFProtectionPlanSerializer(plan, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CIFObjectGenerateReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        cif_object = get_object_or_404(CIFObject, pk=pk)
        return Response(
            {
                "status": "ok",
                "message": f"Report generated for CIF object {cif_object.pk}",
                "generated_at": timezone.now(),
            },
            status=status.HTTP_200_OK,
        )


class CIFDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "total_objects": CIFObject.objects.count(),
            "approved_passports": CIFObject.objects.filter(is_passport_approved=True).count(),
            "active_plans": CIFProtectionPlan.objects.filter(status="active").count(),
            "completed_measures": CIFProtectionMeasure.objects.filter(implementation_status="completed").count(),
            "overdue_measures": CIFProtectionMeasure.objects.filter(
                implementation_status__in=["not_started", "in_progress"],
                deadline__lt=timezone.now().date(),
            ).count(),
        }
        return Response(data)
