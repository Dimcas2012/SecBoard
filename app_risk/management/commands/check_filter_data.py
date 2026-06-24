from django.core.management.base import BaseCommand
from app_asset.models import AssetGroup, AssetType


class Command(BaseCommand):
    help = 'Check if asset groups and asset types exist in the database'

    def handle(self, *args, **options):
        self.stdout.write('Checking database for asset groups and asset types...')
        
        # Check asset groups
        asset_groups = AssetGroup.objects.all()
        self.stdout.write(f'Found {asset_groups.count()} asset groups:')
        for group in asset_groups:
            self.stdout.write(f'  - {group.name_uk} (ID: {group.id})')
        
        # Check asset types
        asset_types = AssetType.objects.all()
        self.stdout.write(f'\nFound {asset_types.count()} asset types:')
        for asset_type in asset_types:
            self.stdout.write(f'  - {asset_type.name_uk} (ID: {asset_type.id}, Group: {asset_type.group.name_uk})')
        
        if asset_groups.count() == 0:
            self.stdout.write(self.style.WARNING('No asset groups found in database!'))
        
        if asset_types.count() == 0:
            self.stdout.write(self.style.WARNING('No asset types found in database!'))
        
        if asset_groups.count() > 0 and asset_types.count() > 0:
            self.stdout.write(self.style.SUCCESS('Database contains asset groups and asset types. Filters should work correctly.'))
