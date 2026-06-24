from django.core.management.base import BaseCommand
from django.utils.translation import get_language
from app_asset.models import InformationAsset, CriticalityLevel
from app_risk.models import Vulnerability, Threat, RiskLevel
from app_risk.risk_assessment_views import calculate_value_of_risk, calculate_risk_level
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Debug risk calculation by testing with sample data'

    def handle(self, *args, **options):
        self.stdout.write("Starting risk calculation debug...")
        
        # Set up logging to see debug messages
        logging.basicConfig(level=logging.DEBUG)
        
        try:
            # Get some sample assets and vulnerabilities
            assets = InformationAsset.objects.all()[:5]
            vulnerabilities = Vulnerability.objects.all()[:5]
            
            self.stdout.write(f"Found {assets.count()} assets and {vulnerabilities.count()} vulnerabilities")
            
            for asset in assets:
                self.stdout.write(f"\n--- Asset: {asset.name} (ID: {asset.id}) ---")
                criticality = asset.get_criticality()
                self.stdout.write(f"Criticality: {criticality}")
                
                for vuln in vulnerabilities:
                    self.stdout.write(f"\n  Vulnerability: {vuln.get_name()[:50]}... (ID: {vuln.id})")
                    
                    # Check if asset and vulnerability are compatible
                    if asset.asset_type and vuln.asset_type and asset.asset_type != vuln.asset_type:
                        self.stdout.write(f"    Skipping - asset type mismatch")
                        continue
                    
                    # Get threats for this vulnerability
                    threats = vuln.threats.all()
                    self.stdout.write(f"    Threats count: {threats.count()}")
                    
                    if threats.exists():
                        try:
                            risk_value = calculate_value_of_risk(asset, vuln)
                            self.stdout.write(f"    Calculated risk value: {risk_value}")
                            
                            risk_level = calculate_risk_level(risk_value)
                            if risk_level:
                                current_language = get_language()[:2]
                                risk_level_name = risk_level.get_name_by_language(current_language) or risk_level.get_name()
                                self.stdout.write(f"    Risk level: {risk_level_name} (min: {risk_level.min_value}, max: {risk_level.max_value})")
                            else:
                                self.stdout.write(f"    Risk level: None/Unknown")
                        except Exception as e:
                            self.stdout.write(f"    Error calculating risk: {str(e)}")
                    else:
                        self.stdout.write(f"    No threats found for this vulnerability")
            
            # Also check RiskLevel data
            self.stdout.write(f"\n--- RiskLevel Data ---")
            risk_levels = RiskLevel.objects.filter(is_active=True).order_by('min_value')
            for level in risk_levels:
                self.stdout.write(f"Level: {level.get_name()} (min: {level.min_value}, max: {level.max_value})")
            
        except Exception as e:
            self.stdout.write(f"Error during debug: {str(e)}")
            import traceback
            self.stdout.write(traceback.format_exc())
