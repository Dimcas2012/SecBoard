from rest_framework import serializers

from app_cif.models import CIFObject, CIFPassport, CIFProtectionMeasure, CIFProtectionPlan


class CIFPassportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CIFPassport
        fields = [
            "id",
            "version",
            "status",
            "approval_date",
            "next_review_date",
            "general_info",
            "critical_functions",
            "resources",
            "dependencies",
            "threats",
        ]


class CIFProtectionMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = CIFProtectionMeasure
        fields = [
            "id",
            "class_code",
            "measure_number",
            "name",
            "description",
            "implementation_status",
            "deadline",
            "responsible_id",
            "related_compliance_control_id",
            "notes",
        ]


class CIFProtectionPlanSerializer(serializers.ModelSerializer):
    measures = CIFProtectionMeasureSerializer(many=True, read_only=True)
    implementation_percent = serializers.SerializerMethodField()

    class Meta:
        model = CIFProtectionPlan
        fields = [
            "id",
            "version",
            "status",
            "approval_date",
            "next_review_date",
            "implementation_percent",
            "id_percent",
            "pr_percent",
            "de_percent",
            "rs_percent",
            "rc_percent",
            "structure",
            "responsible_person_id",
            "measures",
        ]

    def get_implementation_percent(self, obj):
        obj.recalculate_progress(save=True)
        return obj.implementation_percent


class CIFObjectSerializer(serializers.ModelSerializer):
    passport = CIFPassportSerializer(read_only=True)
    protection_plan = CIFProtectionPlanSerializer(read_only=True)

    class Meta:
        model = CIFObject
        fields = [
            "id",
            "name",
            "edrpou",
            "category",
            "sector_id",
            "address",
            "company_id",
            "status",
            "responsible_person_id",
            "critical_functions_count",
            "is_passport_approved",
            "passport_approved_date",
            "created_at",
            "updated_at",
            "passport",
            "protection_plan",
        ]
