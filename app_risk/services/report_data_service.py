# SecBoard/app_risk/services/report_data_service.py

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from django.db.models import Count, Q, Sum, Avg, Max, Min, F, Case, When, IntegerField
from django.utils import timezone
from django.utils.translation import gettext as _, get_language
from django.core.cache import cache
from django.contrib.auth.models import User

from ..models import (
    InformationAsset, AssetVulnerability, Vulnerability, Threat, 
    RiskLevel, RiskTreatment, AccessRisk
)
from .report_config import ReportConfig

logger = logging.getLogger(__name__)


class ReportDataService:
    """Service for optimized data retrieval for reports"""
    
    def __init__(self, user: User, config: ReportConfig):
        self.user = user
        self.config = config
        self.cache_timeout = 300  # 5 minutes
        
    def get_comprehensive_report_data(self) -> Dict[str, Any]:
        """Get all data needed for report generation with optimized queries"""
        cache_key = f"report_data_{self.user.id}_{self.config.hash}"
        
        # Try to get from cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Report data retrieved from cache for user {self.user.username}")
            return cached_data
        
        logger.info(f"Generating fresh report data for user {self.user.username}")
        
        # Get user's accessible companies
        user_companies = self._get_user_companies()
        
        # Build company filter
        company_filter = self._build_company_filter(user_companies)
        
        # Get optimized asset data
        assets_data = self._get_optimized_assets_data(company_filter)
        
        # Get statistics
        statistics = self._calculate_comprehensive_statistics(assets_data['assets'])
        
        # Get compliance data
        compliance_data = self._get_compliance_data(assets_data['asset_vulnerabilities'])
        
        # Get risk treatments data
        risk_treatments_data = self._get_risk_treatments_data(assets_data['assets'])
        
        # Compile comprehensive data
        report_data = {
            'generation_date': timezone.now(),
            'generated_by': self.user.get_full_name() or self.user.username,
            'user': self.user,
            'config': self.config,
            'date_range': {
                'start': self.config.start_date,
                'end': self.config.end_date
            },
            'companies': user_companies,
            'assets': assets_data['assets'],
            'asset_vulnerabilities': assets_data['asset_vulnerabilities'],
            'vulnerabilities': assets_data['vulnerabilities'],
            'risk_treatments': risk_treatments_data,
            'statistics': statistics,
            'compliance': compliance_data,
            'language': self.config.language,
            'translations': self._get_report_translations()
        }
        
        # Cache the result
        cache.set(cache_key, report_data, timeout=self.cache_timeout)
        logger.info(f"Report data cached for user {self.user.username}")
        
        return report_data
    
    def _get_user_companies(self):
        """Get user's accessible companies"""
        # This should be implemented based on your user-company relationship
        # For now, assuming all companies are accessible
        from ..models import Company
        return Company.objects.all()
    
    def _build_company_filter(self, user_companies) -> Q:
        """Build Q object for company filtering"""
        if self.config.company_id:
            return Q(company_id=self.config.company_id)
        elif user_companies:
            return Q(company__in=user_companies)
        else:
            return Q()
    
    def _get_optimized_assets_data(self, company_filter: Q) -> Dict[str, Any]:
        """Get assets data with optimized queries"""
        # Base asset query with all necessary joins
        assets_query = (
            InformationAsset.objects
            .filter(company_filter)
            .select_related('company', 'group', 'criticality')
            .prefetch_related(
                'assetvulnerability_set__vulnerability',
                'assetvulnerability_set__modified_by',
                'risktreatment_set__treatment_type',
                'risktreatment_set__status'
            )
        )
        
        # Apply date filters
        if self.config.start_date and self.config.end_date:
            assets_query = assets_query.filter(
                Q(registration_date__range=[self.config.start_date, self.config.end_date]) |
                Q(assetvulnerability__modified_at__date__range=[self.config.start_date, self.config.end_date]) |
                Q(risktreatment__last_modified__date__range=[self.config.start_date, self.config.end_date])
            ).distinct()
        
        # Handle deleted assets
        if not self.config.include_deleted:
            assets_query = assets_query.filter(deletion_date__isnull=True)
        
        # Add annotations for statistics
        assets_query = assets_query.annotate(
            vulnerability_count=Count('assetvulnerability', distinct=True),
            high_risk_count=Count(
                'assetvulnerability',
                filter=Q(assetvulnerability__status='Yes'),
                distinct=True
            ),
            treatment_count=Count('risktreatment', distinct=True),
            completed_treatments=Count(
                'risktreatment',
                filter=Q(risktreatment__status__name='Completed'),
                distinct=True
            )
        )
        
        assets = list(assets_query)
        
        # Get related vulnerabilities and asset vulnerabilities
        asset_vulnerabilities = AssetVulnerability.objects.filter(
            asset__in=assets,
            modified_at__date__range=[self.config.start_date, self.config.end_date]
        ).select_related('asset', 'vulnerability', 'modified_by')
        
        vulnerabilities = Vulnerability.objects.filter(
            assetvulnerability__in=asset_vulnerabilities
        ).distinct()
        
        return {
            'assets': assets,
            'asset_vulnerabilities': asset_vulnerabilities,
            'vulnerabilities': vulnerabilities
        }
    
    def _calculate_comprehensive_statistics(self, assets) -> Dict[str, Any]:
        """Calculate comprehensive statistics from assets data"""
        total_assets = len(assets)
        
        # Calculate vulnerability statistics
        vulnerability_stats = self._calculate_vulnerability_statistics(assets)
        
        # Calculate risk level distribution
        risk_levels = self._calculate_risk_levels(assets)
        
        # Calculate criticality distribution
        criticality_stats = self._calculate_criticality_distribution(assets)
        
        # Calculate treatment statistics
        treatment_stats = self._calculate_treatment_statistics(assets)
        
        # Calculate completion rate
        completion_rate = self._calculate_completion_rate(assets)
        
        # Get high risk assets
        high_risk_assets = self._get_high_risk_assets(assets)
        
        return {
            'total_assets': total_assets,
            'vulnerability_statistics': vulnerability_stats,
            'risk_levels': risk_levels,
            'criticality_distribution': criticality_stats,
            'treatment_statistics': treatment_stats,
            'completion_rate': completion_rate,
            'high_risk_assets': high_risk_assets,
            'high_risk_count': len(high_risk_assets),
            'generation_timestamp': timezone.now()
        }
    
    def _calculate_vulnerability_statistics(self, assets) -> Dict[str, Any]:
        """Calculate vulnerability-related statistics"""
        total_vulnerabilities = sum(asset.vulnerability_count for asset in assets)
        
        # Status breakdown
        status_breakdown = {}
        for asset in assets:
            for av in asset.assetvulnerability_set.all():
                status = av.status or 'Undefined'
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        return {
            'total_vulnerabilities': total_vulnerabilities,
            'status_breakdown': status_breakdown,
            'average_per_asset': total_vulnerabilities / len(assets) if assets else 0
        }
    
    def _calculate_risk_levels(self, assets) -> Dict[str, int]:
        """Calculate risk level distribution"""
        risk_levels = {}
        
        for asset in assets:
            # This is a simplified calculation - you might want to implement
            # more sophisticated risk calculation based on your business logic
            high_risk_vulns = asset.high_risk_count
            total_vulns = asset.vulnerability_count
            
            if total_vulns == 0:
                level = 'No Risk'
            elif high_risk_vulns > total_vulns * 0.7:
                level = 'High'
            elif high_risk_vulns > total_vulns * 0.3:
                level = 'Medium'
            else:
                level = 'Low'
            
            risk_levels[level] = risk_levels.get(level, 0) + 1
        
        return risk_levels
    
    def _calculate_criticality_distribution(self, assets) -> List[Dict[str, Any]]:
        """Calculate asset criticality distribution"""
        criticality_counts = {}
        
        for asset in assets:
            criticality_name = asset.criticality.name_uk if asset.criticality else 'Unknown'
            criticality_counts[criticality_name] = criticality_counts.get(criticality_name, 0) + 1
        
        return [
            {'criticality__name_uk': name, 'count': count}
            for name, count in criticality_counts.items()
        ]
    
    def _calculate_treatment_statistics(self, assets) -> Dict[str, Any]:
        """Calculate treatment-related statistics"""
        total_treatments = sum(asset.treatment_count for asset in assets)
        completed_treatments = sum(asset.completed_treatments for asset in assets)
        
        return {
            'total_treatments': total_treatments,
            'completed_treatments': completed_treatments,
            'completion_percentage': (completed_treatments / total_treatments * 100) if total_treatments > 0 else 0
        }
    
    def _calculate_completion_rate(self, assets) -> float:
        """Calculate overall completion rate"""
        total_items = 0
        completed_items = 0
        
        for asset in assets:
            total_items += asset.vulnerability_count + asset.treatment_count
            completed_items += asset.completed_treatments
            
            # Count 'No' status vulnerabilities as completed
            for av in asset.assetvulnerability_set.all():
                if av.status == 'No':
                    completed_items += 1
        
        return (completed_items / total_items * 100) if total_items > 0 else 0
    
    def _get_high_risk_assets(self, assets) -> List[Dict[str, Any]]:
        """Get list of high-risk assets"""
        high_risk_assets = []
        
        for asset in assets:
            if asset.high_risk_count > 0:
                high_risk_assets.append({
                    'id': asset.id,
                    'name': asset.name,
                    'company': asset.company.name if asset.company else 'Unknown',
                    'vulnerability_count': asset.vulnerability_count,
                    'high_risk_count': asset.high_risk_count,
                    'criticality': asset.criticality.name_uk if asset.criticality else 'Unknown'
                })
        
        # Sort by high risk count descending
        high_risk_assets.sort(key=lambda x: x['high_risk_count'], reverse=True)
        
        return high_risk_assets
    
    def _get_compliance_data(self, asset_vulnerabilities) -> Dict[str, Any]:
        """Get compliance data for PCI DSS, ISO 27001, and compliance requirements"""
        pcidss_data = self._calculate_pcidss_compliance(asset_vulnerabilities)
        iso27001_data = self._calculate_iso27001_compliance(asset_vulnerabilities)
        
        # Get compliance requirements data if sections are enabled
        framework_company_requirements = None
        company_requirements = None
        internal_requirements = None
        
        # Check sections_config if available, otherwise check sections
        sections_config = getattr(self.config, 'sections_config', {}) or {}
        if not sections_config:
            sections_config = getattr(self.config, 'sections', {}) or {}
        
        if sections_config.get('framework_company_requirements', False):
            framework_company_requirements = self._get_framework_company_requirements()
        
        if sections_config.get('company_requirements', False):
            company_requirements = self._get_local_company_requirements()
        
        if sections_config.get('internal_requirements', False):
            internal_requirements = self._get_internal_company_requirements()
        
        return {
            'pcidss': pcidss_data,
            'iso27001': iso27001_data,
            'framework_company_requirements': framework_company_requirements,
            'company_requirements': company_requirements,
            'internal_requirements': internal_requirements
        }
    
    def _calculate_pcidss_compliance(self, asset_vulnerabilities) -> Dict[str, Any]:
        """Calculate PCI DSS compliance metrics"""
        total_requirements = 0
        compliant_requirements = 0
        gaps = []
        
        for av in asset_vulnerabilities:
            if av.vulnerability.pci_dss_requirement:
                total_requirements += 1
                if av.status == 'No':  # Vulnerability is not present = compliant
                    compliant_requirements += 1
                elif av.status == 'Yes':  # Vulnerability is present = gap
                    gaps.append({
                        'asset': av.asset.name,
                        'vulnerability': av.vulnerability.vulnerability,
                        'requirement': av.vulnerability.pci_dss_requirement,
                        'status': av.status
                    })
        
        compliance_rate = (compliant_requirements / total_requirements * 100) if total_requirements > 0 else 0
        
        return {
            'total_requirements': total_requirements,
            'compliant_vulnerabilities': compliant_requirements,
            'overall_compliance': compliance_rate,
            'gaps': gaps
        }
    
    def _calculate_iso27001_compliance(self, asset_vulnerabilities) -> Dict[str, Any]:
        """Calculate ISO 27001 compliance metrics"""
        total_controls = 0
        compliant_controls = 0
        gaps = []
        
        for av in asset_vulnerabilities:
            if av.vulnerability.iso27001_requirement:
                total_controls += 1
                if av.status == 'No':  # Vulnerability is not present = compliant
                    compliant_controls += 1
                elif av.status == 'Yes':  # Vulnerability is present = gap
                    gaps.append({
                        'asset': av.asset.name,
                        'vulnerability': av.vulnerability.vulnerability,
                        'control': av.vulnerability.iso27001_requirement,
                        'status': av.status
                    })
        
        compliance_rate = (compliant_controls / total_controls * 100) if total_controls > 0 else 0
        
        return {
            'total_controls': total_controls,
            'compliant_vulnerabilities': compliant_controls,
            'overall_compliance': compliance_rate,
            'gaps': gaps
        }
    
    def _get_framework_company_requirements(self) -> Dict[str, Any]:
        """Get Framework Company Requirements data from app_compliance"""
        try:
            from app_compliance.models import ComplianceFramework
            from django.db.models import Count, Q
            
            # Get company filter
            user_companies = self._get_user_companies()
            company_filter = self._build_company_filter(user_companies)
            
            # Get framework instances (not templates) for the company
            company_ids = list(user_companies.values_list('id', flat=True)) if hasattr(user_companies, 'values_list') else []
            if self.config.company_id:
                company_ids = [self.config.company_id]
            
            frameworks = ComplianceFramework.objects.filter(
                is_template=False,
                company_id__in=company_ids if company_ids else []
            ).select_related('company', 'template').annotate(
                controls_total=Count('controls', distinct=True),
                controls_completed=Count('controls', filter=Q(controls__status='completed'), distinct=True),
                controls_in_progress=Count('controls', filter=Q(controls__status='in_progress'), distinct=True),
                controls_not_started=Count('controls', filter=Q(controls__status='not_started'), distinct=True)
            )
            
            frameworks_list = []
            for framework in frameworks:
                total = framework.controls_total or 0
                completed = framework.controls_completed or 0
                completion = round((completed / total * 100), 1) if total > 0 else 0
                
                frameworks_list.append({
                    'id': framework.id,
                    'name': framework.name,
                    'framework_type': framework.get_framework_type_display(),
                    'version': framework.version,
                    'company': framework.company.name if framework.company else None,
                    'is_mandatory': framework.is_mandatory,
                    'status': framework.get_status_display(),
                    'controls_total': total,
                    'controls_completed': completed,
                    'controls_in_progress': framework.controls_in_progress or 0,
                    'controls_not_started': framework.controls_not_started or 0,
                    'completion_percentage': completion
                })
            
            return {
                'total_frameworks': len(frameworks_list),
                'frameworks': frameworks_list,
                'overall_completion': round(sum(f['completion_percentage'] for f in frameworks_list) / len(frameworks_list), 1) if frameworks_list else 0
            }
        except ImportError:
            logger.warning("app_compliance module not available")
            return None
        except Exception as e:
            logger.error(f"Error getting framework company requirements: {str(e)}")
            return None
    
    def _get_local_company_requirements(self) -> Dict[str, Any]:
        """Get Local Company Requirements data from app_compliance"""
        try:
            from app_compliance.models import LocalComplianceRequirement
            from django.db.models import Count, Q
            
            # Get company filter
            user_companies = self._get_user_companies()
            company_ids = list(user_companies.values_list('id', flat=True)) if hasattr(user_companies, 'values_list') else []
            if self.config.company_id:
                company_ids = [self.config.company_id]
            
            # Get local requirement instances (not templates) for the company
            requirements = LocalComplianceRequirement.objects.filter(
                is_template=False,
                company_id__in=company_ids if company_ids else []
            ).select_related('company', 'template', 'regulator').annotate(
                controls_total=Count('controls', distinct=True),
                controls_completed=Count('controls', filter=Q(controls__status='completed'), distinct=True),
                controls_in_progress=Count('controls', filter=Q(controls__status='in_progress'), distinct=True),
                controls_not_started=Count('controls', filter=Q(controls__status='not_started'), distinct=True)
            )
            
            requirements_list = []
            for req in requirements:
                total = req.controls_total or 0
                completed = req.controls_completed or 0
                completion = round((completed / total * 100), 1) if total > 0 else 0
                
                requirements_list.append({
                    'id': req.id,
                    'code': req.code,
                    'name': req.name,
                    'requirement_type': req.get_requirement_type_display(),
                    'company': req.company.name if req.company else None,
                    'regulator': req.regulator.name if req.regulator else None,
                    'is_mandatory': req.is_mandatory,
                    'status': req.get_status_display(),
                    'effective_date': req.effective_date.isoformat() if req.effective_date else None,
                    'deadline_date': req.deadline_date.isoformat() if req.deadline_date else None,
                    'controls_total': total,
                    'controls_completed': completed,
                    'controls_in_progress': req.controls_in_progress or 0,
                    'controls_not_started': req.controls_not_started or 0,
                    'completion_percentage': completion
                })
            
            return {
                'total_requirements': len(requirements_list),
                'requirements': requirements_list,
                'overall_completion': round(sum(r['completion_percentage'] for r in requirements_list) / len(requirements_list), 1) if requirements_list else 0
            }
        except ImportError:
            logger.warning("app_compliance module not available")
            return None
        except Exception as e:
            logger.error(f"Error getting local company requirements: {str(e)}")
            return None
    
    def _get_internal_company_requirements(self) -> Dict[str, Any]:
        """Get Internal Company Requirements data from app_compliance"""
        try:
            from app_compliance.models import InternalComplianceRequirement
            from django.db.models import Count, Q
            
            # Get company filter
            user_companies = self._get_user_companies()
            company_ids = list(user_companies.values_list('id', flat=True)) if hasattr(user_companies, 'values_list') else []
            if self.config.company_id:
                company_ids = [self.config.company_id]
            
            # Get internal requirements for the company (can be templates or instances)
            requirements = InternalComplianceRequirement.objects.filter(
                company_id__in=company_ids if company_ids else []
            ).select_related('company', 'source').annotate(
                controls_count=Count('controls', distinct=True)
            )
            
            requirements_list = []
            for req in requirements:
                requirements_list.append({
                    'id': req.id,
                    'code': req.code,
                    'name': req.name,
                    'requirement_type': req.get_requirement_type_display(),
                    'company': req.company.name if req.company else None,
                    'source': req.source.name if req.source else None,
                    'is_mandatory': req.is_mandatory,
                    'status': req.get_status_display(),
                    'effective_date': req.effective_date.isoformat() if req.effective_date else None,
                    'deadline_date': req.deadline_date.isoformat() if req.deadline_date else None,
                    'controls_count': req.controls_count or 0
                })
            
            return {
                'total_requirements': len(requirements_list),
                'requirements': requirements_list
            }
        except ImportError:
            logger.warning("app_compliance module not available")
            return None
        except Exception as e:
            logger.error(f"Error getting internal company requirements: {str(e)}")
            return None
    
    def _get_risk_treatments_data(self, assets) -> List[Dict[str, Any]]:
        """Get risk treatments data"""
        treatments = []
        
        for asset in assets:
            for treatment in asset.risktreatment_set.all():
                treatments.append({
                    'id': treatment.id,
                    'asset': asset.name,
                    'vulnerability': treatment.vulnerability.vulnerability if treatment.vulnerability else 'General',
                    'treatment_type': treatment.treatment_type.name if treatment.treatment_type else 'Unknown',
                    'status': treatment.status.name if treatment.status else 'Unknown',
                    'last_modified': treatment.last_modified,
                    'completion_percentage': getattr(treatment, 'completion_percentage', 0)
                })
        
        return treatments
    
    def _get_report_translations(self) -> Dict[str, str]:
        """Get translations for the current language"""
        # This would typically come from a translation service
        # For now, returning basic translations
        return {
            'total_assets': _('Total Assets'),
            'total_vulnerabilities': _('Total Vulnerabilities'),
            'completion_rate': _('Completion Rate'),
            'high_risk_count': _('High Risk Count'),
            'risk_level': _('Risk Level'),
            'count': _('Count'),
            'percentage': _('Percentage'),
            'criticality': _('Criticality'),
            'compliance_summary': _('Compliance Summary'),
            'pci_dss_compliance': _('PCI DSS Compliance'),
            'iso27001_compliance': _('ISO 27001 Compliance'),
            'overall_compliance': _('Overall Compliance'),
            'gaps': _('Gaps'),
            'executive_summary': _('Executive Summary'),
            'risk_distribution': _('Risk Distribution'),
            'by_risk_level': _('By Risk Level'),
            'by_criticality': _('By Criticality'),
            'vulnerability_analysis': _('Vulnerability Analysis'),
            'treatment_status': _('Treatment Status'),
            'recommendations': _('Recommendations')
        }
    
    def get_quick_statistics(self) -> Dict[str, Any]:
        """Get quick statistics for dashboard display"""
        cache_key = f"quick_stats_{self.user.id}_{self.config.company_id or 'all'}"
        
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        # Get user companies
        user_companies = self._get_user_companies()
        company_filter = self._build_company_filter(user_companies)
        
        # Quick aggregated queries
        assets_count = InformationAsset.objects.filter(
            company_filter,
            deletion_date__isnull=True
        ).count()
        
        vulnerabilities_count = AssetVulnerability.objects.filter(
            asset__in=InformationAsset.objects.filter(company_filter),
            status='Yes'
        ).count()
        
        high_risk_count = AssetVulnerability.objects.filter(
            asset__in=InformationAsset.objects.filter(company_filter),
            status='Yes',
            vulnerability__risk_level='High'
        ).count()
        
        stats = {
            'total_assets': assets_count,
            'total_vulnerabilities': vulnerabilities_count,
            'high_risk_count': high_risk_count,
            'last_updated': timezone.now()
        }
        
        cache.set(cache_key, stats, timeout=60)  # Cache for 1 minute
        return stats 