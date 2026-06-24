from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app_compliance.models import ComplianceFramework, ControlCategory, Control


class Command(BaseCommand):
    help = 'Expand existing frameworks with additional categories and controls'

    def add_arguments(self, parser):
        parser.add_argument(
            '--framework',
            type=str,
            choices=['pci_dss', 'iso_27001', 'soc2', 'all'],
            default='all',
            help='Which framework to expand'
        )

    def handle(self, *args, **options):
        framework_choice = options['framework']
        
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No user found!'))
            return
        
        self.stdout.write(f'User: {user.username}')
        self.stdout.write('='*60)
        
        # Expand frameworks
        if framework_choice == 'all' or framework_choice == 'pci_dss':
            self.expand_pci_dss(user)
        
        if framework_choice == 'all' or framework_choice == 'iso_27001':
            self.expand_iso_27001(user)
        
        if framework_choice == 'all' or framework_choice == 'soc2':
            self.expand_soc2(user)
        
        self.stdout.write(self.style.SUCCESS('\n[DONE] Expansion completed!'))

    def expand_pci_dss(self, user):
        """Expand PCI DSS 4.0 framework with all categories and controls"""
        self.stdout.write('\n[PCI DSS] Expanding PCI DSS 4.0...')
        
        # Find existing framework
        framework = ComplianceFramework.objects.filter(
            name='PCI DSS',
            version='4.0'
        ).first()
        
        if not framework:
            self.stdout.write(self.style.WARNING('  PCI DSS 4.0 not found, skipping...'))
            return
        
        # Get existing category count
        existing_cats = ControlCategory.objects.filter(framework=framework).count()
        self.stdout.write(f'  Existing categories: {existing_cats}')
        
        # Categories and Controls - PCI DSS 4.0 Complete (REQ-2 to REQ-12)
        categories_data = [
            {
                'code': 'REQ-2',
                'name': 'Apply Secure Configurations to All System Components',
                'description': 'Malicious individuals, both external and internal to an entity, often use default passwords to compromise systems',
                'order': 2,
                'controls': [
                    {'code': '2.1', 'name': 'Processes and mechanisms for applying secure configurations are defined', 'evidence': 2},
                    {'code': '2.2', 'name': 'System components are configured and managed securely', 'evidence': 5},
                    {'code': '2.3', 'name': 'Wireless environments are configured and managed securely', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-3',
                'name': 'Protect Stored Account Data',
                'description': 'Protection methods such as encryption, truncation, masking, and hashing are critical components of account data protection',
                'order': 3,
                'controls': [
                    {'code': '3.1', 'name': 'Processes and mechanisms for protecting stored account data are defined', 'evidence': 3},
                    {'code': '3.2', 'name': 'Storage of account data is kept to a minimum', 'evidence': 2},
                    {'code': '3.3', 'name': 'Sensitive authentication data is not stored after authorization', 'evidence': 4},
                    {'code': '3.4', 'name': 'Access to displays of full PAN is restricted', 'evidence': 2},
                    {'code': '3.5', 'name': 'PAN is secured wherever it is stored', 'evidence': 5},
                ]
            },
            {
                'code': 'REQ-4',
                'name': 'Protect Cardholder Data with Strong Cryptography',
                'description': 'Cryptographic controls protect cardholder data during transmission over open, public networks',
                'order': 4,
                'controls': [
                    {'code': '4.1', 'name': 'Processes and mechanisms for protecting cardholder data with strong cryptography are defined', 'evidence': 3},
                    {'code': '4.2', 'name': 'Strong cryptography and security protocols are used to safeguard sensitive cardholder data', 'evidence': 4},
                    {'code': '4.3', 'name': 'Cardholder data is protected with strong cryptography during transmission', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-5',
                'name': 'Protect All Systems and Networks from Malicious Software',
                'description': 'Malicious software, commonly referred to as malware, including viruses, worms, and Trojans, enters the network during many business-approved activities',
                'order': 5,
                'controls': [
                    {'code': '5.1', 'name': 'Processes and mechanisms for protecting systems and networks from malicious software are defined', 'evidence': 2},
                    {'code': '5.2', 'name': 'Malicious software is prevented, or detected and addressed', 'evidence': 4},
                    {'code': '5.3', 'name': 'Anti-malware solutions are kept current, actively running, and capable of generating audit logs', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-6',
                'name': 'Develop and Maintain Secure Systems and Software',
                'description': 'Security vulnerabilities in systems and applications are often exploited by malicious individuals',
                'order': 6,
                'controls': [
                    {'code': '6.1', 'name': 'Processes and mechanisms for developing and maintaining secure systems and software are defined', 'evidence': 3},
                    {'code': '6.2', 'name': 'System and software development life cycle (SDLC) processes include security requirements', 'evidence': 4},
                    {'code': '6.3', 'name': 'Security vulnerabilities are identified and addressed', 'evidence': 5},
                    {'code': '6.4', 'name': 'Public-facing web applications are protected against attacks', 'evidence': 4},
                    {'code': '6.5', 'name': 'Security patches are installed in a timely manner', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-7',
                'name': 'Restrict Access to System Components and Cardholder Data',
                'description': 'Access control is a critical security requirement for cardholder data',
                'order': 7,
                'controls': [
                    {'code': '7.1', 'name': 'Processes and mechanisms for restricting access to system components and cardholder data are defined', 'evidence': 3},
                    {'code': '7.2', 'name': 'Access to system components and cardholder data is restricted', 'evidence': 5},
                    {'code': '7.3', 'name': 'Access to system components and cardholder data is restricted to only those individuals whose job requires such access', 'evidence': 4},
                ]
            },
            {
                'code': 'REQ-8',
                'name': 'Identify Users and Authenticate Access to System Components',
                'description': 'Assigning a unique identification (ID) to each person with access ensures that each individual is uniquely accountable for their actions',
                'order': 8,
                'controls': [
                    {'code': '8.1', 'name': 'Processes and mechanisms for identifying users and authenticating access are defined', 'evidence': 3},
                    {'code': '8.2', 'name': 'Users are identified and authenticated', 'evidence': 4},
                    {'code': '8.3', 'name': 'Strong authentication is implemented for all non-console administrative access', 'evidence': 3},
                    {'code': '8.4', 'name': 'Multi-factor authentication is implemented for all non-console administrative access', 'evidence': 4},
                    {'code': '8.5', 'name': 'Multi-factor authentication is implemented for all remote network access', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-9',
                'name': 'Restrict Physical Access to Cardholder Data',
                'description': 'Physical access controls limit and monitor access to system components that store, process, or transmit cardholder data',
                'order': 9,
                'controls': [
                    {'code': '9.1', 'name': 'Processes and mechanisms for restricting physical access to cardholder data are defined', 'evidence': 2},
                    {'code': '9.2', 'name': 'Physical access to cardholder data is restricted', 'evidence': 3},
                    {'code': '9.3', 'name': 'Physical access to media containing cardholder data is restricted', 'evidence': 2},
                ]
            },
            {
                'code': 'REQ-10',
                'name': 'Log and Monitor All Access to System Components and Cardholder Data',
                'description': 'Logging mechanisms and the ability to track user activities are critical in preventing, detecting, or minimizing the impact of a data compromise',
                'order': 10,
                'controls': [
                    {'code': '10.1', 'name': 'Processes and mechanisms for logging and monitoring access are defined', 'evidence': 3},
                    {'code': '10.2', 'name': 'Audit logs are implemented to track access to system components and cardholder data', 'evidence': 5},
                    {'code': '10.3', 'name': 'Audit logs are protected from tampering and unauthorized access', 'evidence': 4},
                    {'code': '10.4', 'name': 'Audit logs are reviewed to identify anomalies or suspicious activity', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-11',
                'name': 'Test Security of Systems and Networks Regularly',
                'description': 'Vulnerabilities are being discovered continually by malicious individuals and researchers, and being introduced by new software',
                'order': 11,
                'controls': [
                    {'code': '11.1', 'name': 'Processes and mechanisms for testing security of systems and networks are defined', 'evidence': 3},
                    {'code': '11.2', 'name': 'Wireless access points are identified and monitored', 'evidence': 2},
                    {'code': '11.3', 'name': 'External and internal vulnerability scans are performed', 'evidence': 4},
                    {'code': '11.4', 'name': 'Penetration testing is performed', 'evidence': 3},
                    {'code': '11.5', 'name': 'Intrusion-detection and/or intrusion-prevention techniques are implemented', 'evidence': 3},
                ]
            },
            {
                'code': 'REQ-12',
                'name': 'Support Information Security with Organizational Policies',
                'description': 'Strong security policy sets the security tone for the whole entity and informs personnel what is expected of them',
                'order': 12,
                'controls': [
                    {'code': '12.1', 'name': 'Processes and mechanisms for supporting information security with organizational policies are defined', 'evidence': 2},
                    {'code': '12.2', 'name': 'Information security policy is established, published, maintained, and disseminated', 'evidence': 3},
                    {'code': '12.3', 'name': 'Risk assessment is performed', 'evidence': 4},
                    {'code': '12.4', 'name': 'Risk management program is implemented', 'evidence': 3},
                    {'code': '12.5', 'name': 'Information security awareness program is implemented', 'evidence': 3},
                ]
            },
        ]
        
        added_cats = 0
        added_ctrls = 0
        
        for cat_data in categories_data:
            # Check if category already exists
            if ControlCategory.objects.filter(framework=framework, code=cat_data['code']).exists():
                self.stdout.write(f'  Category {cat_data["code"]} already exists, skipping...')
                continue
            
            category = ControlCategory.objects.create(
                framework=framework,
                code=cat_data['code'],
                name=cat_data['name'],
                description=cat_data.get('description', ''),
                order=cat_data.get('order', 0)
            )
            added_cats += 1
            
            for ctrl_data in cat_data['controls']:
                # Check if control already exists
                if not Control.objects.filter(category=category, code=ctrl_data['code']).exists():
                    try:
                        Control.objects.create(
                            category=category,
                            code=ctrl_data['code'],
                            name=ctrl_data['name'],
                            description=f'PCI DSS requirement {ctrl_data["code"]}: {ctrl_data["name"]}',
                            status='not_started',
                            priority='high',
                            required_evidence_count=ctrl_data.get('evidence', 1),
                            created_by=user
                        )
                        added_ctrls += 1
                    except Exception as e:
                        self.stdout.write(f'    Error adding control {ctrl_data["code"]}: {e}')
        
        self.stdout.write(self.style.SUCCESS(f'  [OK] Added {added_cats} categories, {added_ctrls} controls'))

    def expand_iso_27001(self, user):
        """Expand ISO 27001:2022 framework with all categories and controls"""
        self.stdout.write('\n[ISO 27001] Expanding ISO 27001:2022...')
        
        framework = ComplianceFramework.objects.filter(
            name='ISO/IEC 27001',
            version='2022'
        ).first()
        
        if not framework:
            self.stdout.write(self.style.WARNING('  ISO 27001:2022 not found, skipping...'))
            return
        
        existing_cats = ControlCategory.objects.filter(framework=framework).count()
        self.stdout.write(f'  Existing categories: {existing_cats}')
        
        # Expand A.5 category and add A.6, A.7, A.8
        categories_data = [
            {
                'code': 'A.5',
                'name': 'Organizational Controls',
                'description': 'Controls related to organizational aspects of information security',
                'order': 5,
                'controls': [
                    {'code': 'A.5.6', 'name': 'Contact with special interest groups', 'evidence': 1},
                    {'code': 'A.5.7', 'name': 'Threat intelligence', 'evidence': 2},
                    {'code': 'A.5.8', 'name': 'Information security in project management', 'evidence': 2},
                    {'code': 'A.5.9', 'name': 'Inventory of information and other associated assets', 'evidence': 3},
                    {'code': 'A.5.10', 'name': 'Acceptable use of information and other associated assets', 'evidence': 2},
                    {'code': 'A.5.11', 'name': 'Return of assets', 'evidence': 1},
                    {'code': 'A.5.12', 'name': 'Classification of information', 'evidence': 2},
                    {'code': 'A.5.13', 'name': 'Labelling of information', 'evidence': 2},
                    {'code': 'A.5.14', 'name': 'Information transfer', 'evidence': 2},
                    {'code': 'A.5.15', 'name': 'Access control', 'evidence': 3},
                    {'code': 'A.5.16', 'name': 'Identity management', 'evidence': 3},
                    {'code': 'A.5.17', 'name': 'Authentication information', 'evidence': 3},
                    {'code': 'A.5.18', 'name': 'Access rights', 'evidence': 3},
                    {'code': 'A.5.19', 'name': 'Information security in supplier relationships', 'evidence': 3},
                    {'code': 'A.5.20', 'name': 'Addressing information security within supplier agreements', 'evidence': 2},
                    {'code': 'A.5.21', 'name': 'Managing information security in the ICT supply chain', 'evidence': 2},
                    {'code': 'A.5.22', 'name': 'Monitoring, review and change management of supplier services', 'evidence': 2},
                    {'code': 'A.5.23', 'name': 'Information security for use of cloud services', 'evidence': 3},
                    {'code': 'A.5.24', 'name': 'Information security incident management planning and preparation', 'evidence': 2},
                    {'code': 'A.5.25', 'name': 'Assessment and decision on information security events', 'evidence': 2},
                    {'code': 'A.5.26', 'name': 'Response to information security incidents', 'evidence': 3},
                    {'code': 'A.5.27', 'name': 'Learning from information security incidents', 'evidence': 2},
                    {'code': 'A.5.28', 'name': 'Collection of evidence', 'evidence': 2},
                    {'code': 'A.5.29', 'name': 'Information security during disruption', 'evidence': 2},
                    {'code': 'A.5.30', 'name': 'ICT readiness for business continuity', 'evidence': 3},
                ]
            },
            {
                'code': 'A.6',
                'name': 'People Controls',
                'description': 'Controls related to personnel security',
                'order': 6,
                'controls': [
                    {'code': 'A.6.1', 'name': 'Screening', 'evidence': 2},
                    {'code': 'A.6.2', 'name': 'Terms and conditions of employment', 'evidence': 2},
                    {'code': 'A.6.3', 'name': 'Information security awareness, education and training', 'evidence': 3},
                    {'code': 'A.6.4', 'name': 'Disciplinary process', 'evidence': 1},
                    {'code': 'A.6.5', 'name': 'Responsibilities after termination or change of employment', 'evidence': 2},
                    {'code': 'A.6.6', 'name': 'Confidentiality or non-disclosure agreements', 'evidence': 2},
                    {'code': 'A.6.7', 'name': 'Remote working', 'evidence': 3},
                ]
            },
            {
                'code': 'A.7',
                'name': 'Physical Controls',
                'description': 'Controls related to physical and environmental security',
                'order': 7,
                'controls': [
                    {'code': 'A.7.1', 'name': 'Physical security perimeters', 'evidence': 3},
                    {'code': 'A.7.2', 'name': 'Physical entry', 'evidence': 2},
                    {'code': 'A.7.3', 'name': 'Securing offices, rooms and facilities', 'evidence': 2},
                    {'code': 'A.7.4', 'name': 'Physical security monitoring', 'evidence': 2},
                    {'code': 'A.7.5', 'name': 'Protecting against physical and environmental threats', 'evidence': 2},
                    {'code': 'A.7.6', 'name': 'Working in secure areas', 'evidence': 2},
                    {'code': 'A.7.7', 'name': 'Clear desk and clear screen', 'evidence': 2},
                    {'code': 'A.7.8', 'name': 'Equipment siting and protection', 'evidence': 2},
                    {'code': 'A.7.9', 'name': 'Security of assets off-premises', 'evidence': 2},
                    {'code': 'A.7.10', 'name': 'Storage media', 'evidence': 2},
                    {'code': 'A.7.11', 'name': 'Supporting utilities', 'evidence': 2},
                    {'code': 'A.7.12', 'name': 'Cabling security', 'evidence': 2},
                    {'code': 'A.7.13', 'name': 'Equipment maintenance', 'evidence': 2},
                    {'code': 'A.7.14', 'name': 'Secure disposal or re-use of equipment', 'evidence': 2},
                ]
            },
            {
                'code': 'A.8',
                'name': 'Technological Controls',
                'description': 'Controls related to technology and systems',
                'order': 8,
                'controls': [
                    {'code': 'A.8.1', 'name': 'User endpoint devices', 'evidence': 3},
                    {'code': 'A.8.2', 'name': 'Privileged access rights', 'evidence': 3},
                    {'code': 'A.8.3', 'name': 'Information access restriction', 'evidence': 2},
                    {'code': 'A.8.4', 'name': 'Access to source code', 'evidence': 2},
                    {'code': 'A.8.5', 'name': 'Secure authentication', 'evidence': 4},
                    {'code': 'A.8.6', 'name': 'Capacity management', 'evidence': 2},
                    {'code': 'A.8.7', 'name': 'Protection against malware', 'evidence': 3},
                    {'code': 'A.8.8', 'name': 'Management of technical vulnerabilities', 'evidence': 3},
                    {'code': 'A.8.9', 'name': 'Configuration management', 'evidence': 3},
                    {'code': 'A.8.10', 'name': 'Information deletion', 'evidence': 2},
                    {'code': 'A.8.11', 'name': 'Data masking', 'evidence': 2},
                    {'code': 'A.8.12', 'name': 'Data leakage prevention', 'evidence': 3},
                    {'code': 'A.8.13', 'name': 'Information backup', 'evidence': 3},
                    {'code': 'A.8.14', 'name': 'Redundancy of information processing facilities', 'evidence': 2},
                    {'code': 'A.8.15', 'name': 'Logging', 'evidence': 3},
                    {'code': 'A.8.16', 'name': 'Monitoring activities', 'evidence': 3},
                    {'code': 'A.8.17', 'name': 'Clock synchronization', 'evidence': 1},
                    {'code': 'A.8.18', 'name': 'Use of privileged utility programs', 'evidence': 2},
                    {'code': 'A.8.19', 'name': 'Installation of software on operational systems', 'evidence': 2},
                    {'code': 'A.8.20', 'name': 'Network controls', 'evidence': 3},
                    {'code': 'A.8.21', 'name': 'Security of network services', 'evidence': 2},
                    {'code': 'A.8.22', 'name': 'Segregation of networks', 'evidence': 2},
                    {'code': 'A.8.23', 'name': 'Web filtering', 'evidence': 2},
                    {'code': 'A.8.24', 'name': 'Use of cryptography', 'evidence': 3},
                    {'code': 'A.8.25', 'name': 'Secure development life cycle', 'evidence': 4},
                    {'code': 'A.8.26', 'name': 'Application security requirements', 'evidence': 3},
                    {'code': 'A.8.27', 'name': 'Secure system architecture and engineering principles', 'evidence': 3},
                    {'code': 'A.8.28', 'name': 'Secure coding', 'evidence': 3},
                    {'code': 'A.8.29', 'name': 'Security testing in development and acceptance', 'evidence': 3},
                    {'code': 'A.8.30', 'name': 'Outsourced development', 'evidence': 2},
                    {'code': 'A.8.31', 'name': 'Separation of development, test and production environments', 'evidence': 2},
                    {'code': 'A.8.32', 'name': 'Change management', 'evidence': 3},
                    {'code': 'A.8.33', 'name': 'Test information', 'evidence': 2},
                    {'code': 'A.8.34', 'name': 'Protection of information systems during audit testing', 'evidence': 2},
                ]
            },
        ]
        
        added_cats = 0
        added_ctrls = 0
        
        for cat_data in categories_data:
            # Get or create category
            category, created = ControlCategory.objects.get_or_create(
                framework=framework,
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data.get('description', ''),
                    'order': cat_data.get('order', 0)
                }
            )
            
            if created:
                added_cats += 1
            
            for ctrl_data in cat_data['controls']:
                # Check if control already exists
                if Control.objects.filter(category=category, code=ctrl_data['code']).exists():
                    continue
                
                try:
                    Control.objects.create(
                        category=category,
                        code=ctrl_data['code'],
                        name=ctrl_data['name'],
                        description=f'ISO 27001:2022 control {ctrl_data["code"]}: {ctrl_data["name"]}',
                        status='not_started',
                        priority='medium',
                        required_evidence_count=ctrl_data.get('evidence', 1),
                        created_by=user
                    )
                    added_ctrls += 1
                except Exception as e:
                    self.stdout.write(f'    Error adding control {ctrl_data["code"]}: {e}')
        
        self.stdout.write(self.style.SUCCESS(f'  [OK] Added {added_cats} categories, {added_ctrls} controls'))

    def expand_soc2(self, user):
        """Expand SOC 2 framework with all categories and controls"""
        self.stdout.write('\n[SOC 2] Expanding SOC 2...')
        
        framework = ComplianceFramework.objects.filter(
            name='SOC 2',
            version='2023'
        ).first()
        
        if not framework:
            self.stdout.write(self.style.WARNING('  SOC 2 not found, skipping...'))
            return
        
        existing_cats = ControlCategory.objects.filter(framework=framework).count()
        self.stdout.write(f'  Existing categories: {existing_cats}')
        
        # Expand SOC 2 categories
        categories_data = [
            {
                'code': 'CC1',
                'name': 'Control Environment',
                'description': 'COSO Principle 1-5: Control environment sets the tone of the organization',
                'order': 1,
                'controls': [
                    {'code': 'CC1.6', 'name': 'Establishes performance measures, incentives, and rewards', 'evidence': 2},
                    {'code': 'CC1.7', 'name': 'Evaluates performance and rewards', 'evidence': 2},
                ]
            },
            {
                'code': 'CC2',
                'name': 'Communication and Information',
                'description': 'COSO Principle 13-14: Information and communication support the internal control system',
                'order': 2,
                'controls': [
                    {'code': 'CC2.1', 'name': 'Obtains or generates relevant, quality information', 'evidence': 2},
                    {'code': 'CC2.2', 'name': 'Internally communicates information', 'evidence': 2},
                    {'code': 'CC2.3', 'name': 'Communicates with external parties', 'evidence': 2},
                    {'code': 'CC2.4', 'name': 'Communicates objectives and responsibilities', 'evidence': 2},
                    {'code': 'CC2.5', 'name': 'Communicates internal control matters', 'evidence': 2},
                ]
            },
            {
                'code': 'CC3',
                'name': 'Risk Assessment',
                'description': 'COSO Principle 6-9: Risk assessment process identifies and analyzes risks',
                'order': 3,
                'controls': [
                    {'code': 'CC3.1', 'name': 'Specifies suitable objectives', 'evidence': 2},
                    {'code': 'CC3.2', 'name': 'Identifies and analyzes risk', 'evidence': 3},
                    {'code': 'CC3.3', 'name': 'Assesses fraud risk', 'evidence': 2},
                    {'code': 'CC3.4', 'name': 'Identifies and analyzes significant change', 'evidence': 2},
                    {'code': 'CC3.5', 'name': 'Analyzes business model', 'evidence': 2},
                    {'code': 'CC3.6', 'name': 'Analyzes external environment', 'evidence': 2},
                    {'code': 'CC3.7', 'name': 'Analyzes internal environment', 'evidence': 2},
                ]
            },
            {
                'code': 'CC4',
                'name': 'Monitoring Activities',
                'description': 'COSO Principle 16-17: Ongoing and separate evaluations of internal controls',
                'order': 4,
                'controls': [
                    {'code': 'CC4.1', 'name': 'Conducts ongoing and separate evaluations', 'evidence': 3},
                    {'code': 'CC4.2', 'name': 'Evaluates and communicates deficiencies', 'evidence': 2},
                    {'code': 'CC4.3', 'name': 'Selects, develops, and performs ongoing and separate evaluations', 'evidence': 2},
                    {'code': 'CC4.4', 'name': 'Evaluates deficiencies and communicates deficiencies', 'evidence': 2},
                ]
            },
            {
                'code': 'CC5',
                'name': 'Control Activities',
                'description': 'COSO Principle 10-12: Control activities help ensure management directives are carried out',
                'order': 5,
                'controls': [
                    {'code': 'CC5.1', 'name': 'Selects and develops control activities', 'evidence': 3},
                    {'code': 'CC5.2', 'name': 'Selects and develops general controls over technology', 'evidence': 4},
                    {'code': 'CC5.3', 'name': 'Deploys control activities through policies and procedures', 'evidence': 2},
                    {'code': 'CC5.4', 'name': 'Selects and develops control activities that mitigate risks', 'evidence': 3},
                    {'code': 'CC5.5', 'name': 'Selects and develops general controls over technology to achieve objectives', 'evidence': 4},
                    {'code': 'CC5.6', 'name': 'Deploys control activities through policies and procedures', 'evidence': 2},
                ]
            },
            {
                'code': 'CC6',
                'name': 'Logical and Physical Access Controls',
                'description': 'Controls to restrict access to information assets',
                'order': 6,
                'controls': [
                    {'code': 'CC6.1', 'name': 'Restricts logical access', 'evidence': 5},
                    {'code': 'CC6.2', 'name': 'Identifies and authenticates users', 'evidence': 3},
                    {'code': 'CC6.3', 'name': 'Protects encryption keys', 'evidence': 3},
                    {'code': 'CC6.4', 'name': 'Restricts physical access', 'evidence': 2},
                    {'code': 'CC6.5', 'name': 'Restricts access to information assets', 'evidence': 4},
                    {'code': 'CC6.6', 'name': 'Restricts access to information assets to authorized users', 'evidence': 4},
                    {'code': 'CC6.7', 'name': 'Restricts access to information assets to authorized processes', 'evidence': 3},
                    {'code': 'CC6.8', 'name': 'Restricts access to information assets to authorized devices', 'evidence': 3},
                ]
            },
            {
                'code': 'CC7',
                'name': 'System Operations',
                'description': 'Controls for managing system operations and detecting anomalies',
                'order': 7,
                'controls': [
                    {'code': 'CC7.1', 'name': 'Detects and mitigates processing deviations', 'evidence': 3},
                    {'code': 'CC7.2', 'name': 'Monitors system components', 'evidence': 4},
                    {'code': 'CC7.3', 'name': 'Evaluates security events to identify threats', 'evidence': 3},
                    {'code': 'CC7.4', 'name': 'Responds to security incidents', 'evidence': 4},
                    {'code': 'CC7.5', 'name': 'Detects and mitigates processing deviations', 'evidence': 3},
                    {'code': 'CC7.6', 'name': 'Monitors system components and takes action to maintain compliance', 'evidence': 4},
                    {'code': 'CC7.7', 'name': 'Evaluates security events to identify threats', 'evidence': 3},
                    {'code': 'CC7.8', 'name': 'Responds to security incidents', 'evidence': 4},
                ]
            },
            {
                'code': 'CC8',
                'name': 'Change Management',
                'description': 'Controls for managing changes to infrastructure and software',
                'order': 8,
                'controls': [
                    {'code': 'CC8.1', 'name': 'Authorizes, designs, develops, configures, documents, tests, approves and implements changes', 'evidence': 5},
                    {'code': 'CC8.2', 'name': 'Authorizes changes', 'evidence': 3},
                    {'code': 'CC8.3', 'name': 'Designs changes', 'evidence': 3},
                    {'code': 'CC8.4', 'name': 'Develops changes', 'evidence': 3},
                    {'code': 'CC8.5', 'name': 'Configures changes', 'evidence': 3},
                    {'code': 'CC8.6', 'name': 'Documents changes', 'evidence': 2},
                    {'code': 'CC8.7', 'name': 'Tests changes', 'evidence': 3},
                    {'code': 'CC8.8', 'name': 'Approves changes', 'evidence': 3},
                    {'code': 'CC8.9', 'name': 'Implements changes', 'evidence': 3},
                ]
            },
            {
                'code': 'CC9',
                'name': 'Risk Mitigation',
                'description': 'Controls for identifying and managing risks',
                'order': 9,
                'controls': [
                    {'code': 'CC9.1', 'name': 'Identifies, selects and develops risk mitigation activities', 'evidence': 3},
                    {'code': 'CC9.2', 'name': 'Assesses and manages risks associated with vendors and business partners', 'evidence': 3},
                    {'code': 'CC9.3', 'name': 'Identifies and analyzes risks', 'evidence': 3},
                    {'code': 'CC9.4', 'name': 'Selects and develops risk mitigation activities', 'evidence': 3},
                    {'code': 'CC9.5', 'name': 'Assesses and manages risks associated with vendors', 'evidence': 3},
                    {'code': 'CC9.6', 'name': 'Assesses and manages risks associated with business partners', 'evidence': 3},
                ]
            },
        ]
        
        added_cats = 0
        added_ctrls = 0
        
        for cat_data in categories_data:
            # Get or create category
            category, created = ControlCategory.objects.get_or_create(
                framework=framework,
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data.get('description', ''),
                    'order': cat_data.get('order', 0)
                }
            )
            
            if created:
                added_cats += 1
            
            for ctrl_data in cat_data['controls']:
                # Check if control already exists
                if Control.objects.filter(category=category, code=ctrl_data['code']).exists():
                    continue
                
                try:
                    Control.objects.create(
                        category=category,
                        code=ctrl_data['code'],
                        name=ctrl_data['name'],
                        description=f'SOC 2 control {ctrl_data["code"]}: {ctrl_data["name"]}',
                        status='not_started',
                        priority='medium',
                        required_evidence_count=ctrl_data.get('evidence', 1),
                        created_by=user
                    )
                    added_ctrls += 1
                except Exception as e:
                    self.stdout.write(f'    Error adding control {ctrl_data["code"]}: {e}')
        
        self.stdout.write(self.style.SUCCESS(f'  [OK] Added {added_cats} categories, {added_ctrls} controls'))

