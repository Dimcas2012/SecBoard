#  SecBoard\SecBoard\app_asset\urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.i18n import JavaScriptCatalog

from . import views
from django.contrib.auth.decorators import user_passes_test


# app_name = 'app_asset'


urlpatterns = [


    path('information_assets/', views.information_assets, name='information_assets'),
    # Software register: more specific paths first (before software_register/)
    path('software_register/get/<int:pk>/', views.get_software_register_entry, name='get_software_register_entry'),
    path('software_register/history/<int:pk>/', views.get_software_register_history, name='get_software_register_history'),
    path('software_register/add/', views.add_software_register, name='add_software_register'),
    path('software_register/edit/', views.edit_software_register, name='edit_software_register'),
    path('software_register/delete/<int:pk>/', views.delete_software_register, name='delete_software_register'),
    path('software_register/duplicate/<int:pk>/', views.duplicate_software_register, name='duplicate_software_register'),
    path('software_register/upload/<int:pk>/', views.upload_software_register_files, name='upload_software_register_files'),
    path('software_register/file/delete/<int:file_pk>/', views.delete_software_register_file, name='delete_software_register_file'),
    path('software_register/actualize/<int:entry_id>/', views.actualize_software_register, name='actualize_software_register'),
    path('software_register/bulk_actualize/', views.bulk_actualize_software_register, name='bulk_actualize_software_register'),
    path('software_register/export/', views.export_software_register, name='export_software_register'),
    path('software_register/import/', views.import_software_register, name='import_software_register'),
    path('software_register/import/template/', views.download_software_register_import_template, name='download_software_register_import_template'),
    path('software_register/guide/', views.software_guide, name='software_guide'),
    path('software_register/api/guide/translate/', views.software_guide_translate, name='software_guide_translate'),
    path('software_register/', views.software_register, name='software_register'),
    # External Media Register
    path('external_media_register/get/<int:pk>/', views.get_external_media_register_entry, name='get_external_media_register_entry'),
    path('external_media_register/history/<int:pk>/', views.get_external_media_register_history, name='get_external_media_register_history'),
    path('external_media_register/add/', views.add_external_media_register, name='add_external_media_register'),
    path('external_media_register/edit/', views.edit_external_media_register, name='edit_external_media_register'),
    path('external_media_register/delete/<int:pk>/', views.delete_external_media_register, name='delete_external_media_register'),
    path('external_media_register/duplicate/<int:pk>/', views.duplicate_external_media_register, name='duplicate_external_media_register'),
    path('external_media_register/upload/<int:pk>/', views.upload_external_media_register_files, name='upload_external_media_register_files'),
    path('external_media_register/file/delete/<int:file_pk>/', views.delete_external_media_register_file, name='delete_external_media_register_file'),
    path('external_media_register/import/', views.import_external_media_register, name='import_external_media_register'),
    path('external_media_register/import/template/', views.download_external_media_register_import_template, name='download_external_media_register_import_template'),
    path('external_media_register/actualize/<int:entry_id>/', views.actualize_external_media_register, name='actualize_external_media_register'),
    path('external_media_register/export/', views.export_external_media_register, name='export_external_media_register'),
    path('external_media_register/guide/', views.external_media_guide, name='external_media_guide'),
    path('external_media_register/api/guide/translate/', views.external_media_guide_translate, name='external_media_guide_translate'),
    path('external_media_register/', views.external_media_register, name='external_media_register'),
    path('asset_data/', views.AssetDatatableView.as_view(), name='asset_data'),
    path('add_asset/', views.add_asset, name='add_asset'),
    path('edit_asset/<int:asset_id>/', views.edit_asset, name='edit_asset'),
    path('delete_asset/<int:asset_id>/', views.delete_asset, name='delete_asset'),
    path('get_asset/<int:asset_id>/', views.get_asset, name='get_asset'),
    path('get_asset_details/<int:asset_id>/', views.get_asset_details, name='get_asset_details'),
    path('get_asset_history/<int:asset_id>/', views.get_asset_history, name='get_asset_history'),
    path('actualize_asset/<int:asset_id>/', views.actualize_asset, name='actualize_asset'),
    path('bulk_actualize_assets/', views.bulk_actualize_assets, name='bulk_actualize_assets'),
    path('export/excel/', views.export_assets_to_excel, name='export_assets_to_excel'),
    path('guide/', views.asset_guide, name='asset_guide'),
    path('api/guide/translate/', views.asset_guide_translate, name='asset_guide_translate'),
    path('search-cabinet-users/', views.search_cabinet_users, name='search_cabinet_users'),
    path('get_asset_types_by_group/', views.get_asset_types_by_group, name='get_asset_types_by_group'),


    path('get_criticality_levels/', views.get_criticality_levels, name='get_criticality_levels'),
    path('get_company_people/', views.get_company_people, name='get_company_people'),
    path('check_asset_permissions/', views.check_asset_permissions, name='check_asset_permissions'),
    path('get_asset_types/', views.get_asset_types, name='get_asset_types'),
    path('get_asset_type/', views.get_asset_type, name='get_asset_type'),
    path('add_asset_type/', views.add_asset_type, name='add_asset_type'),
    path('edit_asset_type/', views.edit_asset_type, name='edit_asset_type'),
    path('delete_asset_type/', views.delete_asset_type, name='delete_asset_type'),

    # Asset Group management URLs
    path('get_all_asset_groups/', views.get_all_asset_groups, name='get_all_asset_groups'),
    path('get_asset_group/', views.get_asset_group, name='get_asset_group'),
    path('add_asset_group/', views.add_asset_group, name='add_asset_group'),
    path('edit_asset_group/', views.edit_asset_group, name='edit_asset_group'),
    path('delete_asset_group/', views.delete_asset_group, name='delete_asset_group'),

    # New paths for owners
    path('get_asset_owners/<int:asset_id>/', views.get_asset_owners, name='get_asset_owners'),
    path('add_asset_owner/', views.add_asset_owner, name='add_asset_owner'),
    path('api/asset/owners/get-or-create/', views.get_or_create_asset_owner, name='get_or_create_asset_owner'),

    path('edit_asset_owner/', views.edit_asset_owner, name='edit_asset_owner'),
    # path('api/asset/owners/<int:owner_id>/edit/', views.edit_asset_owner, name='edit_asset_owner'),
    path('remove_asset_owner/<int:asset_id>/<int:owner_id>/', views.remove_asset_owner, name='remove_asset_owner'),
    path('get_owner/<int:owner_id>/', views.get_owner, name='get_owner'),
    path('delete-asset-owners/', views.delete_asset_owners, name='delete_asset_owners'),
    # path('get_all_asset_owners/', views.get_all_asset_owners, name='get_all_asset_owners'),
    path('api/asset/owners/all/', views.get_all_asset_owners, name='get_all_asset_owners'),

    # New paths for administrators
    path('get_asset_administrators/<int:asset_id>/', views.get_asset_administrators, name='get_asset_administrators'),
    path('add_asset_administrator/', views.add_asset_administrator, name='add_asset_administrator'),

    path('edit_asset_administrator/', views.edit_asset_administrator, name='edit_asset_administrator'),
    # path('api/asset/administrators/<int:admin_id>/edit/', views.edit_asset_administrator, name='edit_asset_administrator'),
    path('remove_asset_administrator/<int:asset_id>/<int:admin_id>/', views.remove_asset_administrator, name='remove_asset_administrator'),
    path('get_administrator/<int:admin_id>/', views.get_administrator, name='get_administrator'),
    path('get_all_administrators/', views.get_all_administrators, name='get_all_administrators'),
    path('delete_asset_owners/', views.delete_asset_owners, name='delete_asset_owners'),
    path('delete_asset_administrators/', views.delete_asset_administrators, name='delete_asset_administrators'),
    path('api/asset/administrators/all/', views.get_all_asset_administrators, name='get_all_asset_administrators'),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)