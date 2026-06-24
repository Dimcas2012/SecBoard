# #  SecBoard\SecBoard\app_suib\serializers.py
# import datetime
#
# import pytz
# from django.conf import settings
# from django.utils import timezone
# from django.utils.dateparse import parse_date
# from rest_framework import serializers
# from .models import InformationAsset, AssetGroup, AssetType, CriticalityLevel
# from app_conf.models import Company
# from django.utils.translation import get_language
#
#
#
# class CompanySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Company
#         fields = ['id', 'name']
#
# class LocalizedNameSerializer(serializers.Serializer):
#     uk = serializers.CharField(source='name_uk')
#     ru = serializers.CharField(source='name_ru')
#     en = serializers.CharField(source='name_en')
#
# class AssetGroupSerializer(serializers.ModelSerializer):
#     name = LocalizedNameSerializer(source='*')
#
#     class Meta:
#         model = AssetGroup
#         fields = ['id', 'name', 'abbreviation']
#
# class AssetTypeSerializer(serializers.ModelSerializer):
#     name = LocalizedNameSerializer(source='*')
#
#     class Meta:
#         model = AssetType
#         fields = ['id', 'name']
#
# class CriticalityLevelSerializer(serializers.ModelSerializer):
#     name = serializers.SerializerMethodField()
#
#     class Meta:
#         model = CriticalityLevel
#         fields = ['id', 'name', 'cost', 'color', 'critical_name_uk', 'critical_name_ru', 'critical_name_en']
#
#     def get_name(self, obj):
#         return obj.get_name()
#
#
#
#
# class InformationAssetSerializer(serializers.ModelSerializer):
#     company = CompanySerializer()
#     group = AssetGroupSerializer()
#     asset_type = AssetTypeSerializer()
#     last_modified = serializers.SerializerMethodField()
#     criticality = serializers.SerializerMethodField()
#     confidentiality = CriticalityLevelSerializer()
#     integrity = CriticalityLevelSerializer()
#     availability = CriticalityLevelSerializer()
#     vulnerabilities_count = serializers.IntegerField(read_only=True)
#     registration_date = serializers.DateField(format='%d.%m.%Y', input_formats=['%d.%m.%Y', '%Y-%m-%d'],
#                                               allow_null=True, required=False)
#     deletion_date = serializers.DateField(format='%d.%m.%Y', input_formats=['%d.%m.%Y', '%Y-%m-%d'],
#                                           allow_null=True, required=False)
#     last_modified = serializers.SerializerMethodField()
#     last_modified_by = serializers.SerializerMethodField()
#
#     class Meta:
#         model = InformationAsset
#         fields = ['id', 'asset_id', 'name', 'company', 'group', 'asset_type', 'description', 'location',
#                   'registration_date', 'deletion_date', 'notes', 'last_modified', 'last_modified_by', 'criticality',
#                   'confidentiality', 'integrity', 'availability', 'vulnerabilities_count']
#
#     def get_last_modified(self, obj):
#         if obj.last_modified:
#             kyiv_tz = pytz.timezone('Europe/Kiev')
#             if timezone.is_naive(obj.last_modified):
#                 obj.last_modified = timezone.make_aware(obj.last_modified, timezone.utc)
#             kyiv_time = obj.last_modified.astimezone(kyiv_tz)
#             return kyiv_time.strftime('%d.%m.%Y, %H:%M:%S')
#         return None
#
#     def to_internal_value(self, data):
#         def parse_date(date_string):
#             if date_string and date_string != 'NaN.NaN.NaN':
#                 try:
#                     return datetime.strptime(date_string, '%d.%m.%Y').date()
#                 except ValueError:
#                     raise serializers.ValidationError(f"Invalid date format: {date_string}")
#             return None
#
#         if 'registration_date' in data:
#             data['registration_date'] = parse_date(data['registration_date'])
#         if 'deletion_date' in data:
#             data['deletion_date'] = parse_date(data['deletion_date'])
#         return super().to_internal_value(data)
#
#     def to_representation(self, instance):
#         ret = super().to_representation(instance)
#         # Конвертуємо дати в формат 'DD.MM.YYYY' для відображення
#         if ret['registration_date']:
#             ret['registration_date'] = instance.registration_date.strftime('%d.%m.%Y')
#         if ret['deletion_date']:
#             ret['deletion_date'] = instance.deletion_date.strftime('%d.%m.%Y')
#         return ret
#     def get_criticality(self, obj):
#         return obj.get_criticality()
#
#     def get_last_modified_by(self, obj):
#         if obj.last_modified_by:
#             return obj.last_modified_by.get_full_name() or obj.last_modified_by.username
#         return ''