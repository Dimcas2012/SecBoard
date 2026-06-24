"""
Standalone Python script to load sample local compliance regulators
Can be executed directly or imported in Django shell

Usage in Django shell:
    python manage.py shell
    >>> exec(open('app_compliance/load_sample_data.py').read())

Or run directly (if migrations are applied):
    python manage.py shell < app_compliance/load_sample_data.py
"""

from app_compliance.models import LocalComplianceRegulator, LocalComplianceRequirement, LocalComplianceControl
from django.contrib.auth.models import User
from datetime import date, timedelta

# Get admin user
admin_user = User.objects.filter(is_superuser=True).first()

print("=" * 70)
print("Loading Sample Local Compliance Regulators")
print("=" * 70)

# ========================
# UKRAINE REGULATORS
# ========================
print("\n🇺🇦 UKRAINE Regulators:")

# 1. NBU
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
print(f"  {'✓ Created' if created else '→ Exists'}: NBU - {nbu.name}")

# NBU Requirement 1: Cybersecurity
nbu_cyber, created = LocalComplianceRequirement.objects.get_or_create(
    regulator=nbu,
    code='NBU-2023-77',
    is_template=True,
    defaults={
        'name': 'Regulation on Cybersecurity of Banks',
        'name_local': 'Постанова про кібербезпеку банків',
        'requirement_type': 'resolution',
        'description': 'Comprehensive cybersecurity requirements for banking sector',
        'status': 'active',
        'applicable_to': 'All banks operating in Ukraine',
        'publication_date': date(2023, 6, 15),
        'effective_date': date(2023, 9, 1),
        'deadline_date': date(2024, 3, 1),
        'is_mandatory': True,
        'priority': 'critical',
        'official_link': 'https://bank.gov.ua/ua/legislation',
        'created_by': admin_user
    }
)
print(f"    {'✓ Created' if created else '→ Exists'}: {nbu_cyber.code}")

# Add sample controls to NBU-2023-77
if created:
    controls_data = [
        ('NBU-CYBER-001', 'Security Policy Documentation', 'Develop and maintain comprehensive security policies', 'critical'),
        ('NBU-CYBER-002', 'Access Control Implementation', 'Implement role-based access control mechanisms', 'high'),
        ('NBU-CYBER-003', 'Security Monitoring and Logging', 'Establish continuous security monitoring', 'high'),
        ('NBU-CYBER-004', 'Incident Response Procedures', 'Develop and test incident response procedures', 'critical'),
    ]
    
    for code, name, desc, priority in controls_data:
        LocalComplianceControl.objects.create(
            requirement=nbu_cyber,
            company=None,  # Template control
            code=code,
            name=name,
            description=desc,
            status='not_started',
            priority=priority,
            created_by=admin_user
        )
    print(f"      → Added {len(controls_data)} sample controls")

# 2. NSSMC
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
print(f"  {'✓ Created' if created else '→ Exists'}: NSSMC - {nssmc.name}")

# 3. STS
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
print(f"  {'✓ Created' if created else '→ Exists'}: STS - {sts.name}")

# 4. MinDigital
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
print(f"  {'✓ Created' if created else '→ Exists'}: MinDigital - {mindigital.name}")

# 5. NFSC
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
print(f"  {'✓ Created' if created else '→ Exists'}: NFSC - {nfsc.name}")

# ========================
# LITHUANIA REGULATORS
# ========================
print("\n🇱🇹 LITHUANIA Regulators:")

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
print(f"  {'✓ Created' if created else '→ Exists'}: LB - {lb.name}")

