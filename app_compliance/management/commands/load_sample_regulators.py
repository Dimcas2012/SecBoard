"""
Management command to load sample local compliance regulators for Ukraine, Lithuania, and Kazakhstan
with example requirements and controls.

Usage:
    python manage.py load_sample_regulators
    python manage.py load_sample_regulators --country UA
    python manage.py load_sample_regulators --country LT --with-controls
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app_compliance.models import (
    LocalComplianceRegulator, 
    LocalComplianceRequirement, 
    LocalComplianceControl
)
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Load sample local compliance regulators for Ukraine, Lithuania, and Kazakhstan'

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            type=str,
            choices=['UA', 'LT', 'KZ', 'ALL'],
            default='ALL',
            help='Country code to load regulators for (UA, LT, KZ, or ALL)'
        )
        parser.add_argument(
            '--with-controls',
            action='store_true',
            help='Create sample controls for requirements'
        )

    def handle(self, *args, **options):
        country = options['country']
        with_controls = options['with_controls']
        
        # Get or create admin user for created_by field
        admin_user = User.objects.filter(is_superuser=True).first()
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Loading Sample Local Compliance Regulators'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if country in ['UA', 'ALL']:
            self.load_ukraine_regulators(admin_user, with_controls)
        
        if country in ['LT', 'ALL']:
            self.load_lithuania_regulators(admin_user, with_controls)
        
        if country in ['KZ', 'ALL']:
            self.load_kazakhstan_regulators(admin_user, with_controls)
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✓ Sample regulators loaded successfully!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

    def load_ukraine_regulators(self, admin_user, with_controls):
        """Load Ukrainian regulators"""
        self.stdout.write(self.style.WARNING('\n🇺🇦 Loading UKRAINE regulators...'))
        
        # 1. Національний банк України (NBU)
        nbu, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='NBU',
            country='UA',
            defaults={
                'name': 'National Bank of Ukraine',
                'name_local': 'Національний банк України',
                'regulator_type': 'banking',
                'description': 'Central bank and main financial regulator of Ukraine',
                'website': 'https://bank.gov.ua',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {nbu.name}'))
        else:
            self.stdout.write(f'  → Already exists: {nbu.name}')
        
        # NBU Requirements
        self._create_nbu_requirements(nbu, admin_user, with_controls)
        
        # 2. НКЦПФР (National Securities Commission)
        nssmc, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='NSSMC',
            country='UA',
            defaults={
                'name': 'National Securities and Stock Market Commission',
                'name_local': 'Національна комісія з цінних паперів та фондового ринку',
                'regulator_type': 'securities',
                'description': 'Regulator of securities and stock market',
                'website': 'https://www.nssmc.gov.ua',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {nssmc.name}'))
        else:
            self.stdout.write(f'  → Already exists: {nssmc.name}')
        
        # 3. Державна податкова служба (State Tax Service)
        sts, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='STS',
            country='UA',
            defaults={
                'name': 'State Tax Service of Ukraine',
                'name_local': 'Державна податкова служба України',
                'regulator_type': 'tax',
                'description': 'Tax regulator and administration',
                'website': 'https://tax.gov.ua',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {sts.name}'))
        else:
            self.stdout.write(f'  → Already exists: {sts.name}')
        
        # 4. Мінцифри (Ministry of Digital Transformation)
        mindigital, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='MinDigital',
            country='UA',
            defaults={
                'name': 'Ministry of Digital Transformation',
                'name_local': 'Міністерство цифрової трансформації України',
                'regulator_type': 'data_protection',
                'description': 'Digital transformation and cybersecurity regulator',
                'website': 'https://thedigital.gov.ua',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {mindigital.name}'))
        else:
            self.stdout.write(f'  → Already exists: {mindigital.name}')
        
        # 5. Нацкомфінпослуг (National Financial Services Commission)
        nfsc, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='NFSC',
            country='UA',
            defaults={
                'name': 'National Commission for Financial Services Markets Regulation',
                'name_local': 'Національна комісія з регулювання ринків фінансових послуг',
                'regulator_type': 'financial',
                'description': 'Regulator of non-banking financial services',
                'website': 'https://nfp.gov.ua',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {nfsc.name}'))
        else:
            self.stdout.write(f'  → Already exists: {nfsc.name}')

    def _create_nbu_requirements(self, regulator, admin_user, with_controls):
        """Create sample NBU requirements"""
        
        # Постанова про кібербезпеку
        req1, created = LocalComplianceRequirement.objects.get_or_create(
            regulator=regulator,
            code='NBU-2023-77',
            is_template=True,
            defaults={
                'name': 'Regulation on Cybersecurity of Banks',
                'name_local': 'Постанова про кібербезпеку банків',
                'requirement_type': 'regulation',
                'description': 'Requirements for cybersecurity management in banking institutions',
                'status': 'active',
                'applicable_to': 'Banks, financial institutions',
                'publication_date': date(2023, 6, 15),
                'effective_date': date(2023, 9, 1),
                'deadline_date': date(2024, 1, 1),
                'is_mandatory': True,
                'priority': 'critical',
                'official_link': 'https://bank.gov.ua/ua/legislation',
                'created_by': admin_user
            }
        )
        
        if created and with_controls:
            self.stdout.write(f'    → Creating controls for: {req1.code}')
            self._create_sample_controls(req1, admin_user, 'NBU-CYBER', 5)

    def load_lithuania_regulators(self, admin_user, with_controls):
        """Load Lithuanian regulators"""
        self.stdout.write(self.style.WARNING('\n🇱🇹 Loading LITHUANIA regulators...'))
        
        # 1. Bank of Lithuania
        lb, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='LB',
            country='LT',
            defaults={
                'name': 'Bank of Lithuania',
                'name_local': 'Lietuvos bankas',
                'regulator_type': 'banking',
                'description': 'Central bank and financial regulator of Lithuania',
                'website': 'https://www.lb.lt',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {lb.name}'))
        else:
            self.stdout.write(f'  → Already exists: {lb.name}')
        
        # LB Requirement
        req1, created = LocalComplianceRequirement.objects.get_or_create(
            regulator=lb,
            code='LB-2023-01',
            is_template=True,
            defaults={
                'name': 'ICT and Security Risk Management Requirements',
                'name_local': 'IRT ir saugumo rizikos valdymo reikalavimai',
                'requirement_type': 'regulation',
                'description': 'Requirements for ICT security and risk management in financial institutions',
                'status': 'active',
                'applicable_to': 'Banks, financial institutions, payment service providers',
                'publication_date': date(2023, 1, 15),
                'effective_date': date(2023, 3, 1),
                'deadline_date': date(2023, 12, 31),
                'is_mandatory': True,
                'priority': 'high',
                'official_link': 'https://www.lb.lt/en/legislation',
                'created_by': admin_user
            }
        )
        
        if created and with_controls:
            self.stdout.write(f'    → Creating controls for: {req1.code}')
            self._create_sample_controls(req1, admin_user, 'LT-ICT', 4)
        
        # 2. State Data Protection Inspectorate
        sdpi, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='SDPI',
            country='LT',
            defaults={
                'name': 'State Data Protection Inspectorate',
                'name_local': 'Valstybinė duomenų apsaugos inspekcija',
                'regulator_type': 'data_protection',
                'description': 'Data protection and privacy regulator',
                'website': 'https://vdai.lrv.lt',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {sdpi.name}'))
        else:
            self.stdout.write(f'  → Already exists: {sdpi.name}')
        
        # 3. Insurance Supervision Commission
        isc, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='ISC',
            country='LT',
            defaults={
                'name': 'Insurance Supervision Commission',
                'name_local': 'Draudimo priežiūros komisija',
                'regulator_type': 'insurance',
                'description': 'Insurance market regulator',
                'website': 'https://www.lb.lt',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {isc.name}'))
        else:
            self.stdout.write(f'  → Already exists: {isc.name}')

    def load_kazakhstan_regulators(self, admin_user, with_controls):
        """Load Kazakhstan regulators"""
        self.stdout.write(self.style.WARNING('\n🇰🇿 Loading KAZAKHSTAN regulators...'))
        
        # 1. National Bank of Kazakhstan
        nbk, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='NBK',
            country='KZ',
            defaults={
                'name': 'National Bank of Kazakhstan',
                'name_local': 'Қазақстан Ұлттық Банкі',
                'regulator_type': 'banking',
                'description': 'Central bank and financial regulator of Kazakhstan',
                'website': 'https://nationalbank.kz',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {nbk.name}'))
        else:
            self.stdout.write(f'  → Already exists: {nbk.name}')
        
        # NBK Requirement
        req1, created = LocalComplianceRequirement.objects.get_or_create(
            regulator=nbk,
            code='NBK-2023-154',
            is_template=True,
            defaults={
                'name': 'Information Security Requirements for Financial Organizations',
                'name_local': 'Қаржы ұйымдарының ақпараттық қауіпсіздік талаптары',
                'requirement_type': 'regulation',
                'description': 'Requirements for information security in banks and financial organizations',
                'status': 'active',
                'applicable_to': 'Banks, microfinance organizations, payment organizations',
                'publication_date': date(2023, 5, 10),
                'effective_date': date(2023, 7, 1),
                'deadline_date': date(2024, 1, 1),
                'is_mandatory': True,
                'priority': 'critical',
                'official_link': 'https://nationalbank.kz/en/page/legislation',
                'created_by': admin_user
            }
        )
        
        if created and with_controls:
            self.stdout.write(f'    → Creating controls for: {req1.code}')
            self._create_sample_controls(req1, admin_user, 'KZ-INFOSEC', 6)
        
        # 2. Agency for Regulation and Development of Financial Market
        ardfm, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='ARDFM',
            country='KZ',
            defaults={
                'name': 'Agency for Regulation and Development of Financial Market',
                'name_local': 'Қаржы нарығын реттеу және дамыту агенттігі',
                'regulator_type': 'financial',
                'description': 'Regulator of insurance, securities, and non-banking sectors',
                'website': 'https://finreg.kz',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {ardfm.name}'))
        else:
            self.stdout.write(f'  → Already exists: {ardfm.name}')
        
        # 3. Committee for Control of Personal Data Protection
        ccpdp, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='CCPDP',
            country='KZ',
            defaults={
                'name': 'Committee for Control in the Sphere of Personal Data Protection',
                'name_local': 'Дербес деректерді қорғау саласындағы бақылау комитеті',
                'regulator_type': 'data_protection',
                'description': 'Personal data protection regulator',
                'website': 'https://www.gov.kz',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {ccpdp.name}'))
        else:
            self.stdout.write(f'  → Already exists: {ccpdp.name}')
        
        # 4. State Revenue Committee
        src, created = LocalComplianceRegulator.objects.get_or_create(
            acronym='SRC',
            country='KZ',
            defaults={
                'name': 'State Revenue Committee',
                'name_local': 'Мемлекеттік кірістер комитеті',
                'regulator_type': 'tax',
                'description': 'Tax and customs administration',
                'website': 'https://kgd.gov.kz',
                'is_active': True,
                'created_by': admin_user
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {src.name}'))
        else:
            self.stdout.write(f'  → Already exists: {src.name}')

    def _create_nbu_requirements(self, regulator, admin_user, with_controls):
        """Create specific NBU requirements"""
        
        requirements_data = [
            {
                'code': 'NBU-2023-77',
                'name': 'Regulation on Cybersecurity of Banks',
                'name_local': 'Постанова про кібербезпеку банків',
                'requirement_type': 'resolution',
                'description': 'Comprehensive cybersecurity requirements for banking sector including incident management, access control, and security monitoring',
                'applicable_to': 'All banks operating in Ukraine',
                'publication_date': date(2023, 6, 15),
                'effective_date': date(2023, 9, 1),
                'deadline_date': date(2024, 3, 1),
                'priority': 'critical',
            },
            {
                'code': 'NBU-2022-95',
                'name': 'Requirements for Business Continuity Management',
                'name_local': 'Вимоги до управління безперервністю діяльності',
                'requirement_type': 'regulation',
                'description': 'Requirements for business continuity and disaster recovery planning',
                'applicable_to': 'Banks, non-bank financial institutions',
                'publication_date': date(2022, 8, 10),
                'effective_date': date(2022, 10, 1),
                'deadline_date': date(2023, 4, 1),
                'priority': 'high',
            },
            {
                'code': 'NBU-2021-65',
                'name': 'Data Protection Requirements for Financial Sector',
                'name_local': 'Вимоги щодо захисту персональних даних у фінансовому секторі',
                'requirement_type': 'instruction',
                'description': 'Personal data protection requirements aligned with GDPR principles',
                'applicable_to': 'All financial institutions',
                'publication_date': date(2021, 5, 20),
                'effective_date': date(2021, 7, 1),
                'deadline_date': date(2022, 1, 1),
                'priority': 'high',
            },
        ]
        
        for req_data in requirements_data:
            req, created = LocalComplianceRequirement.objects.get_or_create(
                regulator=regulator,
                code=req_data['code'],
                is_template=True,
                defaults={
                    **req_data,
                    'status': 'active',
                    'is_mandatory': True,
                    'official_link': 'https://bank.gov.ua/ua/legislation',
                    'created_by': admin_user
                }
            )
            
            if created:
                self.stdout.write(f'    ✓ Requirement: {req.code}')
                
                if with_controls:
                    # Create sample controls for this requirement
                    control_prefix = req_data['code'].replace('-', '_')
                    self._create_sample_controls(req, admin_user, control_prefix, 4)
            else:
                self.stdout.write(f'    → Requirement exists: {req.code}')

    def _create_sample_controls(self, requirement, admin_user, prefix, count):
        """Create sample controls for a requirement template"""
        
        control_templates = [
            {
                'suffix': '001',
                'name': 'Security Policy Documentation',
                'description': 'Develop and maintain comprehensive security policies',
                'priority': 'critical',
            },
            {
                'suffix': '002',
                'name': 'Access Control Implementation',
                'description': 'Implement role-based access control mechanisms',
                'priority': 'high',
            },
            {
                'suffix': '003',
                'name': 'Security Monitoring and Logging',
                'description': 'Establish continuous security monitoring and logging',
                'priority': 'high',
            },
            {
                'suffix': '004',
                'name': 'Incident Response Procedures',
                'description': 'Develop and test incident response procedures',
                'priority': 'critical',
            },
            {
                'suffix': '005',
                'name': 'Employee Security Training',
                'description': 'Conduct regular security awareness training',
                'priority': 'medium',
            },
            {
                'suffix': '006',
                'name': 'Vulnerability Management',
                'description': 'Implement vulnerability assessment and patch management',
                'priority': 'high',
            },
        ]
        
        for i, template in enumerate(control_templates[:count]):
            code = f"{prefix}-{template['suffix']}"
            
            control, created = LocalComplianceControl.objects.get_or_create(
                requirement=requirement,
                company=None,  # Template control
                code=code,
                defaults={
                    'name': template['name'],
                    'description': template['description'],
                    'status': 'not_started',
                    'priority': template['priority'],
                    'implementation_notes': f'Implementation guidance for {template["name"]}',
                    'evidence_notes': 'Required: Policy documents, procedures, audit logs',
                    'created_by': admin_user
                }
            )
            
            if created:
                self.stdout.write(f'      • Control: {code} - {template["name"]}')

