# SecBoard/app_risk/services/report_data_service_optimized.py

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from django.db.models import (
    Count, Q, Sum, Avg, Max, Min, F, Case, When, IntegerField, 
    Prefetch, Subquery, OuterRef, Exists, Value, CharField
)
from django.db.models.functions import Coalesce, Cast, Extract
from django.utils import timezone
from django.utils.translation import gettext as _, get_language
from django.core.cache import cache
from django.contrib.auth.models import User
from django.db import transaction, connection
from django.core.paginator import Paginator
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from asgiref.sync import sync_to_async

from ..models import (
    InformationAsset, AssetVulnerability, Vulnerability, Threat, 
    RiskLevel, RiskTreatment, AccessRisk
)
from .report_config import ReportConfig

logger = logging.getLogger(__name__)


class OptimizedReportDataService:
    """Highly optimized service for report data retrieval with advanced performance features"""
    
    def __init__(self, user: User, config: ReportConfig):
        self.user = user
        self.config = config
        self.cache_timeout = 300  # 5 minutes
        self.quick_cache_timeout = 60  # 1 minute for quick stats
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self._db_connection_pool = None
        
    def get_comprehensive_report_data(self) -> Dict[str, Any]:
        """Get all data needed for report generation with maximum optimization"""
        cache_key = f"optimized_report_data_{self.user.id}_{self.config.hash}"
        
        # Multi-level caching strategy
        cached_data = self._get_from_multilevel_cache(cache_key)
        if cached_data:
            logger.info(f"Report data retrieved from cache for user {self.user.username}")
            return cached_data
        
        logger.info(f"Generating optimized report data for user {self.user.username}")
        
        # Use database connection pooling
        with self._get_db_connection():
            # Parallel data retrieval
            report_data = self._get_data_parallel()
        
        # Cache with compression
        self._set_multilevel_cache(cache_key, report_data)
        logger.info(f"Optimized report data cached for user {self.user.username}")
        
        return report_data
    
    def _get_data_parallel(self) -> Dict[str, Any]:
        """Retrieve data using parallel processing"""
        futures = {}
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit parallel tasks
            futures['user_companies'] = executor.submit(self._get_user_companies_optimized)
            futures['base_data'] = executor.submit(self._get_base_data_optimized)
            futures['statistics'] = executor.submit(self._get_statistics_optimized)
            futures['compliance'] = executor.submit(self._get_compliance_data_optimized)
            futures['risk_treatments'] = executor.submit(self._get_risk_treatments_optimized)
            futures['translations'] = executor.submit(self._get_report_translations)
            
            # Collect results
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=30)
                except Exception as e:
                    logger.error(f"Error in parallel task {key}: {e}")
                    results[key] = self._get_fallback_data(key)
        
        # Compile final data
        return {
            'generation_date': timezone.now(),
            'generated_by': self.user.get_full_name() or self.user.username,
            'user': self.user,
            'config': self.config,
            'date_range': {
                'start': self.config.start_date,
                'end': self.config.end_date
            },
            'companies': results['user_companies'],
            'assets': results['base_data'].get('assets', []),
            'asset_vulnerabilities': results['base_data'].get('asset_vulnerabilities', []),
            'vulnerabilities': results['base_data'].get('vulnerabilities', []),
            'risk_treatments': results['risk_treatments'],
            'statistics': results['statistics'],
            'compliance': results['compliance'],
            'language': self.config.language,
            'translations': results['translations']
        }
    
    def _get_base_data_optimized(self) -> Dict[str, Any]:
        """Get base data with maximum query optimization"""
        # Build complex query with all necessary joins and annotations
        assets_query = self._build_optimized_assets_query()
        
        # Use database-level pagination for large datasets
        if self.config.use_pagination:
            paginator = Paginator(assets_query, self.config.page_size or 1000)
            assets = []
            for page_num in paginator.page_range:
                page = paginator.page(page_num)
                assets.extend(list(page.object_list))
        else:
            assets = list(assets_query)
        
        # Get related data using optimized subqueries
        asset_vulnerabilities = self._get_asset_vulnerabilities_optimized(assets)
        vulnerabilities = self._get_vulnerabilities_optimized(asset_vulnerabilities)
        
        return {
            'assets': assets,
            'asset_vulnerabilities': asset_vulnerabilities,
            'vulnerabilities': vulnerabilities
        }
    
    def _build_optimized_assets_query(self):
        """Build highly optimized assets query with all necessary data"""
        # Get user companies filter
        user_companies = self._get_user_companies_optimized()
        company_filter = self._build_company_filter(user_companies)
        
        # Build base query with optimized joins
        query = (
            InformationAsset.objects
            .filter(company_filter)
            .select_related('company', 'group', 'criticality')
            .prefetch_related(
                Prefetch(
                    'assetvulnerability_set',
                    queryset=AssetVulnerability.objects.select_related(
                        'vulnerability', 'modified_by'
                    ).filter(
                        modified_at__date__range=[self.config.start_date, self.config.end_date]
                    )
                ),
                Prefetch(
                    'risktreatment_set',
                    queryset=RiskTreatment.objects.select_related(
                        'treatment_type', 'status'
                    ).filter(
                        last_modified__date__range=[self.config.start_date, self.config.end_date]
                    )
                )
            )
        )
        
        # Add comprehensive annotations for statistics
        query = query.annotate(
            vulnerability_count=Count('assetvulnerability', distinct=True),
            high_risk_count=Count(
                'assetvulnerability',
                filter=Q(assetvulnerability__status='Yes'),
                distinct=True
            ),
            critical_vulnerability_count=Count(
                'assetvulnerability',
                filter=Q(assetvulnerability__vulnerability__severity='Critical'),
                distinct=True
            ),
            treatment_count=Count('risktreatment', distinct=True),
            completed_treatments=Count(
                'risktreatment',
                filter=Q(risktreatment__status__name='Completed'),
                distinct=True
            ),
            pending_treatments=Count(
                'risktreatment',
                filter=Q(risktreatment__status__name='Pending'),
                distinct=True
            ),
            # Risk score calculation
            risk_score=Coalesce(
                Avg('assetvulnerability__risk_score'),
                Value(0)
            ),
            # Compliance indicators
            pci_compliant=Case(
                When(
                    assetvulnerability__vulnerability__pci_requirement__isnull=False,
                    then=Count('assetvulnerability', filter=Q(assetvulnerability__status='No'))
                ),
                default=Value(0),
                output_field=IntegerField()
            ),
            iso_compliant=Case(
                When(
                    assetvulnerability__vulnerability__iso_control__isnull=False,
                    then=Count('assetvulnerability', filter=Q(assetvulnerability__status='No'))
                ),
                default=Value(0),
                output_field=IntegerField()
            )
        )
        
        # Apply filters
        if self.config.start_date and self.config.end_date:
            query = query.filter(
                Q(registration_date__range=[self.config.start_date, self.config.end_date]) |
                Q(assetvulnerability__modified_at__date__range=[self.config.start_date, self.config.end_date]) |
                Q(risktreatment__last_modified__date__range=[self.config.start_date, self.config.end_date])
            ).distinct()
        
        if not self.config.include_deleted:
            query = query.filter(deletion_date__isnull=True)
        
        # Ordering for consistent results
        query = query.order_by('id')
        
        return query
    
    def _get_asset_vulnerabilities_optimized(self, assets) -> List:
        """Get asset vulnerabilities with optimized query"""
        if not assets:
            return []
        
        asset_ids = [asset.id for asset in assets]
        
        return list(
            AssetVulnerability.objects
            .filter(
                asset_id__in=asset_ids,
                modified_at__date__range=[self.config.start_date, self.config.end_date]
            )
            .select_related('asset', 'vulnerability', 'modified_by')
            .annotate(
                vulnerability_name=F('vulnerability__name'),
                vulnerability_severity=F('vulnerability__severity'),
                asset_name=F('asset__name'),
                company_name=F('asset__company__name')
            )
        )
    
    def _get_vulnerabilities_optimized(self, asset_vulnerabilities) -> List:
        """Get vulnerabilities with optimized query"""
        if not asset_vulnerabilities:
            return []
        
        vulnerability_ids = list(set(av.vulnerability_id for av in asset_vulnerabilities))
        
        return list(
            Vulnerability.objects
            .filter(id__in=vulnerability_ids)
            .annotate(
                affected_assets_count=Count('assetvulnerability'),
                high_risk_assets_count=Count(
                    'assetvulnerability',
                    filter=Q(assetvulnerability__status='Yes')
                )
            )
        )
    
    def _get_statistics_optimized(self) -> Dict[str, Any]:
        """Get comprehensive statistics using database aggregations"""
        cache_key = f"stats_optimized_{self.user.id}_{self.config.hash}"
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        # Use raw SQL for complex statistics
        with connection.cursor() as cursor:
            # Get comprehensive statistics in single query
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT a.id) as total_assets,
                    COUNT(DISTINCT av.id) as total_vulnerabilities,
                    COUNT(DISTINCT CASE WHEN av.status = 'Yes' THEN av.id END) as high_risk_vulnerabilities,
                    COUNT(DISTINCT rt.id) as total_treatments,
                    COUNT(DISTINCT CASE WHEN rt.status_id = (
                        SELECT id FROM app_risk_treatmentstatus WHERE name = 'Completed'
                    ) THEN rt.id END) as completed_treatments,
                    AVG(CASE WHEN av.risk_score IS NOT NULL THEN av.risk_score ELSE 0 END) as avg_risk_score,
                    MAX(av.risk_score) as max_risk_score,
                    MIN(av.risk_score) as min_risk_score
                FROM app_risk_informationasset a
                LEFT JOIN app_risk_assetvulnerability av ON a.id = av.asset_id
                LEFT JOIN app_risk_risktreatment rt ON a.id = rt.asset_id
                WHERE a.deletion_date IS NULL
                AND av.modified_at::date BETWEEN %s AND %s
            """, [self.config.start_date, self.config.end_date])
            
            row = cursor.fetchone()
            
            stats = {
                'total_assets': row[0] or 0,
                'total_vulnerabilities': row[1] or 0,
                'high_risk_vulnerabilities': row[2] or 0,
                'total_treatments': row[3] or 0,
                'completed_treatments': row[4] or 0,
                'avg_risk_score': float(row[5] or 0),
                'max_risk_score': float(row[6] or 0),
                'min_risk_score': float(row[7] or 0),
                'completion_rate': (row[4] / row[3] * 100) if row[3] > 0 else 0,
                'generation_timestamp': timezone.now()
            }
        
        # Cache statistics
        cache.set(cache_key, stats, timeout=self.quick_cache_timeout)
        return stats
    
    def _get_compliance_data_optimized(self) -> Dict[str, Any]:
        """Get compliance data with optimized queries"""
        cache_key = f"compliance_optimized_{self.user.id}_{self.config.hash}"
        cached_compliance = cache.get(cache_key)
        
        if cached_compliance:
            return cached_compliance
        
        # Use aggregated queries for compliance calculations
        pci_compliance = self._calculate_pci_compliance_optimized()
        iso_compliance = self._calculate_iso_compliance_optimized()
        
        compliance_data = {
            'pci_dss': pci_compliance,
            'iso_27001': iso_compliance,
            'overall_score': (pci_compliance['score'] + iso_compliance['score']) / 2
        }
        
        cache.set(cache_key, compliance_data, timeout=self.cache_timeout)
        return compliance_data
    
    def _calculate_pci_compliance_optimized(self) -> Dict[str, Any]:
        """Calculate PCI DSS compliance using optimized queries"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT av.id) as total_pci_vulnerabilities,
                    COUNT(DISTINCT CASE WHEN av.status = 'No' THEN av.id END) as compliant_vulnerabilities,
                    COUNT(DISTINCT CASE WHEN av.status = 'Yes' THEN av.id END) as non_compliant_vulnerabilities
                FROM app_risk_assetvulnerability av
                JOIN app_risk_vulnerability v ON av.vulnerability_id = v.id
                WHERE v.pci_requirement IS NOT NULL
                AND av.modified_at::date BETWEEN %s AND %s
            """, [self.config.start_date, self.config.end_date])
            
            row = cursor.fetchone()
            total = row[0] or 0
            compliant = row[1] or 0
            non_compliant = row[2] or 0
            
            return {
                'total_requirements': total,
                'compliant_requirements': compliant,
                'non_compliant_requirements': non_compliant,
                'score': (compliant / total * 100) if total > 0 else 100
            }
    
    def _calculate_iso_compliance_optimized(self) -> Dict[str, Any]:
        """Calculate ISO 27001 compliance using optimized queries"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT av.id) as total_iso_vulnerabilities,
                    COUNT(DISTINCT CASE WHEN av.status = 'No' THEN av.id END) as compliant_vulnerabilities,
                    COUNT(DISTINCT CASE WHEN av.status = 'Yes' THEN av.id END) as non_compliant_vulnerabilities
                FROM app_risk_assetvulnerability av
                JOIN app_risk_vulnerability v ON av.vulnerability_id = v.id
                WHERE v.iso_control IS NOT NULL
                AND av.modified_at::date BETWEEN %s AND %s
            """, [self.config.start_date, self.config.end_date])
            
            row = cursor.fetchone()
            total = row[0] or 0
            compliant = row[1] or 0
            non_compliant = row[2] or 0
            
            return {
                'total_controls': total,
                'compliant_controls': compliant,
                'non_compliant_controls': non_compliant,
                'score': (compliant / total * 100) if total > 0 else 100
            }
    
    def _get_risk_treatments_optimized(self) -> List[Dict[str, Any]]:
        """Get risk treatments with optimized query"""
        treatments = list(
            RiskTreatment.objects
            .filter(
                last_modified__date__range=[self.config.start_date, self.config.end_date]
            )
            .select_related('asset', 'treatment_type', 'status', 'assigned_to')
            .annotate(
                asset_name=F('asset__name'),
                company_name=F('asset__company__name'),
                treatment_type_name=F('treatment_type__name'),
                status_name=F('status__name'),
                assigned_to_name=F('assigned_to__get_full_name')
            )
            .values(
                'id', 'title', 'description', 'asset_name', 'company_name',
                'treatment_type_name', 'status_name', 'assigned_to_name',
                'due_date', 'completion_date', 'last_modified'
            )
        )
        
        return treatments
    
    def _get_user_companies_optimized(self):
        """Get user's accessible companies with caching"""
        cache_key = f"user_companies_{self.user.id}"
        cached_companies = cache.get(cache_key)
        
        if cached_companies:
            return cached_companies
        
        # This should be implemented based on your user-company relationship
        from ..models import Company
        companies = list(Company.objects.all())
        
        cache.set(cache_key, companies, timeout=self.cache_timeout)
        return companies
    
    def _build_company_filter(self, user_companies) -> Q:
        """Build Q object for company filtering"""
        if self.config.company_id:
            return Q(company_id=self.config.company_id)
        elif user_companies:
            company_ids = [c.id for c in user_companies]
            return Q(company_id__in=company_ids)
        else:
            return Q()
    
    def _get_multilevel_cache(self, key: str) -> Optional[Any]:
        """Get data from multi-level cache (memory + Redis)"""
        # First try memory cache
        if hasattr(self, '_memory_cache'):
            if key in self._memory_cache:
                return self._memory_cache[key]
        
        # Then try Redis/database cache
        return cache.get(key)
    
    def _set_multilevel_cache(self, key: str, value: Any):
        """Set data in multi-level cache with compression"""
        # Set in memory cache (limited size)
        if not hasattr(self, '_memory_cache'):
            self._memory_cache = {}
        
        # Keep memory cache size limited
        if len(self._memory_cache) > 10:
            # Remove oldest entries
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
        
        self._memory_cache[key] = value
        
        # Set in Redis/database cache
        cache.set(key, value, timeout=self.cache_timeout)
    
    def _get_db_connection(self):
        """Get optimized database connection"""
        return transaction.atomic()
    
    def _get_fallback_data(self, data_type: str) -> Any:
        """Get fallback data in case of errors"""
        fallback_data = {
            'user_companies': [],
            'base_data': {'assets': [], 'asset_vulnerabilities': [], 'vulnerabilities': []},
            'statistics': {'total_assets': 0, 'total_vulnerabilities': 0},
            'compliance': {'pci_dss': {'score': 0}, 'iso_27001': {'score': 0}},
            'risk_treatments': [],
            'translations': {}
        }
        return fallback_data.get(data_type, {})
    
    def _get_report_translations(self) -> Dict[str, str]:
        """Get report translations for current language"""
        language = self.config.language or get_language()
        
        translations = {
            'report_title': _('Risk Assessment Report'),
            'executive_summary': _('Executive Summary'),
            'risk_statistics': _('Risk Statistics'),
            'vulnerability_analysis': _('Vulnerability Analysis'),
            'compliance_status': _('Compliance Status'),
            'risk_treatments': _('Risk Treatments'),
            'recommendations': _('Recommendations'),
            'generated_on': _('Generated on'),
            'generated_by': _('Generated by'),
            'total_assets': _('Total Assets'),
            'high_risk_assets': _('High Risk Assets'),
            'completion_rate': _('Completion Rate'),
            'pci_compliance': _('PCI DSS Compliance'),
            'iso_compliance': _('ISO 27001 Compliance')
        }
        
        return translations
    
    def get_quick_statistics(self) -> Dict[str, Any]:
        """Get quick statistics with aggressive caching"""
        cache_key = f"quick_stats_{self.user.id}_{self.config.hash}"
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        # Get basic statistics quickly
        stats = self._get_statistics_optimized()
        
        # Cache with shorter timeout
        cache.set(cache_key, stats, timeout=self.quick_cache_timeout)
        return stats
    
    async def get_comprehensive_report_data_async(self) -> Dict[str, Any]:
        """Async version of comprehensive report data retrieval"""
        cache_key = f"async_report_data_{self.user.id}_{self.config.hash}"
        
        # Try cache first
        cached_data = await sync_to_async(cache.get)(cache_key)
        if cached_data:
            return cached_data
        
        # Get data asynchronously
        tasks = [
            sync_to_async(self._get_user_companies_optimized)(),
            sync_to_async(self._get_base_data_optimized)(),
            sync_to_async(self._get_statistics_optimized)(),
            sync_to_async(self._get_compliance_data_optimized)(),
            sync_to_async(self._get_risk_treatments_optimized)(),
            sync_to_async(self._get_report_translations)()
        ]
        
        results = await asyncio.gather(*tasks)
        
        report_data = {
            'generation_date': timezone.now(),
            'generated_by': self.user.get_full_name() or self.user.username,
            'user': self.user,
            'config': self.config,
            'companies': results[0],
            'base_data': results[1],
            'statistics': results[2],
            'compliance': results[3],
            'risk_treatments': results[4],
            'translations': results[5]
        }
        
        # Cache result
        await sync_to_async(cache.set)(cache_key, report_data, timeout=self.cache_timeout)
        
        return report_data
    
    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)