# LB Requirement
lb_ict, created = LocalComplianceRequirement.objects.get_or_create(
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
print(f"    {'✓ Created' if created else '→ Exists'}: {lb_ict.code}")

# 2. SDPI
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
print(f"  {'✓ Created' if created else '→ Exists'}: SDPI - {sdpi.name}")

# 3. ISC
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
print(f"  {'✓ Created' if created else '→ Exists'}: ISC - {isc.name}")

# ========================
# KAZAKHSTAN REGULATORS
# ========================
print("\n🇰🇿 KAZAKHSTAN Regulators:")

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
print(f"  {'✓ Created' if created else '→ Exists'}: NBK - {nbk.name}")

# NBK Requirement
nbk_infosec, created = LocalComplianceRequirement.objects.get_or_create(
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
print(f"    {'✓ Created' if created else '→ Exists'}: {nbk_infosec.code}")

# 2. ARDFM
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
print(f"  {'✓ Created' if created else '→ Exists'}: ARDFM - {ardfm.name}")

# 3. CCPDP
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
print(f"  {'✓ Created' if created else '→ Exists'}: CCPDP - {ccpdp.name}")

# 4. SRC
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
print(f"  {'✓ Created' if created else '→ Exists'}: SRC - {src.name}")

# ========================
# CREATE REQUIREMENT TEMPLATES WITH CONTROLS
# ========================

print("\n📋 Creating Requirement Templates with Controls...")

# NBU-2023-77: Cybersecurity
nbu_cyber, created = LocalComplianceRequirement.objects.get_or_create(
    regulator=nbu,
    code='NBU-2023-77',
    is_template=True,
    defaults={
        'name': 'Regulation on Cybersecurity of Banks',
        'name_local': 'Постанова про кібербезпеку банків',
        'requirement_type': 'resolution',
        'description': 'Comprehensive cybersecurity requirements for banking sector',
        'status': 'active',
        'applicable_to': 'All banks operating in Ukraine',
        'publication_date': date(2023, 6, 15),
        'effective_date': date(2023, 9, 1),
        'deadline_date': date(2024, 3, 1),
        'is_mandatory': True,
        'priority': 'critical',
        'official_link': 'https://bank.gov.ua/ua/legislation',
        'created_by': admin_user
    }
)
print(f"  {'✓ Created' if created else '→ Exists'}: {nbu_cyber.code}")

if created:
    # Add controls
    controls_data = [
        ('NBU-CYBER-001', 'Security Policy Documentation', 'Develop and maintain comprehensive security policies', 'critical'),
        ('NBU-CYBER-002', 'Access Control Implementation', 'Implement RBAC with least privilege principle', 'high'),
        ('NBU-CYBER-003', 'Security Monitoring and Logging', 'Establish SIEM and continuous monitoring', 'high'),
        ('NBU-CYBER-004', 'Incident Response Procedures', 'Develop and test IR procedures', 'critical'),
        ('NBU-CYBER-005', 'Vulnerability Management', 'Regular scanning and patch management', 'high'),
    ]
    
    for code, name, desc, priority in controls_data:
        LocalComplianceControl.objects.create(
            requirement=nbu_cyber,
            company=None,
            code=code,
            name=name,
            description=desc,
            status='not_started',
            priority=priority,
            created_by=admin_user
        )
    print(f"    → Added {len(controls_data)} controls")

# NBU-2022-95: Business Continuity
nbu_bcm, created = LocalComplianceRequirement.objects.get_or_create(
    regulator=nbu,
    code='NBU-2022-95',
    is_template=True,
    defaults={
        'name': 'Requirements for Business Continuity Management',
        'name_local': 'Вимоги до управління безперервністю діяльності',
        'requirement_type': 'regulation',
        'description': 'Business continuity and disaster recovery requirements',
        'status': 'active',
        'applicable_to': 'Banks, non-bank financial institutions',
        'publication_date': date(2022, 8, 10),
        'effective_date': date(2022, 10, 1),
        'deadline_date': date(2023, 4, 1),
        'is_mandatory': True,
        'priority': 'high',
        'created_by': admin_user
    }
)
print(f"  {'✓ Created' if created else '→ Exists'}: {nbu_bcm.code}")

if created:
    controls_data = [
        ('NBU-BCM-001', 'Business Impact Analysis', 'Conduct BIA for critical functions', 'high'),
        ('NBU-BCM-002', 'Disaster Recovery Plan', 'Develop and test DR plan', 'critical'),
        ('NBU-BCM-003', 'Alternative Processing Site', 'Establish backup site', 'high'),
    ]
    
    for code, name, desc, priority in controls_data:
        LocalComplianceControl.objects.create(
            requirement=nbu_bcm,
            company=None,
            code=code,
            name=name,
            description=desc,
            status='not_started',
            priority=priority,
            created_by=admin_user
        )
    print(f"    → Added {len(controls_data)} controls")

# LB-2023-01: ICT Security (Lithuania)
lb_ict, created = LocalComplianceRequirement.objects.get_or_create(
    regulator=lb,
    code='LB-2023-01',
    is_template=True,
    defaults={
        'name': 'ICT and Security Risk Management Requirements',
        'name_local': 'IRT ir saugumo rizikos valdymo reikalavimai',
        'requirement_type': 'regulation',
        'description': 'ICT security and risk management requirements',
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
print(f"  {'✓ Created' if created else '→ Exists'}: {lb_ict.code}")

if created:
    controls_data = [
        ('LB-ICT-001', 'ICT Governance Framework', 'Establish ICT governance', 'high'),
        ('LB-ICT-002', 'Cybersecurity Controls', 'Implement security controls', 'high'),
        ('LB-ICT-003', 'Third-Party Management', 'Manage service providers', 'medium'),
        ('LB-ICT-004', 'Business Continuity Testing', 'Test BCP/DR plans', 'critical'),
    ]
    
    for code, name, desc, priority in controls_data:
        LocalComplianceControl.objects.create(
            requirement=lb_ict,
            company=None,
            code=code,
            name=name,
            description=desc,
            status='not_started',
            priority=priority,
            created_by=admin_user
        )
    print(f"    → Added {len(controls_data)} controls")

# NBK-2023-154: InfoSec (Kazakhstan)
nbk_infosec, created = LocalComplianceRequirement.objects.get_or_create(
    regulator=nbk,
    code='NBK-2023-154',
    is_template=True,
    defaults={
        'name': 'Information Security Requirements for Financial Organizations',
        'name_local': 'Қаржы ұйымдарының ақпараттық қауіпсіздік талаптары',
        'requirement_type': 'regulation',
        'description': 'Information security requirements for banks and financial institutions',
        'status': 'active',
        'applicable_to': 'Banks, microfinance, payment organizations',
        'publication_date': date(2023, 5, 10),
        'effective_date': date(2023, 7, 1),
        'deadline_date': date(2024, 1, 1),
        'is_mandatory': True,
        'priority': 'critical',
        'official_link': 'https://nationalbank.kz/en/page/legislation',
        'created_by': admin_user
    }
)
print(f"  {'✓ Created' if created else '→ Exists'}: {nbk_infosec.code}")

if created:
    controls_data = [
        ('NBK-INFOSEC-001', 'Security Organization', 'Establish security structure', 'critical'),
        ('NBK-INFOSEC-002', 'Access Control', 'Implement access controls', 'high'),
        ('NBK-INFOSEC-003', 'Cryptographic Protection', 'Crypto controls and key management', 'high'),
        ('NBK-INFOSEC-004', 'Security Audit', 'Regular security audits', 'high'),
    ]
    
    for code, name, desc, priority in controls_data:
        LocalComplianceControl.objects.create(
            requirement=nbk_infosec,
            company=None,
            code=code,
            name=name,
            description=desc,
            status='not_started',
            priority=priority,
            created_by=admin_user
        )
    print(f"    → Added {len(controls_data)} controls")

# Summary
print("\n" + "=" * 70)
total_regulators = LocalComplianceRegulator.objects.filter(country__in=['UA', 'LT', 'KZ']).count()
total_requirements = LocalComplianceRequirement.objects.filter(
    regulator__country__in=['UA', 'LT', 'KZ'],
    is_template=True
).count()
total_controls = LocalComplianceControl.objects.filter(
    requirement__regulator__country__in=['UA', 'LT', 'KZ'],
    company__isnull=True
).count()

print(f"✓ Total Regulators: {total_regulators}")
print(f"✓ Total Requirement Templates: {total_requirements}")
print(f"✓ Total Template Controls: {total_controls}")
print("=" * 70)
print("\n📊 Breakdown by country:")
for country_code in ['UA', 'LT', 'KZ']:
    flag = {'UA': '🇺🇦', 'LT': '🇱🇹', 'KZ': '🇰🇿'}[country_code]
    regs = LocalComplianceRegulator.objects.filter(country=country_code).count()
    reqs = LocalComplianceRequirement.objects.filter(
        regulator__country=country_code,
        is_template=True
    ).count()
    ctrls = LocalComplianceControl.objects.filter(
        requirement__regulator__country=country_code,
        company__isnull=True
    ).count()
    print(f"  {flag} {country_code}: {regs} regulators, {reqs} requirements, {ctrls} controls")

print("\n" + "=" * 70)
print("\nTo view the data:")
print("  1. Dashboard: /compliance/local/")
print("  2. Requirements Library: /compliance/local/requirements/")
print("  3. Django Admin: /admin/app_compliance/localcomplianceregulator/")
print("=" * 70)

