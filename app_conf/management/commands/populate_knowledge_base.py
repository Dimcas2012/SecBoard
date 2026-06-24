"""
Management command to populate Knowledge Base with initial sample articles
Usage: python manage.py populate_knowledge_base
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from app_conf.models import KnowledgeBaseCategory, KnowledgeBaseArticle


class Command(BaseCommand):
    help = 'Populate Knowledge Base with sample articles'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting Knowledge Base population...'))
        
        # Get or create admin user
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No admin user found. Please create a superuser first.'))
            return
        
        # Create categories
        categories_data = [
            {
                'name': 'Security Threats',
                'slug': 'security-threats',
                'category_type': 'threats',
                'icon': 'fa-skull-crossbones',
                'color': 'danger',
                'description': 'Information about various security threats and attack vectors',
                'order': 1
            },
            {
                'name': 'Protection Methods',
                'slug': 'protection-methods',
                'category_type': 'protection',
                'icon': 'fa-shield-alt',
                'color': 'success',
                'description': 'Methods and techniques to protect against security threats',
                'order': 2
            },
            {
                'name': 'Standards & Compliance',
                'slug': 'standards-compliance',
                'category_type': 'standards',
                'icon': 'fa-check-square',
                'color': 'primary',
                'description': 'Security standards and compliance requirements',
                'order': 3
            },
            {
                'name': 'Best Practices',
                'slug': 'best-practices',
                'category_type': 'best_practices',
                'icon': 'fa-star',
                'color': 'warning',
                'description': 'Industry best practices for information security',
                'order': 4
            },
            {
                'name': 'Security Tools',
                'slug': 'security-tools',
                'category_type': 'tools',
                'icon': 'fa-tools',
                'color': 'info',
                'description': 'Overview of security tools and technologies',
                'order': 5
            },
            {
                'name': 'Incident Response',
                'slug': 'incident-response',
                'category_type': 'incidents',
                'icon': 'fa-fire-extinguisher',
                'color': 'secondary',
                'description': 'Incident response procedures and case studies',
                'order': 6
            },
        ]
        
        categories = {}
        for cat_data in categories_data:
            category, created = KnowledgeBaseCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            categories[cat_data['slug']] = category
            status = 'Created' if created else 'Already exists'
            self.stdout.write(f'{status}: {category.name}')
        
        # Sample articles
        articles_data = [
            {
                'title': 'Understanding Phishing Attacks',
                'slug': 'understanding-phishing-attacks',
                'category': categories['security-threats'],
                'article_type': 'threat',
                'priority': 'high',
                'summary': 'Phishing is one of the most common cyber threats. Learn how to identify and protect against phishing attacks.',
                'content': '''
                    <h2>What is Phishing?</h2>
                    <p>Phishing is a type of social engineering attack where attackers attempt to trick users into revealing sensitive information such as passwords, credit card numbers, or personal data.</p>
                    
                    <h3>Common Types of Phishing</h3>
                    <ul>
                        <li><strong>Email Phishing:</strong> Fraudulent emails that appear to come from legitimate sources</li>
                        <li><strong>Spear Phishing:</strong> Targeted attacks aimed at specific individuals or organizations</li>
                        <li><strong>Whaling:</strong> Phishing attacks targeting high-profile individuals like executives</li>
                        <li><strong>Smishing:</strong> Phishing via SMS text messages</li>
                        <li><strong>Vishing:</strong> Voice phishing conducted over phone calls</li>
                    </ul>
                    
                    <h3>How to Identify Phishing</h3>
                    <ul>
                        <li>Check the sender's email address carefully</li>
                        <li>Look for grammatical errors and typos</li>
                        <li>Hover over links to see the actual URL</li>
                        <li>Be suspicious of urgent requests</li>
                        <li>Verify requests through alternate channels</li>
                    </ul>
                    
                    <h3>Protection Measures</h3>
                    <p>Organizations should implement multi-layered defense including employee training, email filtering, and regular phishing simulations using tools like GoPhish.</p>
                ''',
                'tags': 'phishing, social engineering, email security, threats',
                'meta_description': 'Learn about phishing attacks, how to identify them, and protect your organization from this common cyber threat.',
                'meta_keywords': 'phishing, email security, social engineering, cyber threats',
                'is_published': True,
                'is_featured': True,
            },
            {
                'title': 'ISO 27001 Overview',
                'slug': 'iso-27001-overview',
                'category': categories['standards-compliance'],
                'article_type': 'standard',
                'priority': 'medium',
                'summary': 'ISO 27001 is the international standard for information security management. Understand its requirements and benefits.',
                'content': '''
                    <h2>What is ISO 27001?</h2>
                    <p>ISO/IEC 27001 is an international standard for managing information security. It provides a systematic approach to managing sensitive company information.</p>
                    
                    <h3>Key Components</h3>
                    <ul>
                        <li><strong>ISMS:</strong> Information Security Management System</li>
                        <li><strong>Risk Assessment:</strong> Identify and assess information security risks</li>
                        <li><strong>Controls:</strong> Implement appropriate security controls (Annex A)</li>
                        <li><strong>Monitoring:</strong> Continuous monitoring and improvement</li>
                    </ul>
                    
                    <h3>Benefits of ISO 27001</h3>
                    <ul>
                        <li>Systematic approach to information security</li>
                        <li>Internationally recognized certification</li>
                        <li>Competitive advantage</li>
                        <li>Legal and regulatory compliance</li>
                        <li>Customer trust and confidence</li>
                    </ul>
                    
                    <h3>Implementation Process</h3>
                    <ol>
                        <li>Define scope and objectives</li>
                        <li>Conduct risk assessment</li>
                        <li>Design and implement controls</li>
                        <li>Monitor and measure effectiveness</li>
                        <li>Continuous improvement</li>
                    </ol>
                ''',
                'tags': 'ISO 27001, ISMS, compliance, standards, certification',
                'meta_description': 'Comprehensive overview of ISO 27001 standard for information security management.',
                'meta_keywords': 'ISO 27001, ISMS, security standard, compliance',
                'is_published': True,
                'is_featured': True,
            },
            {
                'title': 'Multi-Factor Authentication Best Practices',
                'slug': 'mfa-best-practices',
                'category': categories['best-practices'],
                'article_type': 'guide',
                'priority': 'high',
                'summary': 'Implementing multi-factor authentication (MFA) significantly improves account security. Learn the best practices.',
                'content': '''
                    <h2>Why MFA is Essential</h2>
                    <p>Multi-factor authentication adds an additional layer of security beyond just passwords, making it much harder for attackers to gain unauthorized access.</p>
                    
                    <h3>Types of Authentication Factors</h3>
                    <ul>
                        <li><strong>Something you know:</strong> Password, PIN</li>
                        <li><strong>Something you have:</strong> Phone, hardware token, smart card</li>
                        <li><strong>Something you are:</strong> Fingerprint, facial recognition</li>
                    </ul>
                    
                    <h3>MFA Implementation Best Practices</h3>
                    <ol>
                        <li><strong>Choose appropriate methods:</strong> Select MFA methods suitable for your environment</li>
                        <li><strong>Enforce for all users:</strong> Require MFA for all accounts, especially privileged ones</li>
                        <li><strong>Provide backup options:</strong> Offer multiple MFA methods for redundancy</li>
                        <li><strong>User education:</strong> Train users on MFA usage and benefits</li>
                        <li><strong>Monitor and audit:</strong> Track MFA usage and failures</li>
                    </ol>
                    
                    <h3>Common MFA Solutions</h3>
                    <ul>
                        <li>Google Authenticator / Microsoft Authenticator</li>
                        <li>SMS-based codes (less secure but convenient)</li>
                        <li>Hardware tokens (YubiKey, etc.)</li>
                        <li>Biometric authentication</li>
                        <li>Push notifications</li>
                    </ul>
                ''',
                'tags': 'MFA, authentication, 2FA, security, access control',
                'meta_description': 'Best practices for implementing multi-factor authentication to enhance security.',
                'meta_keywords': 'MFA, multi-factor authentication, 2FA, security best practices',
                'is_published': True,
                'is_featured': True,
            },
            {
                'title': 'Ransomware: Prevention and Response',
                'slug': 'ransomware-prevention-response',
                'category': categories['security-threats'],
                'article_type': 'threat',
                'priority': 'critical',
                'summary': 'Ransomware attacks can cripple organizations. Learn how to prevent attacks and respond effectively if targeted.',
                'content': '''
                    <h2>Understanding Ransomware</h2>
                    <p>Ransomware is malicious software that encrypts files and demands payment for decryption. It's one of the most damaging cyber threats facing organizations today.</p>
                    
                    <h3>Common Attack Vectors</h3>
                    <ul>
                        <li>Phishing emails with malicious attachments</li>
                        <li>Exploit kits targeting software vulnerabilities</li>
                        <li>Remote Desktop Protocol (RDP) attacks</li>
                        <li>Malicious websites and drive-by downloads</li>
                    </ul>
                    
                    <h3>Prevention Strategies</h3>
                    <ol>
                        <li><strong>Regular backups:</strong> Maintain offline, encrypted backups</li>
                        <li><strong>Patch management:</strong> Keep systems and software updated</li>
                        <li><strong>Email filtering:</strong> Block malicious attachments and links</li>
                        <li><strong>Network segmentation:</strong> Limit lateral movement</li>
                        <li><strong>User training:</strong> Educate staff about ransomware risks</li>
                        <li><strong>Endpoint protection:</strong> Deploy anti-malware solutions</li>
                        <li><strong>Access control:</strong> Implement least privilege principle</li>
                    </ol>
                    
                    <h3>Incident Response</h3>
                    <p>If you suspect a ransomware infection:</p>
                    <ol>
                        <li>Isolate affected systems immediately</li>
                        <li>Activate incident response team</li>
                        <li>Document everything</li>
                        <li>Assess the scope and impact</li>
                        <li>Do not pay the ransom (FBI recommendation)</li>
                        <li>Restore from backups if available</li>
                        <li>Report to authorities</li>
                        <li>Conduct post-incident review</li>
                    </ol>
                ''',
                'tags': 'ransomware, malware, cyber attack, incident response, backup',
                'meta_description': 'Comprehensive guide to ransomware prevention and response strategies.',
                'meta_keywords': 'ransomware, malware prevention, cyber attack, incident response',
                'is_published': True,
            },
            {
                'title': 'NIST Cybersecurity Framework Explained',
                'slug': 'nist-cybersecurity-framework',
                'category': categories['standards-compliance'],
                'article_type': 'standard',
                'priority': 'medium',
                'summary': 'The NIST Cybersecurity Framework provides a policy framework of computer security guidance. Learn about its five core functions.',
                'content': '''
                    <h2>NIST Cybersecurity Framework</h2>
                    <p>The NIST (National Institute of Standards and Technology) Cybersecurity Framework is a voluntary framework that provides standards, guidelines, and best practices to manage cybersecurity risk.</p>
                    
                    <h3>Five Core Functions</h3>
                    
                    <h4>1. Identify</h4>
                    <ul>
                        <li>Develop organizational understanding of cybersecurity risk</li>
                        <li>Asset management</li>
                        <li>Business environment</li>
                        <li>Governance and risk assessment</li>
                    </ul>
                    
                    <h4>2. Protect</h4>
                    <ul>
                        <li>Develop and implement safeguards</li>
                        <li>Access control</li>
                        <li>Data security</li>
                        <li>Protective technology</li>
                    </ul>
                    
                    <h4>3. Detect</h4>
                    <ul>
                        <li>Define activities to identify cybersecurity events</li>
                        <li>Anomalies and events detection</li>
                        <li>Security continuous monitoring</li>
                    </ul>
                    
                    <h4>4. Respond</h4>
                    <ul>
                        <li>Develop response planning</li>
                        <li>Communications</li>
                        <li>Analysis and mitigation</li>
                        <li>Improvements</li>
                    </ul>
                    
                    <h4>5. Recover</h4>
                    <ul>
                        <li>Develop recovery planning</li>
                        <li>Improvements based on lessons learned</li>
                        <li>Communications during recovery</li>
                    </ul>
                    
                    <h3>Benefits</h3>
                    <p>The framework is flexible, cost-effective, and can be used by organizations of any size or sector.</p>
                ''',
                'tags': 'NIST, cybersecurity framework, standards, compliance, risk management',
                'meta_description': 'Understanding the NIST Cybersecurity Framework and its five core functions.',
                'meta_keywords': 'NIST, cybersecurity framework, security standards',
                'is_published': True,
            },
            {
                'title': 'Secure Password Management',
                'slug': 'secure-password-management',
                'category': categories['best-practices'],
                'article_type': 'guide',
                'priority': 'high',
                'summary': 'Passwords are the first line of defense. Learn how to create, manage, and protect passwords effectively.',
                'content': '''
                    <h2>Password Security Fundamentals</h2>
                    <p>Despite advances in authentication technology, passwords remain the primary method of access control for most systems.</p>
                    
                    <h3>Strong Password Criteria</h3>
                    <ul>
                        <li>Minimum 12 characters (longer is better)</li>
                        <li>Mix of uppercase and lowercase letters</li>
                        <li>Include numbers and special characters</li>
                        <li>Avoid dictionary words and personal information</li>
                        <li>Unique for each account</li>
                    </ul>
                    
                    <h3>Password Managers</h3>
                    <p>Using a password manager is the best way to handle multiple complex passwords:</p>
                    <ul>
                        <li>Store passwords securely encrypted</li>
                        <li>Generate strong random passwords</li>
                        <li>Auto-fill login forms</li>
                        <li>Sync across devices</li>
                        <li>Popular options: 1Password, LastPass, Bitwarden, KeePass</li>
                    </ul>
                    
                    <h3>Organizational Password Policies</h3>
                    <ol>
                        <li>Enforce minimum complexity requirements</li>
                        <li>Implement password expiration (90-180 days)</li>
                        <li>Prevent password reuse</li>
                        <li>Require MFA for sensitive systems</li>
                        <li>Monitor for compromised credentials</li>
                        <li>Educate users regularly</li>
                    </ol>
                    
                    <h3>What to Avoid</h3>
                    <ul>
                        <li>Writing passwords on sticky notes</li>
                        <li>Sharing passwords via email or chat</li>
                        <li>Using the same password across multiple sites</li>
                        <li>Storing passwords in plain text</li>
                        <li>Using passwords like "Password123!"</li>
                    </ul>
                ''',
                'tags': 'passwords, password manager, authentication, security best practices',
                'meta_description': 'Best practices for creating and managing secure passwords in organizations.',
                'meta_keywords': 'password security, password management, authentication',
                'is_published': True,
            },
            {
                'title': 'Using Wazuh for Security Monitoring',
                'slug': 'wazuh-security-monitoring',
                'category': categories['security-tools'],
                'article_type': 'guide',
                'priority': 'medium',
                'summary': 'Wazuh is a free, open-source security platform for threat detection, integrity monitoring, and incident response.',
                'content': '''
                    <h2>Introduction to Wazuh</h2>
                    <p>Wazuh is a comprehensive open-source security platform that provides unified XDR and SIEM capabilities.</p>
                    
                    <h3>Key Features</h3>
                    <ul>
                        <li><strong>Security Analytics:</strong> Real-time threat detection</li>
                        <li><strong>Intrusion Detection:</strong> Host and network-based IDS</li>
                        <li><strong>Log Data Analysis:</strong> Centralized log management</li>
                        <li><strong>File Integrity Monitoring:</strong> Detect unauthorized changes</li>
                        <li><strong>Vulnerability Detection:</strong> Identify system weaknesses</li>
                        <li><strong>Compliance Management:</strong> PCI DSS, HIPAA, GDPR compliance</li>
                    </ul>
                    
                    <h3>Architecture</h3>
                    <p>Wazuh consists of:</p>
                    <ul>
                        <li><strong>Wazuh Manager:</strong> Central analysis and alerting</li>
                        <li><strong>Wazuh Agent:</strong> Installed on monitored systems</li>
                        <li><strong>Elastic Stack:</strong> Data indexing and visualization</li>
                    </ul>
                    
                    <h3>Integration with SecBoard</h3>
                    <p>SecBoard integrates with Wazuh to provide a unified security operations dashboard. Alerts from Wazuh are automatically imported and can be converted into incidents for tracking and response.</p>
                    
                    <h3>Getting Started</h3>
                    <ol>
                        <li>Install Wazuh manager</li>
                        <li>Deploy agents on endpoints</li>
                        <li>Configure rules and policies</li>
                        <li>Set up alerting</li>
                        <li>Integrate with SecBoard SOC module</li>
                    </ol>
                ''',
                'tags': 'Wazuh, SIEM, security monitoring, threat detection, SOC',
                'meta_description': 'Learn how to use Wazuh for security monitoring and integrate it with SecBoard.',
                'meta_keywords': 'Wazuh, SIEM, security monitoring, threat detection',
                'is_published': True,
            },
            {
                'title': 'Zero Trust Security Model',
                'slug': 'zero-trust-security-model',
                'category': categories['protection-methods'],
                'article_type': 'method',
                'priority': 'high',
                'summary': 'Zero Trust is a security concept centered on the belief that organizations should not automatically trust anything inside or outside their perimeters.',
                'content': '''
                    <h2>What is Zero Trust?</h2>
                    <p>"Never trust, always verify" - this is the core principle of Zero Trust security architecture.</p>
                    
                    <h3>Core Principles</h3>
                    <ul>
                        <li><strong>Verify explicitly:</strong> Always authenticate and authorize based on all available data points</li>
                        <li><strong>Least privilege access:</strong> Limit user access with Just-In-Time and Just-Enough-Access</li>
                        <li><strong>Assume breach:</strong> Minimize blast radius and segment access</li>
                    </ul>
                    
                    <h3>Key Components</h3>
                    <ol>
                        <li><strong>Identity Verification:</strong> Strong authentication for all users and devices</li>
                        <li><strong>Device Security:</strong> Ensure devices meet security standards</li>
                        <li><strong>Network Segmentation:</strong> Divide network into secure zones</li>
                        <li><strong>Application Security:</strong> Protect applications and APIs</li>
                        <li><strong>Data Protection:</strong> Encrypt data at rest and in transit</li>
                        <li><strong>Monitoring:</strong> Continuous visibility and analytics</li>
                    </ol>
                    
                    <h3>Implementation Steps</h3>
                    <ol>
                        <li>Identify your protect surface (critical data, assets, applications, services)</li>
                        <li>Map transaction flows</li>
                        <li>Architect Zero Trust network</li>
                        <li>Create Zero Trust policy</li>
                        <li>Monitor and maintain</li>
                    </ol>
                    
                    <h3>Benefits</h3>
                    <ul>
                        <li>Reduced risk of data breaches</li>
                        <li>Better visibility and control</li>
                        <li>Improved compliance</li>
                        <li>Support for remote work</li>
                    </ul>
                ''',
                'tags': 'zero trust, security architecture, network security, access control',
                'meta_description': 'Understanding Zero Trust security model and implementation strategies.',
                'meta_keywords': 'zero trust, security architecture, network security',
                'is_published': True,
            },
            {
                'title': 'Incident Response Plan Template',
                'slug': 'incident-response-plan',
                'category': categories['incident-response'],
                'article_type': 'guide',
                'priority': 'high',
                'summary': 'Every organization needs an incident response plan. Learn what to include and how to prepare your team.',
                'content': '''
                    <h2>Why You Need an Incident Response Plan</h2>
                    <p>A well-defined incident response plan helps organizations respond quickly and effectively to security incidents, minimizing damage and recovery time.</p>
                    
                    <h3>Six Phases of Incident Response</h3>
                    
                    <h4>1. Preparation</h4>
                    <ul>
                        <li>Establish incident response team</li>
                        <li>Define roles and responsibilities</li>
                        <li>Procure necessary tools and resources</li>
                        <li>Develop communication plans</li>
                    </ul>
                    
                    <h4>2. Identification</h4>
                    <ul>
                        <li>Monitor systems for anomalies</li>
                        <li>Analyze alerts and events</li>
                        <li>Determine if incident has occurred</li>
                        <li>Document initial findings</li>
                    </ul>
                    
                    <h4>3. Containment</h4>
                    <ul>
                        <li>Short-term containment: Isolate affected systems</li>
                        <li>Long-term containment: Implement temporary fixes</li>
                        <li>Preserve evidence</li>
                    </ul>
                    
                    <h4>4. Eradication</h4>
                    <ul>
                        <li>Remove malware and malicious artifacts</li>
                        <li>Close vulnerabilities</li>
                        <li>Strengthen security controls</li>
                    </ul>
                    
                    <h4>5. Recovery</h4>
                    <ul>
                        <li>Restore systems from clean backups</li>
                        <li>Return to normal operations</li>
                        <li>Monitor for signs of re-infection</li>
                    </ul>
                    
                    <h4>6. Lessons Learned</h4>
                    <ul>
                        <li>Conduct post-incident review</li>
                        <li>Document what happened and why</li>
                        <li>Update procedures and controls</li>
                        <li>Train team on improvements</li>
                    </ul>
                    
                    <h3>Using SecBoard for Incident Response</h3>
                    <p>SecBoard's Incident Management module helps you track incidents through all phases, assign responsibilities, and generate reports for stakeholders.</p>
                ''',
                'tags': 'incident response, IR plan, security incident, CSIRT, playbook',
                'meta_description': 'Complete guide to creating and implementing an incident response plan.',
                'meta_keywords': 'incident response plan, security incident, CSIRT',
                'is_published': True,
            },
        ]
        
        created_count = 0
        for article_data in articles_data:
            article, created = KnowledgeBaseArticle.objects.get_or_create(
                slug=article_data['slug'],
                defaults={**article_data, 'author': admin_user, 'published_at': timezone.now()}
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {article.title}'))
            else:
                self.stdout.write(f'  Already exists: {article.title}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} new articles!'))
        self.stdout.write(self.style.SUCCESS(f'Total categories: {KnowledgeBaseCategory.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total articles: {KnowledgeBaseArticle.objects.count()}'))
        self.stdout.write('')
        self.stdout.write('Access Knowledge Base at: /about/knowledge-base/')

