from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.contrib import messages
from .models import MailServer, MailAccount, ContactMessage, SiteSettings, ContactSettings
from .forms import ContactForm

# Create your views here.

def about(request):
    """Public About page with system and modules description"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_about_page:
        raise Http404()

    modules = [
        {
            'name': 'app_study',
            'title': _('Security Awareness Training'),
            'icon': 'fa-graduation-cap',
            'color': 'primary',
            'description': _('Comprehensive security awareness training platform with interactive courses, quizzes, and certification programs. Helps employees understand cybersecurity threats and best practices.'),
            'features': [
                _('Interactive training courses'),
                _('Knowledge assessments and quizzes'),
                _('Certification management'),
                _('Progress tracking and reporting'),
                _('Customizable training materials'),
            ]
        },
        {
            'name': 'app_cabinet',
            'title': _('User Cabinet & Authentication'),
            'icon': 'fa-user-circle',
            'color': 'success',
            'description': _('Secure user management system with advanced authentication, role-based access control, and comprehensive session management.'),
            'features': [
                _('Multi-factor authentication (MFA)'),
                _('Role-based access control (RBAC)'),
                _('Session management and security'),
                _('User profile and preferences'),
                _('Password policies and enforcement'),
            ]
        },
        {
            'name': 'app_doc',
            'title': _('Document Management'),
            'icon': 'fa-file-text',
            'color': 'info',
            'description': _('Advanced document management system for security policies, procedures, and regulatory documentation with version control and approval workflows.'),
            'features': [
                _('Document version control'),
                _('Approval workflows'),
                _('Template management'),
                _('Document lifecycle management'),
                _('Access control and permissions'),
            ]
        },
        {
            'name': 'app_risk',
            'title': _('Risk Assessment & Management'),
            'icon': 'fa-shield',
            'color': 'warning',
            'description': _('Comprehensive risk assessment platform with threat modeling, vulnerability management, and risk treatment planning based on international standards.'),
            'features': [
                _('Risk identification and analysis'),
                _('Threat and vulnerability assessment'),
                _('Risk treatment planning'),
                _('Risk matrix and heat maps'),
                _('Compliance tracking (ISO 27001, NIST)'),
            ]
        },
        {
            'name': 'app_asset',
            'title': _('Asset Management'),
            'icon': 'fa-server',
            'color': 'secondary',
            'description': _('IT asset inventory and management system tracking hardware, software, and information assets with their security classification and ownership.'),
            'features': [
                _('Asset inventory management'),
                _('Asset classification'),
                _('Ownership and responsibility tracking'),
                _('Lifecycle management'),
                _('Integration with other modules'),
            ]
        },
        {
            'name': 'app_keycert',
            'title': _('Key & Certificate Management'),
            'icon': 'fa-key',
            'color': 'danger',
            'description': _('Cryptographic key and digital certificate lifecycle management with expiration tracking and automated renewal notifications.'),
            'features': [
                _('Certificate lifecycle management'),
                _('Expiration monitoring and alerts'),
                _('Renewal workflow automation'),
                _('Key management and storage'),
                _('Integration with PKI systems'),
            ]
        },
        {
            'name': 'app_incident',
            'title': _('Incident Management'),
            'icon': 'fa-exclamation-triangle',
            'color': 'danger',
            'description': _('Security incident response and management system with workflow automation, escalation procedures, and incident reporting capabilities.'),
            'features': [
                _('Incident registration and tracking'),
                _('Workflow automation'),
                _('Escalation procedures'),
                _('Investigation management'),
                _('Reporting and analytics'),
            ]
        },
        {
            'name': 'app_std',
            'title': _('Standards & Compliance'),
            'icon': 'fa-check-square',
            'color': 'success',
            'description': _('Security standards and compliance management framework supporting ISO 27001, NIST, GDPR, and other regulatory requirements.'),
            'features': [
                _('Standards library (ISO 27001, NIST, etc.)'),
                _('Compliance gap analysis'),
                _('Control implementation tracking'),
                _('Audit preparation'),
                _('Compliance reporting'),
            ]
        },
        {
            'name': 'app_compliance',
            'title': _('Framework Compliance'),
            'icon': 'fa-balance-scale',
            'color': 'primary',
            'description': _('Framework-specific compliance management for NIST CSF, CIS Controls, ISO 27001, and other security frameworks with maturity assessments and gap analysis.'),
            'features': [
                _('Multi-framework support (NIST CSF, CIS, ISO 27001)'),
                _('Framework maturity assessments'),
                _('Control mapping and implementation'),
                _('Gap analysis and remediation tracking'),
                _('Compliance dashboards and reporting'),
            ]
        },
        {
            'name': 'app_access',
            'title': _('Access Management'),
            'icon': 'fa-lock',
            'color': 'primary',
            'description': _('Comprehensive access rights management system with request workflows, approval processes, and periodic access reviews.'),
            'features': [
                _('Access request management'),
                _('Approval workflows'),
                _('Periodic access reviews'),
                _('Access matrix management'),
                _('Integration with identity systems'),
            ]
        },
        {
            'name': 'app_soc',
            'title': _('Security Operations Center (SOC)'),
            'icon': 'fa-eye',
            'color': 'dark',
            'description': _('Security monitoring and operations dashboard integrating with SIEM systems, threat intelligence feeds, and security tools for real-time security monitoring.'),
            'features': [
                _('Real-time security monitoring'),
                _('SIEM integration (Wazuh, etc.)'),
                _('Alert management and triage'),
                _('Threat intelligence integration'),
                _('Security dashboards and reporting'),
            ]
        },
        {
            'name': 'app_gophish',
            'title': _('Phishing Simulation (GoPhish)'),
            'icon': 'fa-fish',
            'color': 'warning',
            'description': _('Integrated phishing simulation platform for security awareness testing and training with campaign management and detailed analytics.'),
            'features': [
                _('Phishing campaign management'),
                _('Email template library'),
                _('Landing page builder'),
                _('Detailed analytics and reporting'),
                _('Integration with training platform'),
            ]
        },
        {
            'name': 'app_gdpr',
            'title': _('GDPR Compliance Management'),
            'icon': 'fa-user-shield',
            'color': 'info',
            'description': _('Comprehensive GDPR compliance platform for managing data subjects, consent records, data breach incidents, and data subject requests with built-in workflows and reporting.'),
            'features': [
                _('Data Subject registry and management'),
                _('Consent management and tracking'),
                _('Data Subject Request (DSR) processing'),
                _('Data breach incident management'),
                _('Data Protection Impact Assessment (DPIA)'),
                _('Processing activities documentation'),
                _('Data retention policies'),
                _('Compliance reporting and audit trail'),
            ]
        },
    ]
    
    context = {
        'modules': modules,
        'page_title': _('About SecBoard'),
        'meta_description': _('SecBoard - Comprehensive Information Security Management Platform. Integrated solution for risk management, compliance, incident response, and security operations.'),
        'meta_keywords': _('information security, security management, risk assessment, compliance, ISO 27001, NIST, SOC, incident management'),
    }
    
    return render(request, 'app_conf/about.html', context)


def module_detail(request, module_name):
    """Public page with detailed module information"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_about_page:
        raise Http404()

    # Define detailed information for all modules
    modules_details = {
        'app_study': {
            'name': 'app_study',
            'title': _('Security Awareness Training'),
            'icon': 'fa-graduation-cap',
            'color': 'primary',
            'tagline': _('Empower Your Team with Security Knowledge'),
            'description': _('Transform your organization\'s security culture with our comprehensive Security Awareness Training platform. Built on modern learning management principles, this module helps you educate employees about cybersecurity threats, best practices, and compliance requirements through interactive and engaging content.'),
            'key_benefits': [
                {
                    'icon': 'fa-graduation-cap',
                    'title': _('Interactive Learning'),
                    'description': _('Engaging courses with videos, quizzes, and real-world scenarios that make security training effective and memorable.'),
                },
                {
                    'icon': 'fa-chart-line',
                    'title': _('Progress Tracking'),
                    'description': _('Monitor individual and team progress with detailed analytics, completion rates, and assessment scores.'),
                },
                {
                    'icon': 'fa-certificate',
                    'title': _('Certification Management'),
                    'description': _('Issue and track security awareness certificates, monitor expiration dates, and automate renewal reminders.'),
                },
                {
                    'icon': 'fa-users',
                    'title': _('Team Management'),
                    'description': _('Organize employees into groups, assign tailored training programs, and track compliance by department.'),
                },
            ],
            'features': [
                {
                    'category': _('Course Management'),
                    'items': [
                        _('Create unlimited custom courses and learning paths'),
                        _('Rich content editor supporting text, images, videos, and embedded media'),
                        _('Organize content into modules, lessons, and topics'),
                        _('Set prerequisites and learning sequences'),
                        _('Version control for course materials'),
                        _('Course templates for quick deployment'),
                    ]
                },
                {
                    'category': _('Assessment & Testing'),
                    'items': [
                        _('Multiple question types: multiple choice, true/false, text answers'),
                        _('Randomized question pools for each attempt'),
                        _('Time limits and attempt restrictions'),
                        _('Passing scores and success criteria'),
                        _('Instant feedback and explanations'),
                        _('Certificate generation upon successful completion'),
                    ]
                },
                {
                    'category': _('User Experience'),
                    'items': [
                        _('Mobile-responsive interface for learning on any device'),
                        _('Bookmark and resume functionality'),
                        _('Personal learning dashboard'),
                        _('Progress indicators and completion badges'),
                        _('Multilingual content support'),
                        _('Accessibility features (WCAG compliant)'),
                    ]
                },
                {
                    'category': _('Reporting & Analytics'),
                    'items': [
                        _('Comprehensive completion and participation reports'),
                        _('Individual learner progress tracking'),
                        _('Department and team analytics'),
                        _('Training effectiveness metrics'),
                        _('Compliance status dashboards'),
                        _('Export reports to PDF, Excel, CSV'),
                    ]
                },
                {
                    'category': _('Integration & Automation'),
                    'items': [
                        _('Integration with phishing simulation (GoPhish)'),
                        _('Automatic enrollment based on user roles'),
                        _('Email notifications for assignments and deadlines'),
                        _('Reminder system for incomplete courses'),
                        _('Calendar integration for scheduled training'),
                        _('API access for external integrations'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('New Employee Onboarding'),
                    'description': _('Automatically enroll new hires in mandatory security awareness training as part of their onboarding process. Track completion before granting full system access.'),
                },
                {
                    'title': _('Compliance Training Programs'),
                    'description': _('Meet regulatory requirements (GDPR, HIPAA, PCI DSS) with structured training programs and automated compliance reporting.'),
                },
                {
                    'title': _('Phishing Awareness'),
                    'description': _('Combine with phishing simulations to identify vulnerable users and provide targeted training to improve email security awareness.'),
                },
                {
                    'title': _('Role-Based Training'),
                    'description': _('Deliver specialized training to different roles: developers receive secure coding training, administrators learn about infrastructure security, and executives focus on strategic security topics.'),
                },
                {
                    'title': _('Incident Response'),
                    'description': _('After security incidents, quickly deploy remedial training to affected users and track completion to prevent future occurrences.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built as a Django application with RESTful API support. Uses PostgreSQL for data storage and Celery for background task processing (automated emails, certificate generation).'),
                'security': _('All training data is encrypted at rest. User progress and assessment results are protected with row-level security. Access controls ensure users only see assigned training.'),
                'scalability': _('Supports unlimited users, courses, and concurrent learners. Content is cached for optimal performance. Media files can be served from CDN.'),
                'customization': _('Fully customizable course templates, email notifications, certificate designs, and user interface themes. White-label options available.'),
            },
            'screenshots': [
                {'title': _('Course Catalog'), 'description': _('Browse available training courses')},
                {'title': _('Interactive Lessons'), 'description': _('Engaging learning experience')},
                {'title': _('Quiz Interface'), 'description': _('Test knowledge with assessments')},
                {'title': _('Progress Dashboard'), 'description': _('Track your learning journey')},
                {'title': _('Certificates'), 'description': _('Earn security awareness certificates')},
            ],
            'faq': [
                {
                    'question': _('Can I create my own training content?'),
                    'answer': _('Yes! The platform includes a full-featured course editor where you can create custom training materials, upload videos, create quizzes, and design your own learning paths.'),
                },
                {
                    'question': _('Does it support multiple languages?'),
                    'answer': _('Yes, the platform supports multilingual content. You can create courses in any language, and the interface is available in English, Ukrainian, and Russian by default.'),
                },
                {
                    'question': _('How do I track compliance?'),
                    'answer': _('The platform provides comprehensive compliance dashboards showing who has completed required training, who is overdue, and when certifications expire. You can export reports for auditors.'),
                },
                {
                    'question': _('Can I integrate with our HR system?'),
                    'answer': _('Yes, the platform provides REST APIs for integration with external systems. You can automatically sync users, trigger enrollments, and retrieve completion status.'),
                },
            ],
            'related_modules': [
                {'name': 'app_gophish', 'title': _('Phishing Simulation')},
                {'name': 'app_cabinet', 'title': _('User Cabinet & Authentication')},
                {'name': 'app_access', 'title': _('Access Management')},
            ],
        },
        'app_cabinet': {
            'name': 'app_cabinet',
            'title': _('User Cabinet & Authentication'),
            'icon': 'fa-user-circle',
            'color': 'success',
            'tagline': _('Secure Access Control for Your Organization'),
            'description': _('Comprehensive user management and authentication system providing enterprise-grade security with multi-factor authentication, role-based access control, and advanced session management. Protect your organization with modern security practices and granular permission controls.'),
            'key_benefits': [
                {
                    'icon': 'fa-shield-alt',
                    'title': _('Multi-Factor Authentication'),
                    'description': _('Enhance account security with MFA support including TOTP, SMS, and email verification. Protect against unauthorized access and credential theft.'),
                },
                {
                    'icon': 'fa-users-cog',
                    'title': _('Role-Based Access Control'),
                    'description': _('Implement granular permissions with RBAC. Create custom roles, assign permissions, and control what users can see and do throughout the platform.'),
                },
                {
                    'icon': 'fa-lock',
                    'title': _('Advanced Security'),
                    'description': _('Password policies, session management, brute-force protection, account lockout, and comprehensive audit logging keep your system secure.'),
                },
                {
                    'icon': 'fa-user-check',
                    'title': _('User Self-Service'),
                    'description': _('Empower users with self-service capabilities: password reset, profile management, security settings, and activity monitoring.'),
                },
            ],
            'features': [
                {
                    'category': _('Authentication & Security'),
                    'items': [
                        _('Multi-factor authentication (TOTP, SMS, Email)'),
                        _('Password complexity requirements and policies'),
                        _('Account lockout after failed login attempts'),
                        _('Brute-force attack protection'),
                        _('Session timeout and concurrent session control'),
                        _('IP-based access restrictions'),
                        _('Password expiration and history'),
                        _('Security questions for account recovery'),
                    ]
                },
                {
                    'category': _('User Management'),
                    'items': [
                        _('User registration and approval workflows'),
                        _('Bulk user import/export (CSV, Excel)'),
                        _('User profile management with custom fields'),
                        _('Department and organization hierarchy'),
                        _('User status management (active, inactive, locked)'),
                        _('Email verification and activation'),
                        _('User search and filtering'),
                    ]
                },
                {
                    'category': _('Roles & Permissions'),
                    'items': [
                        _('Role-based access control (RBAC)'),
                        _('Create custom roles with specific permissions'),
                        _('Permission groups for easier management'),
                        _('Module-level and feature-level permissions'),
                        _('Permission inheritance and delegation'),
                        _('Dynamic permission checks'),
                        _('Role templates for common scenarios'),
                    ]
                },
                {
                    'category': _('Session Management'),
                    'items': [
                        _('Active session monitoring and management'),
                        _('Force logout from all devices'),
                        _('Session history and activity log'),
                        _('Device fingerprinting and recognition'),
                        _('Suspicious activity detection'),
                        _('Geographic location tracking'),
                        _('Concurrent session limits'),
                    ]
                },
                {
                    'category': _('Audit & Compliance'),
                    'items': [
                        _('Comprehensive audit logs for all actions'),
                        _('User activity timeline'),
                        _('Login history with IP and location'),
                        _('Permission change tracking'),
                        _('Failed login attempt monitoring'),
                        _('GDPR compliance features (data export, deletion)'),
                        _('Compliance reporting and analytics'),
                    ]
                },
                {
                    'category': _('Integration & API'),
                    'items': [
                        _('LDAP/Active Directory integration'),
                        _('OAuth 2.0 and OpenID Connect support'),
                        _('SAML 2.0 for enterprise SSO'),
                        _('REST API for user management'),
                        _('Webhook notifications for user events'),
                        _('Token-based authentication for API access'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Enterprise User Management'),
                    'description': _('Manage thousands of users across departments with hierarchical organization structure, bulk operations, and automated workflows. Integrate with existing LDAP/AD infrastructure for seamless user provisioning.'),
                },
                {
                    'title': _('Secure Authentication for Critical Systems'),
                    'description': _('Implement MFA for privileged accounts, enforce strong password policies, and monitor suspicious login activities. Protect sensitive data with advanced authentication mechanisms.'),
                },
                {
                    'title': _('Compliance Requirements (GDPR, SOX, HIPAA)'),
                    'description': _('Meet regulatory requirements with comprehensive audit logs, user consent management, data retention policies, and automated compliance reporting. Provide users with data access and deletion capabilities.'),
                },
                {
                    'title': _('Self-Service Portal'),
                    'description': _('Reduce help desk load by allowing users to manage their own profiles, reset passwords, configure MFA, and monitor their account activity. Empower users while maintaining security.'),
                },
                {
                    'title': _('Third-Party Integration'),
                    'description': _('Enable single sign-on (SSO) with external applications using OAuth/SAML. Allow partners and contractors secure access to specific modules without creating separate accounts.'),
                },
                {
                    'title': _('Security Incident Response'),
                    'description': _('Quickly respond to security incidents by reviewing user activity logs, forcing password changes, locking compromised accounts, and terminating active sessions across all devices.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django\'s authentication framework with custom extensions. Uses PostgreSQL for user data storage with encrypted sensitive fields. Redis for session storage and caching. Celery for background tasks like email sending and cleanup jobs.'),
                'security': _('Password hashing with PBKDF2/Argon2. CSRF protection, XSS prevention, SQL injection protection. Rate limiting on authentication endpoints. Security headers (HSTS, CSP, X-Frame-Options). Regular security audits and updates.'),
                'scalability': _('Supports unlimited users with optimized database queries. Connection pooling for database efficiency. Redis clustering for session storage. Horizontal scaling support with load balancers. Caching strategies for performance.'),
                'customization': _('Customizable user fields and profile forms. Configurable password policies and MFA methods. Custom authentication backends. Pluggable permission systems. White-label UI customization.'),
            },
            'screenshots': [
                {'title': _('Login Page'), 'description': _('Secure login with MFA support')},
                {'title': _('User Dashboard'), 'description': _('Personal user cabinet')},
                {'title': _('Profile Settings'), 'description': _('Manage profile and security')},
                {'title': _('Admin User Management'), 'description': _('Manage all users')},
                {'title': _('Role & Permission Management'), 'description': _('Configure RBAC')},
                {'title': _('Session Monitoring'), 'description': _('View active sessions')},
                {'title': _('Audit Logs'), 'description': _('Track all user activities')},
            ],
            'faq': [
                {
                    'question': _('What MFA methods are supported?'),
                    'answer': _('The platform supports multiple MFA methods: TOTP (Time-based One-Time Password) using apps like Google Authenticator or Authy, SMS verification codes, and email verification. Administrators can configure which methods are available and make MFA mandatory for specific roles.'),
                },
                {
                    'question': _('Can we integrate with our existing LDAP/Active Directory?'),
                    'answer': _('Yes! The platform provides native LDAP/Active Directory integration. You can configure LDAP servers, map LDAP attributes to user fields, and enable automatic user synchronization. Users can authenticate using their existing corporate credentials.'),
                },
                {
                    'question': _('How do password policies work?'),
                    'answer': _('Administrators can configure comprehensive password policies including minimum length, complexity requirements (uppercase, lowercase, numbers, special characters), password history (prevent reuse), expiration periods, and account lockout after failed attempts.'),
                },
                {
                    'question': _('Is the platform GDPR compliant?'),
                    'answer': _('Yes, the platform includes GDPR compliance features: user consent management, data access requests, right to be forgotten (data deletion), data portability (export), audit logs for data access, and privacy policy acknowledgment.'),
                },
                {
                    'question': _('Can users manage their own accounts?'),
                    'answer': _('Yes, users have access to a self-service portal where they can update their profiles, change passwords, configure MFA, view their activity history, manage active sessions, and export their personal data.'),
                },
                {
                    'question': _('How does session management work?'),
                    'answer': _('The platform provides advanced session management: configurable timeout periods, concurrent session limits, device fingerprinting, location tracking, and the ability to force logout from all devices. Users can see all active sessions and terminate them individually.'),
                },
            ],
            'related_modules': [
                {'name': 'app_access', 'title': _('Access Management')},
                {'name': 'app_study', 'title': _('Security Awareness Training')},
                {'name': 'app_soc', 'title': _('Security Operations Center')},
            ],
        },
        'app_doc': {
            'name': 'app_doc',
            'title': _('Document Management'),
            'icon': 'fa-file-text',
            'color': 'info',
            'tagline': _('Comprehensive Document Lifecycle Management'),
            'description': _('Advanced document management system for security policies, procedures, and regulatory documentation. Manage your organization\'s critical documents with version control, approval workflows, electronic signatures, and comprehensive access controls. Ensure compliance and maintain document integrity throughout the entire lifecycle.'),
            'key_benefits': [
                {
                    'icon': 'fa-code-branch',
                    'title': _('Version Control'),
                    'description': _('Track every change with comprehensive version history. Compare versions, restore previous revisions, and maintain complete audit trail of all document modifications.'),
                },
                {
                    'icon': 'fa-check-circle',
                    'title': _('Approval Workflows'),
                    'description': _('Streamline document approval with customizable workflows. Route documents through multiple approvers, track status, and automate notifications.'),
                },
                {
                    'icon': 'fa-shield-alt',
                    'title': _('Access Control'),
                    'description': _('Granular permissions for viewing, editing, and approving documents. Control access by roles, departments, or individual users with fine-grained security.'),
                },
                {
                    'icon': 'fa-calendar-check',
                    'title': _('Lifecycle Management'),
                    'description': _('Manage documents from creation to archival. Automated expiration reminders, periodic reviews, and retention policies ensure compliance.'),
                },
            ],
            'features': [
                {
                    'category': _('Document Management'),
                    'items': [
                        _('Centralized document repository'),
                        _('Hierarchical folder structure with categories'),
                        _('Document metadata and custom fields'),
                        _('Full-text search across all documents'),
                        _('Document tagging and classification'),
                        _('Document templates for quick creation'),
                        _('Bulk upload and import'),
                        _('Document preview without downloading'),
                    ]
                },
                {
                    'category': _('Version Control'),
                    'items': [
                        _('Automatic version tracking for all changes'),
                        _('Version comparison (diff view)'),
                        _('Restore previous versions'),
                        _('Version comments and change logs'),
                        _('Check-in/check-out functionality'),
                        _('Concurrent editing protection'),
                        _('Version branching for parallel development'),
                    ]
                },
                {
                    'category': _('Approval Workflows'),
                    'items': [
                        _('Multi-level approval workflows'),
                        _('Parallel and sequential approval paths'),
                        _('Conditional routing based on rules'),
                        _('Automatic notifications to approvers'),
                        _('Approval delegation and escalation'),
                        _('Comments and feedback during approval'),
                        _('Workflow status tracking and reporting'),
                        _('Emergency approval bypass with logging'),
                    ]
                },
                {
                    'category': _('Collaboration & Review'),
                    'items': [
                        _('Document comments and annotations'),
                        _('Review periods and periodic reviews'),
                        _('Collaborative editing with track changes'),
                        _('Document discussions and Q&A'),
                        _('Reviewer assignments and reminders'),
                        _('Review history and compliance tracking'),
                        _('External reviewer access (secure links)'),
                    ]
                },
                {
                    'category': _('Security & Compliance'),
                    'items': [
                        _('Role-based access control (RBAC)'),
                        _('Document-level permissions'),
                        _('Watermarking for sensitive documents'),
                        _('Digital signatures and validation'),
                        _('Encryption at rest and in transit'),
                        _('Audit logs for all document activities'),
                        _('Compliance tracking (ISO 27001, GDPR)'),
                        _('Document retention and disposal policies'),
                    ]
                },
                {
                    'category': _('Notifications & Automation'),
                    'items': [
                        _('Automated expiration reminders'),
                        _('Review due date notifications'),
                        _('Approval request alerts'),
                        _('Document change notifications'),
                        _('Scheduled reports and summaries'),
                        _('Webhook integrations for events'),
                        _('Email digest of activities'),
                    ]
                },
                {
                    'category': _('Reporting & Analytics'),
                    'items': [
                        _('Document inventory reports'),
                        _('Approval workflow analytics'),
                        _('Compliance status dashboards'),
                        _('Document usage statistics'),
                        _('Review completion tracking'),
                        _('Expiration and renewal reports'),
                        _('Export to PDF, Excel, CSV'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Security Policy Management'),
                    'description': _('Centralize all security policies, procedures, and standards. Implement approval workflows for policy changes, track review cycles, and ensure all policies are current and approved. Provide employees easy access to latest policy versions.'),
                },
                {
                    'title': _('ISO 27001 Documentation'),
                    'description': _('Manage mandatory ISO 27001 documentation including policies, procedures, risk assessments, and records. Track document versions, maintain approval records, and demonstrate compliance during audits with comprehensive audit trails.'),
                },
                {
                    'title': _('Standard Operating Procedures (SOPs)'),
                    'description': _('Create, maintain, and distribute operational procedures across departments. Version control ensures teams always work with current procedures. Approval workflows guarantee quality and management oversight.'),
                },
                {
                    'title': _('Contract and Agreement Management'),
                    'description': _('Store and manage contracts, NDAs, and legal agreements. Track expiration dates, renewal periods, and approval status. Secure access controls protect confidential legal documents.'),
                },
                {
                    'title': _('Compliance Documentation'),
                    'description': _('Maintain regulatory compliance documentation for GDPR, HIPAA, SOX, or industry-specific regulations. Automated reminders ensure timely reviews and updates. Audit trails prove compliance during regulatory inspections.'),
                },
                {
                    'title': _('Incident Response Plans'),
                    'description': _('Manage incident response plans, playbooks, and runbooks. Version control tracks improvements after lessons learned. Approval workflows ensure plans are validated by stakeholders before implementation.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built as Django application with document storage in filesystem or cloud (S3, Azure Blob). Uses PostgreSQL for metadata and search index. Celery for background tasks (virus scanning, notifications, cleanup). Redis for caching and job queuing.'),
                'security': _('Document encryption at rest using AES-256. TLS for data in transit. Virus scanning for uploaded files. Content Security Policy (CSP) headers. XSS and CSRF protection. SQL injection prevention. Access logs for compliance.'),
                'scalability': _('Supports unlimited documents and concurrent users. Efficient file storage with deduplication. CDN integration for faster downloads. Database query optimization with indexes. Horizontal scaling with load balancers.'),
                'customization': _('Custom document types and metadata fields. Configurable approval workflows. Customizable document templates. White-label UI. Pluggable storage backends. Custom notification templates. API for integrations.'),
            },
            'screenshots': [
                {'title': _('Document Library'), 'description': _('Browse and search documents')},
                {'title': _('Document Viewer'), 'description': _('View document with metadata')},
                {'title': _('Version History'), 'description': _('Track all changes')},
                {'title': _('Approval Workflow'), 'description': _('Manage approvals')},
                {'title': _('Document Editor'), 'description': _('Edit documents online')},
                {'title': _('Access Permissions'), 'description': _('Configure security')},
                {'title': _('Reports Dashboard'), 'description': _('Analytics and compliance')},
            ],
            'faq': [
                {
                    'question': _('What file formats are supported?'),
                    'answer': _('The system supports all common document formats: PDF, Microsoft Office (Word, Excel, PowerPoint), OpenOffice/LibreOffice formats, text files, images (PNG, JPG, GIF), and more. Preview functionality is available for most formats.'),
                },
                {
                    'question': _('How does version control work?'),
                    'answer': _('Every time a document is modified, a new version is automatically created. The system maintains complete history of all versions with timestamps, author information, and change comments. You can compare any two versions, view differences, and restore previous versions if needed.'),
                },
                {
                    'question': _('Can we customize approval workflows?'),
                    'answer': _('Yes! You can create custom approval workflows with multiple levels, parallel approvers, conditional routing based on document properties, and automatic escalation. Each document type can have its own workflow. Approval rules can be as simple or complex as your organization requires.'),
                },
                {
                    'question': _('How are documents secured?'),
                    'answer': _('Documents are protected with multiple security layers: encryption at rest and in transit, role-based access control, document-level permissions, watermarking for sensitive content, digital signatures, virus scanning, and comprehensive audit logging. You control exactly who can view, edit, or approve each document.'),
                },
                {
                    'question': _('Does it support electronic signatures?'),
                    'answer': _('Yes, the platform supports digital signatures for document approval. Signatures are cryptographically secure and include timestamp and signer identity. Signature validity can be verified at any time. This meets regulatory requirements for electronic signatures.'),
                },
                {
                    'question': _('Can external users access documents?'),
                    'answer': _('Yes, you can generate secure, time-limited links for external reviewers or partners. Links can be password-protected and expire after specified period. External access is logged for audit purposes. No account creation required for external users.'),
                },
                {
                    'question': _('How does document expiration work?'),
                    'answer': _('You can set expiration dates for documents that require periodic review. The system automatically sends reminders before expiration to document owners and reviewers. Reports show expired and soon-to-expire documents. Expired documents can be automatically archived or flagged for review.'),
                },
            ],
            'related_modules': [
                {'name': 'app_std', 'title': _('Standards & Compliance')},
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_incident', 'title': _('Incident Management')},
            ],
        },
        'app_risk': {
            'name': 'app_risk',
            'title': _('Risk Assessment & Management'),
            'icon': 'fa-shield',
            'color': 'warning',
            'tagline': _('Identify, Assess, and Mitigate Security Risks'),
            'description': _('Comprehensive risk assessment platform based on international standards (ISO 27001, NIST). Identify threats and vulnerabilities, assess their impact, implement risk treatment plans, and maintain continuous risk monitoring. Make informed decisions to protect your organization\'s critical assets and ensure compliance with regulatory requirements.'),
            'key_benefits': [
                {
                    'icon': 'fa-search',
                    'title': _('Risk Identification'),
                    'description': _('Systematically identify threats, vulnerabilities, and risks to your information assets using proven methodologies. Build comprehensive risk register with complete context.'),
                },
                {
                    'icon': 'fa-calculator',
                    'title': _('Risk Assessment'),
                    'description': _('Quantify risks using customizable risk matrices. Calculate likelihood and impact based on your criteria. Generate risk heat maps for visual representation.'),
                },
                {
                    'icon': 'fa-tasks',
                    'title': _('Risk Treatment'),
                    'description': _('Develop and track risk treatment plans. Choose between accept, mitigate, transfer, or avoid strategies. Monitor implementation progress and effectiveness.'),
                },
                {
                    'icon': 'fa-chart-line',
                    'title': _('Continuous Monitoring'),
                    'description': _('Track risk levels over time. Set up automated alerts for risk threshold breaches. Periodic risk reviews ensure your risk landscape stays current.'),
                },
            ],
            'features': [
                {
                    'category': _('Risk Identification'),
                    'items': [
                        _('Asset-based risk assessment'),
                        _('Threat and vulnerability catalogues'),
                        _('Risk scenarios and impact analysis'),
                        _('Threat actor modeling'),
                        _('Attack vector identification'),
                        _('Business impact analysis (BIA)'),
                        _('Risk dependencies and relationships'),
                        _('Import risks from templates'),
                    ]
                },
                {
                    'category': _('Risk Assessment Methodologies'),
                    'items': [
                        _('ISO 27001/27005 methodology'),
                        _('NIST Cybersecurity Framework'),
                        _('OCTAVE methodology support'),
                        _('FAIR (Factor Analysis of Information Risk)'),
                        _('Custom assessment frameworks'),
                        _('Qualitative and quantitative assessment'),
                        _('Multi-criteria risk scoring'),
                    ]
                },
                {
                    'category': _('Risk Matrix & Scoring'),
                    'items': [
                        _('Customizable risk matrices (3x3, 5x5, etc.)'),
                        _('Define likelihood and impact scales'),
                        _('Risk appetite and tolerance levels'),
                        _('Inherent vs residual risk calculation'),
                        _('Risk scoring formulas'),
                        _('Risk heat maps and visualizations'),
                        _('Risk level categorization (Critical, High, Medium, Low)'),
                        _('Weighted scoring for multiple factors'),
                    ]
                },
                {
                    'category': _('Risk Treatment'),
                    'items': [
                        _('Risk treatment plan creation'),
                        _('Treatment strategies (Accept, Mitigate, Transfer, Avoid)'),
                        _('Control implementation tracking'),
                        _('Cost-benefit analysis for controls'),
                        _('Treatment effectiveness monitoring'),
                        _('Action item assignments and deadlines'),
                        _('Progress tracking and status updates'),
                        _('Approval workflows for treatments'),
                    ]
                },
                {
                    'category': _('Threat & Vulnerability Management'),
                    'items': [
                        _('Threat intelligence integration'),
                        _('Vulnerability database and tracking'),
                        _('CVE (Common Vulnerabilities and Exposures) integration'),
                        _('Threat landscape monitoring'),
                        _('Attack surface analysis'),
                        _('Security control mapping'),
                        _('Penetration testing results integration'),
                    ]
                },
                {
                    'category': _('Compliance & Standards'),
                    'items': [
                        _('ISO 27001 risk assessment templates'),
                        _('NIST CSF alignment'),
                        _('GDPR risk assessment'),
                        _('PCI DSS compliance tracking'),
                        _('HIPAA security risk analysis'),
                        _('SOX IT controls risk assessment'),
                        _('Industry-specific compliance frameworks'),
                        _('Gap analysis and remediation tracking'),
                    ]
                },
                {
                    'category': _('Reporting & Analytics'),
                    'items': [
                        _('Executive risk dashboards'),
                        _('Risk register reports'),
                        _('Risk trend analysis over time'),
                        _('Top risks and critical findings'),
                        _('Treatment plan status reports'),
                        _('Compliance status reports'),
                        _('Risk by asset, department, or category'),
                        _('Export to PDF, Excel, CSV'),
                        _('Customizable report templates'),
                    ]
                },
                {
                    'category': _('Collaboration & Workflow'),
                    'items': [
                        _('Risk owner assignments'),
                        _('Collaborative risk assessment sessions'),
                        _('Comments and discussions on risks'),
                        _('Risk review and approval workflows'),
                        _('Notifications and reminders'),
                        _('Audit trail for all changes'),
                        _('Risk committee management'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('ISO 27001 Risk Assessment'),
                    'description': _('Conduct mandatory risk assessment for ISO 27001 certification. Use pre-built templates aligned with ISO 27001/27005 methodology. Document threats, vulnerabilities, and controls. Generate reports for auditors demonstrating systematic risk management process.'),
                },
                {
                    'title': _('Business Impact Analysis (BIA)'),
                    'description': _('Assess potential impact of security incidents on business operations. Identify critical assets and processes. Calculate financial, operational, and reputational impacts. Prioritize security investments based on business criticality.'),
                },
                {
                    'title': _('Third-Party Risk Assessment'),
                    'description': _('Evaluate security risks posed by vendors, suppliers, and partners. Assess third-party security posture. Track vendor risk over time. Ensure supply chain security and compliance with contracts and regulations.'),
                },
                {
                    'title': _('Cloud Migration Risk Assessment'),
                    'description': _('Identify and assess risks before migrating systems to cloud. Evaluate cloud provider security controls. Assess data residency and compliance risks. Develop risk treatment plans for secure cloud adoption.'),
                },
                {
                    'title': _('Regulatory Compliance Risk Management'),
                    'description': _('Assess compliance risks for GDPR, HIPAA, PCI DSS, SOX and other regulations. Identify gaps in compliance controls. Track remediation efforts. Demonstrate compliance to regulators and auditors.'),
                },
                {
                    'title': _('Continuous Risk Monitoring'),
                    'description': _('Implement ongoing risk monitoring program. Automatically reassess risks when threats or assets change. Receive alerts when risk thresholds are exceeded. Maintain current risk landscape with periodic reviews.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django with PostgreSQL database for risk data. Uses Celery for scheduled risk reviews and notifications. Redis for caching risk calculations. RESTful API for integrations with vulnerability scanners and threat intelligence feeds. D3.js for interactive risk visualizations.'),
                'security': _('All risk data encrypted at rest. Role-based access control for sensitive risk information. Audit logging for all risk assessment activities. Data isolation between organizations. Secure API endpoints with authentication. Regular backups and disaster recovery procedures.'),
                'scalability': _('Handles thousands of risks and assets. Optimized database queries with indexes. Lazy loading for large risk registers. Background processing for calculations. Horizontal scaling support. CDN for static assets.'),
                'customization': _('Custom risk matrices and scoring models. Configurable likelihood/impact scales. Custom fields for risks and assets. Pluggable assessment methodologies. White-label branding. Custom report templates. API for integrations with existing tools.'),
            },
            'screenshots': [
                {'title': _('Risk Dashboard'), 'description': _('Overview of risk landscape')},
                {'title': _('Risk Register'), 'description': _('Complete list of identified risks')},
                {'title': _('Risk Heat Map'), 'description': _('Visual risk matrix')},
                {'title': _('Risk Assessment'), 'description': _('Assess individual risk')},
                {'title': _('Treatment Plans'), 'description': _('Risk mitigation strategies')},
                {'title': _('Risk Trends'), 'description': _('Risk over time analytics')},
                {'title': _('Compliance Reports'), 'description': _('ISO 27001, NIST reports')},
            ],
            'faq': [
                {
                    'question': _('What risk assessment methodologies are supported?'),
                    'answer': _('The platform supports multiple methodologies: ISO 27001/27005 for information security risk management, NIST Cybersecurity Framework, OCTAVE for operational risk, and FAIR for quantitative analysis. You can also create custom methodologies tailored to your organization\'s needs.'),
                },
                {
                    'question': _('How do I calculate risk scores?'),
                    'answer': _('Risk scores are calculated based on likelihood and impact using your customizable risk matrix. You define scales (e.g., 1-5) for both factors. The system multiplies or applies custom formulas to generate risk scores. You can set risk appetite thresholds to categorize risks as Critical, High, Medium, or Low.'),
                },
                {
                    'question': _('Can I customize the risk matrix?'),
                    'answer': _('Yes! You have complete control over risk matrix dimensions (3x3, 4x4, 5x5, or custom), likelihood and impact scales, scoring formulas, risk level thresholds, and color coding. Different matrices can be used for different types of assessments.'),
                },
                {
                    'question': _('How does risk treatment tracking work?'),
                    'answer': _('For each identified risk, you create treatment plans specifying strategy (accept, mitigate, transfer, avoid), assigned controls, responsible owners, deadlines, and budgets. The system tracks implementation progress, recalculates residual risk after controls, and monitors effectiveness through periodic reviews.'),
                },
                {
                    'question': _('Does it integrate with vulnerability scanners?'),
                    'answer': _('Yes, the platform can integrate with vulnerability scanners via API. Import vulnerabilities automatically, link them to assets and risks, track CVE identifiers, and monitor remediation status. Supports integration with popular tools like Nessus, Qualys, and OpenVAS.'),
                },
                {
                    'question': _('How often should risks be reviewed?'),
                    'answer': _('Review frequency depends on your risk management policy. The system supports configurable review periods (monthly, quarterly, annually). Automated reminders notify risk owners before reviews are due. You can also trigger ad-hoc reviews when significant changes occur.'),
                },
                {
                    'question': _('Can I generate compliance reports?'),
                    'answer': _('Yes, the platform includes pre-built report templates for ISO 27001, NIST CSF, GDPR, PCI DSS, HIPAA, and other frameworks. Reports show risk assessment methodology, identified risks, treatment plans, and compliance status. All reports are audit-ready and can be exported to PDF or Excel.'),
                },
            ],
            'related_modules': [
                {'name': 'app_std', 'title': _('Standards & Compliance')},
                {'name': 'app_asset', 'title': _('Asset Management')},
                {'name': 'app_incident', 'title': _('Incident Management')},
            ],
        },
        'app_asset': {
            'name': 'app_asset',
            'title': _('Asset Management'),
            'icon': 'fa-server',
            'color': 'secondary',
            'tagline': _('Complete IT Asset Inventory and Lifecycle Management'),
            'description': _('Comprehensive IT asset inventory and management system for tracking hardware, software, and information assets throughout their lifecycle. Maintain accurate asset registers, track ownership and location, manage asset relationships, and ensure security classification compliance. Essential foundation for risk assessment and security management.'),
            'key_benefits': [
                {
                    'icon': 'fa-list-alt',
                    'title': _('Complete Inventory'),
                    'description': _('Maintain comprehensive inventory of all IT assets including hardware, software, data, and services. Track detailed attributes, configurations, and relationships.'),
                },
                {
                    'icon': 'fa-users',
                    'title': _('Ownership & Accountability'),
                    'description': _('Assign clear ownership and responsibility for each asset. Track asset custodians, users, and responsible parties. Ensure accountability throughout the organization.'),
                },
                {
                    'icon': 'fa-tag',
                    'title': _('Classification & Security'),
                    'description': _('Classify assets by criticality and security level. Define confidentiality, integrity, and availability requirements. Link assets to risks and controls.'),
                },
                {
                    'icon': 'fa-sync',
                    'title': _('Lifecycle Management'),
                    'description': _('Track assets from acquisition to disposal. Monitor warranty periods, maintenance schedules, and depreciation. Plan replacements and upgrades proactively.'),
                },
            ],
            'features': [
                {
                    'category': _('Asset Inventory'),
                    'items': [
                        _('Hardware asset tracking (servers, workstations, mobile devices)'),
                        _('Software and license management'),
                        _('Data and information asset catalog'),
                        _('Cloud services and subscriptions'),
                        _('Network infrastructure and devices'),
                        _('Custom asset types and categories'),
                        _('Asset tagging and barcoding'),
                        _('Bulk import from CSV/Excel'),
                    ]
                },
                {
                    'category': _('Asset Attributes'),
                    'items': [
                        _('Detailed technical specifications'),
                        _('Serial numbers and identifiers'),
                        _('Purchase information and costs'),
                        _('Warranty and support contracts'),
                        _('Location and physical placement'),
                        _('Network information (IP, MAC addresses)'),
                        _('Custom fields and metadata'),
                        _('Asset photos and documentation'),
                    ]
                },
                {
                    'category': _('Ownership & Organization'),
                    'items': [
                        _('Asset owner assignments'),
                        _('Custodian and user tracking'),
                        _('Department and team allocation'),
                        _('Business unit associations'),
                        _('Responsibility matrix (RACI)'),
                        _('Contact information management'),
                        _('Delegation and transfer workflows'),
                    ]
                },
                {
                    'category': _('Classification & Security'),
                    'items': [
                        _('Asset criticality levels (Critical, High, Medium, Low)'),
                        _('CIA (Confidentiality, Integrity, Availability) ratings'),
                        _('Security classification labels'),
                        _('Compliance requirements tracking'),
                        _('Risk linkage and exposure'),
                        _('Security control assignments'),
                        _('Data protection requirements'),
                        _('Regulatory compliance tags'),
                    ]
                },
                {
                    'category': _('Lifecycle Management'),
                    'items': [
                        _('Asset lifecycle stages (Planning, Acquisition, Deployment, Operation, Disposal)'),
                        _('Procurement and acquisition tracking'),
                        _('Deployment and commissioning'),
                        _('Maintenance schedules and history'),
                        _('Warranty expiration alerts'),
                        _('Depreciation calculation'),
                        _('End-of-life planning'),
                        _('Secure disposal and decommissioning'),
                    ]
                },
                {
                    'category': _('Relationships & Dependencies'),
                    'items': [
                        _('Asset relationships and dependencies'),
                        _('Parent-child hierarchies'),
                        _('Application-to-infrastructure mapping'),
                        _('Service dependencies'),
                        _('Data flow documentation'),
                        _('Integration points'),
                        _('Impact analysis for changes'),
                    ]
                },
                {
                    'category': _('Software & License Management'),
                    'items': [
                        _('Software inventory and versions'),
                        _('License tracking and compliance'),
                        _('License expiration alerts'),
                        _('Usage monitoring'),
                        _('Cost optimization recommendations'),
                        _('Vendor and supplier management'),
                        _('Subscription renewals'),
                    ]
                },
                {
                    'category': _('Integration & Automation'),
                    'items': [
                        _('Active Directory integration'),
                        _('Network discovery tools integration'),
                        _('CMDB (Configuration Management Database) sync'),
                        _('Automated asset discovery'),
                        _('API for external integrations'),
                        _('Scheduled inventory updates'),
                        _('Notification and alerting'),
                    ]
                },
                {
                    'category': _('Reporting & Analytics'),
                    'items': [
                        _('Asset inventory reports'),
                        _('Cost and financial reports'),
                        _('Compliance status dashboards'),
                        _('Asset utilization analytics'),
                        _('Warranty and maintenance reports'),
                        _('Security classification overview'),
                        _('Custom report builder'),
                        _('Export to PDF, Excel, CSV'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('ISO 27001 Asset Management'),
                    'description': _('Maintain mandatory asset inventory for ISO 27001 compliance. Document all information assets with owners, classification, and locations. Link assets to risks and controls. Generate asset register for auditors.'),
                },
                {
                    'title': _('IT Asset Lifecycle Management'),
                    'description': _('Track IT assets from purchase to disposal. Monitor warranties, maintenance contracts, and depreciation. Plan timely replacements. Optimize asset utilization and reduce costs.'),
                },
                {
                    'title': _('Software License Compliance'),
                    'description': _('Maintain accurate software inventory to ensure license compliance. Track installations against purchased licenses. Receive alerts before license expiration. Avoid penalties from software audits.'),
                },
                {
                    'title': _('Security Risk Assessment'),
                    'description': _('Use asset inventory as foundation for risk assessment. Classify assets by criticality and security requirements. Identify threats to specific assets. Implement appropriate security controls based on asset value.'),
                },
                {
                    'title': _('Incident Response'),
                    'description': _('Quickly identify affected assets during security incidents. Access asset details, owners, and dependencies. Understand impact scope. Coordinate response with asset owners and business units.'),
                },
                {
                    'title': _('IT Service Management (ITSM)'),
                    'description': _('Integrate asset management with ITSM processes. Link assets to incidents, changes, and problems. Track asset history and maintenance. Improve service delivery with accurate asset information.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django framework with PostgreSQL database for asset data. Celery for scheduled tasks (discovery, notifications, updates). Redis for caching and job queuing. RESTful API for integrations with discovery tools, CMDB, and monitoring systems. Support for large-scale deployments.'),
                'security': _('Asset data encrypted at rest. Fine-grained access control for sensitive assets. Audit logging for all asset changes. Data masking for confidential information. Secure API with authentication. Role-based permissions for viewing and editing assets.'),
                'scalability': _('Designed for organizations of any size. Handles tens of thousands of assets efficiently. Optimized database queries with indexes. Pagination for large asset lists. Background processing for bulk operations. Horizontal scaling support.'),
                'customization': _('Custom asset types and categories. Configurable asset fields and attributes. Custom classification schemes. Flexible tagging system. Customizable workflows for asset lifecycle. White-label branding. API for custom integrations.'),
            },
            'screenshots': [
                {'title': _('Asset Dashboard'), 'description': _('Overview of asset inventory')},
                {'title': _('Asset List'), 'description': _('Browse and filter assets')},
                {'title': _('Asset Details'), 'description': _('Complete asset information')},
                {'title': _('Asset Relationships'), 'description': _('Dependencies and connections')},
                {'title': _('License Management'), 'description': _('Software licenses tracking')},
                {'title': _('Asset Reports'), 'description': _('Analytics and compliance')},
            ],
            'faq': [
                {
                    'question': _('What types of assets can be tracked?'),
                    'answer': _('The system supports all types of IT assets: hardware (servers, workstations, laptops, mobile devices, network equipment), software (applications, licenses, subscriptions), data and information assets, cloud services, and physical infrastructure. You can create custom asset types for your specific needs.'),
                },
                {
                    'question': _('How do I classify assets?'),
                    'answer': _('Assets are classified using multiple dimensions: criticality level (Critical, High, Medium, Low), CIA ratings (Confidentiality, Integrity, Availability on scales), security labels, and regulatory requirements. Classification helps prioritize security efforts and link assets to appropriate controls.'),
                },
                {
                    'question': _('Can it discover assets automatically?'),
                    'answer': _('Yes, the platform can integrate with network discovery tools, Active Directory, and CMDB systems to automatically discover and import assets. Scheduled synchronization keeps the inventory up-to-date. You can also manually add assets or bulk import from CSV/Excel files.'),
                },
                {
                    'question': _('How does asset lifecycle management work?'),
                    'answer': _('Assets move through defined lifecycle stages: Planning → Acquisition → Deployment → Operation → Disposal. The system tracks status at each stage, monitors warranties and maintenance, calculates depreciation, sends expiration alerts, and manages secure disposal procedures.'),
                },
                {
                    'question': _('Can I track software licenses?'),
                    'answer': _('Yes, comprehensive software license management is included. Track purchased licenses, installations, usage, costs, and expiration dates. Receive alerts before licenses expire. Compare installations against licenses to ensure compliance and avoid audit penalties.'),
                },
                {
                    'question': _('How are asset relationships tracked?'),
                    'answer': _('Assets can be linked to show dependencies and relationships: applications running on servers, data stored on systems, services depending on infrastructure. Hierarchies show parent-child relationships. Impact analysis helps understand consequences of changes or incidents.'),
                },
            ],
            'related_modules': [
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_incident', 'title': _('Incident Management')},
                {'name': 'app_std', 'title': _('Standards & Compliance')},
            ],
        },
        'app_keycert': {
            'name': 'app_keycert',
            'title': _('Key & Certificate Management'),
            'icon': 'fa-key',
            'color': 'danger',
            'tagline': _('Secure Cryptographic Key and Digital Certificate Lifecycle Management'),
            'description': _('Comprehensive cryptographic key and digital certificate management system. Track SSL/TLS certificates, code signing certificates, encryption keys, and PKI infrastructure. Monitor expiration dates, automate renewal workflows, and prevent security incidents caused by expired certificates. Ensure compliance with cryptographic standards and maintain chain of trust.'),
            'key_benefits': [
                {
                    'icon': 'fa-certificate',
                    'title': _('Certificate Lifecycle'),
                    'description': _('Manage complete certificate lifecycle from issuance to revocation. Track expiration dates, renewal schedules, and certificate chains. Automate notifications and prevent outages from expired certificates.'),
                },
                {
                    'icon': 'fa-bell',
                    'title': _('Expiration Alerts'),
                    'description': _('Automated alerts for upcoming expirations. Multiple notification channels (email, SMS, webhooks). Configurable alert thresholds. Ensure timely renewals and prevent service disruptions.'),
                },
                {
                    'icon': 'fa-shield-alt',
                    'title': _('PKI Management'),
                    'description': _('Manage your Public Key Infrastructure. Track Certificate Authorities, intermediate certificates, and trust chains. Monitor certificate health and compliance with security policies.'),
                },
                {
                    'icon': 'fa-sync-alt',
                    'title': _('Automated Renewal'),
                    'description': _('Integrate with ACME protocol (Let\'s Encrypt) and certificate providers for automated renewal. Approval workflows for manual renewals. Track renewal history and status.'),
                },
            ],
            'features': [
                {
                    'category': _('Certificate Management'),
                    'items': [
                        _('SSL/TLS certificate tracking'),
                        _('Code signing certificates'),
                        _('Email certificates (S/MIME)'),
                        _('Client authentication certificates'),
                        _('Wildcard and multi-domain (SAN) certificates'),
                        _('Self-signed certificate tracking'),
                        _('Certificate import from files or discovery'),
                        _('Certificate metadata and attributes'),
                    ]
                },
                {
                    'category': _('Expiration Monitoring'),
                    'items': [
                        _('Real-time expiration tracking'),
                        _('Configurable alert thresholds (90, 60, 30, 7 days)'),
                        _('Multiple notification channels (email, SMS, Slack, webhooks)'),
                        _('Escalation for critical certificates'),
                        _('Bulk expiration reports'),
                        _('Dashboard with expiration overview'),
                        _('Calendar view of upcoming expirations'),
                    ]
                },
                {
                    'category': _('PKI & Trust Chain'),
                    'items': [
                        _('Certificate Authority (CA) management'),
                        _('Intermediate certificate tracking'),
                        _('Root certificate inventory'),
                        _('Trust chain validation'),
                        _('Certificate revocation list (CRL) monitoring'),
                        _('OCSP (Online Certificate Status Protocol) checking'),
                        _('Certificate path building'),
                    ]
                },
                {
                    'category': _('Certificate Discovery'),
                    'items': [
                        _('Automated certificate discovery from networks'),
                        _('Website SSL certificate scanning'),
                        _('Server certificate inventory'),
                        _('Load balancer certificate tracking'),
                        _('Cloud provider integration (AWS, Azure, GCP)'),
                        _('Kubernetes certificate discovery'),
                        _('API endpoints for custom discovery'),
                    ]
                },
                {
                    'category': _('Renewal Management'),
                    'items': [
                        _('Renewal workflow and approval process'),
                        _('ACME protocol integration (Let\'s Encrypt, ZeroSSL)'),
                        _('Manual renewal tracking'),
                        _('Certificate Signing Request (CSR) generation'),
                        _('Private key management'),
                        _('Renewal history and audit trail'),
                        _('Automatic deployment after renewal'),
                    ]
                },
                {
                    'category': _('Key Management'),
                    'items': [
                        _('Cryptographic key inventory'),
                        _('Key usage tracking'),
                        _('Key rotation policies'),
                        _('Hardware Security Module (HSM) integration'),
                        _('Key escrow and recovery'),
                        _('Key strength validation'),
                        _('Key generation and storage'),
                    ]
                },
                {
                    'category': _('Compliance & Security'),
                    'items': [
                        _('Weak algorithm detection (MD5, SHA-1)'),
                        _('Key length validation (2048-bit minimum)'),
                        _('Certificate policy compliance'),
                        _('PCI DSS compliance tracking'),
                        _('Certificate transparency logging'),
                        _('Security best practices validation'),
                        _('Audit logs for all operations'),
                    ]
                },
                {
                    'category': _('Integration & Automation'),
                    'items': [
                        _('REST API for certificate operations'),
                        _('Webhook notifications for events'),
                        _('Integration with monitoring systems'),
                        _('CI/CD pipeline integration'),
                        _('Infrastructure as Code (IaC) support'),
                        _('Certificate deployment automation'),
                        _('Third-party CA integration'),
                    ]
                },
                {
                    'category': _('Reporting & Analytics'),
                    'items': [
                        _('Certificate inventory reports'),
                        _('Expiration forecasting'),
                        _('Renewal status tracking'),
                        _('Compliance dashboards'),
                        _('Cost analysis and optimization'),
                        _('Security posture reports'),
                        _('Export to PDF, Excel, CSV'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Prevent Certificate Expiration Outages'),
                    'description': _('Avoid service disruptions from expired SSL certificates. Automated monitoring alerts teams weeks before expiration. Track renewals across multiple domains and subdomains. Prevent revenue loss and reputation damage from website downtime.'),
                },
                {
                    'title': _('Enterprise PKI Management'),
                    'description': _('Manage internal Certificate Authority and issued certificates. Track employee certificates for VPN, email, and authentication. Monitor certificate lifecycle in Active Directory. Ensure compliance with corporate PKI policies.'),
                },
                {
                    'title': _('PCI DSS Compliance'),
                    'description': _('Meet PCI DSS requirements for certificate and key management. Document certificate inventory, expiration dates, and renewal processes. Validate strong encryption algorithms. Generate compliance reports for auditors.'),
                },
                {
                    'title': _('Cloud Infrastructure Security'),
                    'description': _('Track certificates across cloud providers (AWS Certificate Manager, Azure Key Vault, GCP Certificate Authority). Monitor load balancers, CDNs, and API gateways. Automate certificate deployment in cloud environments.'),
                },
                {
                    'title': _('DevOps & Microservices'),
                    'description': _('Manage certificates in containerized environments. Track Kubernetes secrets and TLS certificates. Integrate with CI/CD pipelines. Automate certificate rotation for microservices communication.'),
                },
                {
                    'title': _('Code Signing & Software Distribution'),
                    'description': _('Track code signing certificates for software releases. Monitor certificate validity for signed applications. Manage developer certificates. Ensure continuous signing capability for software distribution.'),
                },
            ],
            'technical_details': {
                'architecture': _('Django-based application with PostgreSQL for certificate metadata storage. Celery for scheduled certificate scanning and expiration checks. Redis for caching certificate status. Integration with OpenSSL for certificate parsing and validation. Support for ACME protocol (RFC 8555) for automated renewals.'),
                'security': _('Private keys never stored in database. Integration with HSM for key operations. Certificate data encrypted at rest. Secure API with OAuth 2.0 authentication. Audit logging for all certificate operations. Role-based access control for sensitive operations. Support for air-gapped environments.'),
                'scalability': _('Handles thousands of certificates efficiently. Distributed certificate scanning with worker nodes. Efficient certificate parsing and validation. Optimized database queries with indexes. Horizontal scaling for high-volume environments. Rate limiting for external API calls.'),
                'customization': _('Custom certificate types and categories. Configurable alert thresholds and schedules. Custom notification templates. Flexible integration with certificate providers. Pluggable certificate discovery modules. White-label branding. Custom fields for certificates.'),
            },
            'screenshots': [
                {'title': _('Certificate Dashboard'), 'description': _('Overview of all certificates')},
                {'title': _('Expiration Timeline'), 'description': _('Upcoming expirations calendar')},
                {'title': _('Certificate Details'), 'description': _('Complete certificate information')},
                {'title': _('Trust Chain View'), 'description': _('Certificate hierarchy')},
                {'title': _('Renewal Workflow'), 'description': _('Manage renewals')},
                {'title': _('Compliance Reports'), 'description': _('Security and compliance status')},
            ],
            'faq': [
                {
                    'question': _('What types of certificates can be managed?'),
                    'answer': _('The system supports all types of X.509 certificates: SSL/TLS certificates for websites and APIs, code signing certificates for software, email certificates (S/MIME), client authentication certificates, VPN certificates, and custom certificate types. Both publicly trusted and internal/self-signed certificates can be tracked.'),
                },
                {
                    'question': _('How does expiration monitoring work?'),
                    'answer': _('The system continuously monitors certificate expiration dates and sends automated alerts at configurable thresholds (typically 90, 60, 30, and 7 days before expiration). Alerts are sent via email, SMS, Slack, or webhooks. Critical certificates can have escalation policies for faster response.'),
                },
                {
                    'question': _('Can it automatically renew certificates?'),
                    'answer': _('Yes, for certificates from ACME-compatible providers (Let\'s Encrypt, ZeroSSL), the system can fully automate renewal using the ACME protocol. For other providers, it provides workflow management for manual renewals with approval processes and status tracking. Post-renewal deployment can also be automated.'),
                },
                {
                    'question': _('How does certificate discovery work?'),
                    'answer': _('The system can discover certificates through multiple methods: scanning network ranges for SSL/TLS endpoints, integrating with cloud providers (AWS, Azure, GCP), connecting to web servers, monitoring load balancers, and discovering Kubernetes secrets. Scheduled scans keep the inventory current.'),
                },
                {
                    'question': _('Is private key storage secure?'),
                    'answer': _('Private keys are NEVER stored in the database. The system only tracks certificate metadata and public information. For key operations, integration with Hardware Security Modules (HSM) is supported. All certificate operations are logged for audit purposes. Keys remain where they were generated.'),
                },
                {
                    'question': _('Does it support corporate PKI?'),
                    'answer': _('Yes, the system can integrate with corporate Certificate Authorities (CA), track internal certificates, monitor Active Directory certificate services, validate trust chains, and enforce corporate PKI policies. Both online and offline CAs are supported.'),
                },
                {
                    'question': _('What compliance standards are supported?'),
                    'answer': _('The platform helps meet requirements for PCI DSS (certificate and key management), SOX (IT controls), ISO 27001 (cryptographic controls), and general security best practices. It validates certificate strength, algorithms, and expiration policies required by these standards.'),
                },
            ],
            'related_modules': [
                {'name': 'app_asset', 'title': _('Asset Management')},
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_std', 'title': _('Standards & Compliance')},
            ],
        },
        'app_incident': {
            'name': 'app_incident',
            'title': _('Incident Management'),
            'icon': 'fa-exclamation-triangle',
            'color': 'danger',
            'tagline': _('Effective Security Incident Response and Management'),
            'description': _('Comprehensive security incident response platform for detecting, analyzing, responding to, and recovering from security incidents. Streamline incident workflows, coordinate response teams, document investigation activities, and implement lessons learned. Minimize impact, reduce response time, and improve security posture through systematic incident management.'),
            'key_benefits': [
                {
                    'icon': 'fa-clock',
                    'title': _('Rapid Response'),
                    'description': _('Accelerate incident response with predefined workflows and playbooks. Automated notifications alert response teams immediately. Coordinate activities and reduce mean time to resolution (MTTR).'),
                },
                {
                    'icon': 'fa-project-diagram',
                    'title': _('Workflow Automation'),
                    'description': _('Automate incident handling with customizable workflows. Route incidents through triage, investigation, containment, and recovery stages. Track status and progress in real-time.'),
                },
                {
                    'icon': 'fa-users',
                    'title': _('Team Coordination'),
                    'description': _('Facilitate collaboration between security, IT, legal, and management teams. Share information, assign tasks, and maintain unified incident timeline. Integration with communication tools.'),
                },
                {
                    'icon': 'fa-chart-bar',
                    'title': _('Metrics & Improvement'),
                    'description': _('Track incident metrics (MTTR, MTTD, impact). Analyze trends and root causes. Implement lessons learned. Measure and improve incident response capability continuously.'),
                },
            ],
            'features': [
                {
                    'category': _('Incident Registration'),
                    'items': [
                        _('Multi-channel incident reporting (email, web form, API, phone)'),
                        _('Incident classification by type and severity'),
                        _('Automated incident ID generation'),
                        _('Rich text description with attachments'),
                        _('Incident templates for common scenarios'),
                        _('Integration with monitoring and SIEM systems'),
                        _('Automated incident creation from alerts'),
                        _('Duplicate detection and merging'),
                    ]
                },
                {
                    'category': _('Incident Classification'),
                    'items': [
                        _('Incident types (malware, phishing, DDoS, data breach, etc.)'),
                        _('Severity levels (Critical, High, Medium, Low)'),
                        _('Impact assessment (confidentiality, integrity, availability)'),
                        _('Scope definition (affected assets, users, data)'),
                        _('Business impact evaluation'),
                        _('Regulatory reporting requirements'),
                        _('Classification based on NIST, ISO standards'),
                    ]
                },
                {
                    'category': _('Workflow Management'),
                    'items': [
                        _('Customizable incident lifecycle stages'),
                        _('Status tracking (New, Assigned, In Progress, Resolved, Closed)'),
                        _('Automated workflow transitions'),
                        _('Approval gates for critical actions'),
                        _('Escalation procedures and SLA monitoring'),
                        _('Task assignments and deadlines'),
                        _('Workflow templates by incident type'),
                        _('Visual workflow designer'),
                    ]
                },
                {
                    'category': _('Investigation & Analysis'),
                    'items': [
                        _('Investigation timeline and activity log'),
                        _('Evidence collection and chain of custody'),
                        _('Root cause analysis documentation'),
                        _('Indicators of Compromise (IoC) tracking'),
                        _('Attack vector identification'),
                        _('Impact scope assessment'),
                        _('Forensic investigation support'),
                        _('Integration with threat intelligence'),
                    ]
                },
                {
                    'category': _('Response Actions'),
                    'items': [
                        _('Containment actions tracking'),
                        _('Eradication procedures'),
                        _('Recovery activities management'),
                        _('Communication plans and notifications'),
                        _('Remediation task assignments'),
                        _('Affected asset isolation'),
                        _('User account management (disable, reset)'),
                        _('Configuration change tracking'),
                    ]
                },
                {
                    'category': _('Communication & Collaboration'),
                    'items': [
                        _('Incident notes and comments'),
                        _('Internal communication thread'),
                        _('Stakeholder notifications'),
                        _('External communication templates'),
                        _('Email integration for updates'),
                        _('Slack/Teams integration'),
                        _('Conference bridge management'),
                        _('War room coordination'),
                    ]
                },
                {
                    'category': _('Documentation & Reporting'),
                    'items': [
                        _('Comprehensive incident reports'),
                        _('Post-incident review (PIR) documentation'),
                        _('Lessons learned repository'),
                        _('Executive summaries'),
                        _('Regulatory reporting (GDPR, HIPAA, PCI DSS)'),
                        _('Timeline visualization'),
                        _('Evidence package for legal'),
                        _('Export to PDF, Word, Excel'),
                    ]
                },
                {
                    'category': _('Metrics & Analytics'),
                    'items': [
                        _('Mean Time to Detect (MTTD)'),
                        _('Mean Time to Respond (MTTR)'),
                        _('Mean Time to Contain (MTTC)'),
                        _('Incident volume trends'),
                        _('Incident by type/severity dashboards'),
                        _('Response team performance'),
                        _('Cost of incidents calculation'),
                        _('SLA compliance tracking'),
                    ]
                },
                {
                    'category': _('Integration & Automation'),
                    'items': [
                        _('SIEM integration (Wazuh, Splunk, ELK)'),
                        _('SOAR platform integration'),
                        _('Ticketing system integration (Jira, ServiceNow)'),
                        _('Email parsing and incident creation'),
                        _('REST API for external systems'),
                        _('Webhook notifications'),
                        _('Playbook automation'),
                        _('Response action orchestration'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Security Incident Response'),
                    'description': _('Handle security incidents from detection to resolution. Follow structured incident response process (Preparation, Detection, Analysis, Containment, Eradication, Recovery, Lessons Learned). Coordinate security team activities and maintain incident documentation.'),
                },
                {
                    'title': _('Data Breach Management'),
                    'description': _('Manage data breach incidents with regulatory reporting requirements. Track affected individuals, assess data exposure, coordinate breach notifications, and document response for GDPR, HIPAA, or state breach notification laws.'),
                },
                {
                    'title': _('Ransomware Response'),
                    'description': _('Respond to ransomware attacks systematically. Isolate affected systems, assess impact, coordinate with law enforcement, manage backups restoration, and document recovery process. Track ransom communications if necessary.'),
                },
                {
                    'title': _('Phishing Campaign Response'),
                    'description': _('Handle mass phishing incidents efficiently. Track affected users, coordinate user notifications, block malicious URLs, reset compromised credentials, and provide remedial security awareness training.'),
                },
                {
                    'title': _('Insider Threat Investigation'),
                    'description': _('Investigate suspected insider threats with proper documentation. Maintain chain of custody for evidence, coordinate with HR and legal, track access logs and activities, and document findings for potential legal action.'),
                },
                {
                    'title': _('Third-Party Security Incidents'),
                    'description': _('Manage incidents involving third-party vendors or partners. Coordinate response with external parties, assess supply chain impact, track vendor communications, and document remediation requirements.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django with PostgreSQL for incident data storage. Celery for background tasks (notifications, SLA monitoring, automated actions). Redis for real-time updates and caching. WebSocket support for live incident updates. Integration layer for SIEM, SOAR, and ticketing systems.'),
                'security': _('Incident data encryption at rest and in transit. Fine-grained access control for sensitive incidents. Need-to-know principle enforcement. Audit trail for all incident activities. Secure evidence storage. Data retention policies. Compliance with incident handling standards (NIST SP 800-61, ISO 27035).'),
                'scalability': _('Handles high volumes of incidents and alerts. Efficient incident querying and filtering. Real-time dashboards with optimized queries. Background processing for analytics. Horizontal scaling support. Archive old incidents for performance.'),
                'customization': _('Custom incident types and fields. Configurable workflows and stages. Custom notification templates. Flexible SLA definitions. Pluggable integration modules. Custom playbooks and runbooks. White-label branding. Custom report templates.'),
            },
            'screenshots': [
                {'title': _('Incident Dashboard'), 'description': _('Overview of active incidents')},
                {'title': _('Incident Details'), 'description': _('Complete incident information')},
                {'title': _('Investigation Timeline'), 'description': _('Activity history')},
                {'title': _('Workflow Management'), 'description': _('Response process tracking')},
                {'title': _('Team Collaboration'), 'description': _('Communication and tasks')},
                {'title': _('Analytics Dashboard'), 'description': _('Metrics and trends')},
            ],
            'faq': [
                {
                    'question': _('What incident types are supported?'),
                    'answer': _('The system supports all common incident types: malware infection, phishing, ransomware, data breach, DDoS attack, unauthorized access, insider threat, policy violation, system compromise, account takeover, and more. You can define custom incident types specific to your organization.'),
                },
                {
                    'question': _('How does incident workflow automation work?'),
                    'answer': _('Workflows define stages an incident passes through (New → Triage → Investigation → Containment → Recovery → Closed). Each stage can have automated actions, required tasks, approval gates, and SLA timers. Different workflows can be configured for different incident types and severities.'),
                },
                {
                    'question': _('Can it integrate with SIEM systems?'),
                    'answer': _('Yes, the platform integrates with SIEM systems like Wazuh, Splunk, ELK Stack, and others. Alerts from SIEM can automatically create incidents, or incidents can pull data from SIEM for investigation. Bi-directional integration keeps systems synchronized.'),
                },
                {
                    'question': _('How are incident metrics calculated?'),
                    'answer': _('The system tracks key metrics: Mean Time to Detect (MTTD) from occurrence to detection, Mean Time to Respond (MTTR) from detection to resolution, Mean Time to Contain (MTTC) from detection to containment. Metrics are calculated automatically based on incident timestamps and displayed on dashboards.'),
                },
                {
                    'question': _('Does it support regulatory reporting?'),
                    'answer': _('Yes, the platform includes templates and workflows for regulatory breach notifications (GDPR 72-hour notification, HIPAA breach reporting, PCI DSS incident reporting). Generate compliant reports with required information, track notification deadlines, and maintain documentation for regulators.'),
                },
                {
                    'question': _('How is team collaboration facilitated?'),
                    'answer': _('Teams collaborate through incident-specific communication threads, task assignments, file sharing, and activity feeds. Integration with Slack, Microsoft Teams, and email keeps everyone informed. Role-based access ensures appropriate team members see relevant incidents.'),
                },
                {
                    'question': _('Can playbooks be automated?'),
                    'answer': _('Yes, the platform supports playbook automation. Define response playbooks with automated and manual steps. Integration with SOAR platforms allows orchestration of technical response actions. Playbooks can be triggered automatically or manually based on incident type.'),
                },
            ],
            'related_modules': [
                {'name': 'app_soc', 'title': _('Security Operations Center')},
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_asset', 'title': _('Asset Management')},
            ],
        },
        'app_std': {
            'name': 'app_std',
            'title': _('Standards & Compliance'),
            'icon': 'fa-check-square',
            'color': 'success',
            'tagline': _('Comprehensive Security Standards and Compliance Management'),
            'description': _('Manage organizational compliance with information security standards and regulatory requirements. Track implementation of ISO 27001, NIST, GDPR, PCI DSS, HIPAA, SOX and other frameworks. Conduct gap analysis, manage control implementation, prepare for audits, and maintain continuous compliance. Demonstrate security posture to auditors, regulators, and stakeholders.'),
            'key_benefits': [
                {
                    'icon': 'fa-book',
                    'title': _('Standards Library'),
                    'description': _('Comprehensive library of security standards and frameworks: ISO 27001/27002, NIST CSF, CIS Controls, PCI DSS, HIPAA, GDPR, SOX, and more. Pre-built control mappings and requirements documentation.'),
                },
                {
                    'icon': 'fa-tasks',
                    'title': _('Gap Analysis'),
                    'description': _('Assess current security posture against standard requirements. Identify compliance gaps and missing controls. Prioritize remediation efforts. Track progress toward full compliance.'),
                },
                {
                    'icon': 'fa-clipboard-check',
                    'title': _('Control Implementation'),
                    'description': _('Track implementation of security controls and requirements. Assign responsibilities, set deadlines, monitor progress. Link controls to policies, procedures, and evidence. Maintain control effectiveness assessment.'),
                },
                {
                    'icon': 'fa-file-invoice',
                    'title': _('Audit Readiness'),
                    'description': _('Prepare for internal and external audits. Generate audit documentation, evidence packages, and compliance reports. Track audit findings and remediation. Maintain Statement of Applicability (SoA) for ISO 27001.'),
                },
            ],
            'features': [
                {
                    'category': _('Standards & Frameworks'),
                    'items': [
                        _('ISO 27001/27002 ISMS'),
                        _('NIST Cybersecurity Framework (CSF)'),
                        _('CIS Controls (v8)'),
                        _('PCI DSS (Payment Card Industry)'),
                        _('HIPAA (Healthcare)'),
                        _('GDPR (Data Protection)'),
                        _('SOX (Sarbanes-Oxley IT Controls)'),
                        _('COBIT 2019'),
                        _('NIST SP 800-53'),
                        _('Custom framework support'),
                    ]
                },
                {
                    'category': _('Compliance Assessment'),
                    'items': [
                        _('Self-assessment questionnaires'),
                        _('Gap analysis tools'),
                        _('Compliance scoring and maturity levels'),
                        _('Control implementation status tracking'),
                        _('Evidence collection and management'),
                        _('Non-conformity tracking'),
                        _('Corrective action plans'),
                        _('Compliance dashboard and metrics'),
                    ]
                },
                {
                    'category': _('Control Management'),
                    'items': [
                        _('Control library and catalog'),
                        _('Control-to-requirement mapping'),
                        _('Control ownership assignment'),
                        _('Implementation status tracking'),
                        _('Control effectiveness assessment'),
                        _('Compensating controls documentation'),
                        _('Control testing schedules'),
                        _('Control narrative documentation'),
                    ]
                },
                {
                    'category': _('Policy & Procedure Management'),
                    'items': [
                        _('Policy templates by standard'),
                        _('Policy-to-control mapping'),
                        _('Policy version control'),
                        _('Policy approval workflows'),
                        _('Procedure documentation'),
                        _('Policy distribution and acknowledgment'),
                        _('Policy review schedules'),
                        _('Policy repository'),
                    ]
                },
                {
                    'category': _('Audit Management'),
                    'items': [
                        _('Audit planning and scheduling'),
                        _('Audit scope definition'),
                        _('Audit checklist generation'),
                        _('Finding and observation tracking'),
                        _('Corrective action management'),
                        _('Audit evidence repository'),
                        _('Audit report generation'),
                        _('Follow-up audit tracking'),
                    ]
                },
                {
                    'category': _('Evidence Management'),
                    'items': [
                        _('Centralized evidence repository'),
                        _('Evidence-to-control linking'),
                        _('Document version control'),
                        _('Evidence expiration tracking'),
                        _('Automated evidence collection'),
                        _('Evidence review and approval'),
                        _('Audit trail for evidence access'),
                        _('Evidence package export'),
                    ]
                },
                {
                    'category': _('Risk & Control Integration'),
                    'items': [
                        _('Link controls to risks'),
                        _('Control effectiveness on risk scores'),
                        _('Risk-based compliance prioritization'),
                        _('Integrated risk-compliance dashboard'),
                        _('Control failure impact assessment'),
                        _('Risk treatment to control mapping'),
                    ]
                },
                {
                    'category': _('Reporting & Documentation'),
                    'items': [
                        _('Compliance status reports'),
                        _('Gap analysis reports'),
                        _('Control implementation reports'),
                        _('Statement of Applicability (ISO 27001)'),
                        _('Executive compliance dashboards'),
                        _('Audit-ready documentation packages'),
                        _('Compliance trend analysis'),
                        _('Custom report builder'),
                        _('Export to PDF, Word, Excel'),
                    ]
                },
                {
                    'category': _('Continuous Monitoring'),
                    'items': [
                        _('Automated compliance monitoring'),
                        _('Control testing automation'),
                        _('Compliance alerts and notifications'),
                        _('Drift detection from baseline'),
                        _('Periodic review scheduling'),
                        _('KPI and KRI tracking'),
                        _('Continuous improvement workflows'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('ISO 27001 Certification'),
                    'description': _('Implement and maintain ISO 27001 Information Security Management System. Conduct gap analysis, implement required controls, prepare Statement of Applicability, gather evidence, and prepare for certification audit. Maintain compliance after certification.'),
                },
                {
                    'title': _('NIST Cybersecurity Framework Implementation'),
                    'description': _('Adopt NIST CSF to manage cybersecurity risks. Assess current state against framework functions (Identify, Protect, Detect, Respond, Recover). Create target profile, identify gaps, and implement improvement roadmap.'),
                },
                {
                    'title': _('PCI DSS Compliance'),
                    'description': _('Achieve and maintain PCI DSS compliance for payment card processing. Track implementation of 12 requirements and sub-requirements. Prepare for QSA audits. Maintain quarterly vulnerability scans and annual penetration testing documentation.'),
                },
                {
                    'title': _('GDPR Data Protection Compliance'),
                    'description': _('Ensure GDPR compliance for personal data processing. Document lawful basis, implement technical and organizational measures, maintain records of processing activities (ROPA), prepare for data protection impact assessments (DPIA).'),
                },
                {
                    'title': _('Multi-Framework Compliance'),
                    'description': _('Manage compliance with multiple standards simultaneously. Map common controls across frameworks to reduce duplication. Demonstrate compliance efficiency. Maintain unified compliance posture across all applicable standards.'),
                },
                {
                    'title': _('Audit Preparation'),
                    'description': _('Prepare for internal, external, or regulatory audits. Organize evidence by control or requirement. Generate audit documentation packages. Track audit findings and implement corrective actions. Demonstrate continuous improvement.'),
                },
            ],
            'technical_details': {
                'architecture': _('Django application with PostgreSQL for compliance data. Celery for scheduled compliance checks and notifications. Document storage integration for evidence management. REST API for integration with GRC platforms. Workflow engine for approval processes.'),
                'security': _('Compliance data encryption at rest. Access control by standard and control. Audit trail for all compliance activities. Evidence tampering prevention. Secure document storage. Role-based permissions. Data retention policies.'),
                'scalability': _('Support for multiple standards simultaneously. Efficient control and requirement queries. Handles large evidence repositories. Optimized for organizations of any size. Background processing for assessments. Archive completed audits.'),
                'customization': _('Custom standards and frameworks. Configurable control libraries. Custom assessment criteria. Flexible evidence requirements. White-label branding. Custom report templates. Workflow customization. Integration APIs.'),
            },
            'screenshots': [
                {'title': _('Compliance Dashboard'), 'description': _('Overview of compliance status')},
                {'title': _('Standards Library'), 'description': _('Available frameworks and standards')},
                {'title': _('Gap Analysis'), 'description': _('Identify compliance gaps')},
                {'title': _('Control Implementation'), 'description': _('Track control progress')},
                {'title': _('Evidence Repository'), 'description': _('Manage compliance evidence')},
                {'title': _('Audit Management'), 'description': _('Prepare for audits')},
            ],
            'faq': [
                {
                    'question': _('What standards and frameworks are supported?'),
                    'answer': _('The platform includes comprehensive support for ISO 27001/27002, NIST CSF, CIS Controls, PCI DSS, HIPAA, GDPR, SOX, COBIT, NIST SP 800-53, and other major frameworks. You can also create custom frameworks or import industry-specific standards. Each standard includes pre-built controls, requirements, and assessment templates.'),
                },
                {
                    'question': _('How does gap analysis work?'),
                    'answer': _('Gap analysis compares your current security posture against standard requirements. You assess each control or requirement (Implemented, Partially Implemented, Not Implemented, Not Applicable). The system calculates compliance percentage, identifies gaps, and helps prioritize remediation based on risk and importance.'),
                },
                {
                    'question': _('Can I manage multiple standards simultaneously?'),
                    'answer': _('Yes, the platform supports managing compliance with multiple standards at once. Common controls are mapped across frameworks to avoid duplication. You can see which controls satisfy multiple standards, maintain unified evidence repository, and generate cross-framework reports.'),
                },
                {
                    'question': _('How does evidence management work?'),
                    'answer': _('Evidence documents are stored in centralized repository and linked to specific controls or requirements. Track evidence validity periods, receive expiration alerts, maintain version history, and organize evidence by standard or audit. Generate evidence packages for auditors with one click.'),
                },
                {
                    'question': _('Does it help with ISO 27001 certification?'),
                    'answer': _('Yes, the platform provides complete ISO 27001 support including gap analysis against Annex A controls, risk assessment integration, Statement of Applicability (SoA) generation, ISMS documentation templates, and audit-ready evidence packages. Many organizations use it to prepare for and maintain ISO 27001 certification.'),
                },
                {
                    'question': _('Can it integrate with risk management?'),
                    'answer': _('Yes, full integration with risk management module. Link controls to risks they mitigate, see risk reduction from control implementation, prioritize compliance based on risk levels, and maintain unified risk-compliance view. Controls update residual risk calculations automatically.'),
                },
                {
                    'question': _('How are audits managed?'),
                    'answer': _('Create audit projects with scope, schedule, and checklist. Track audit findings and observations, assign corrective actions with due dates, manage follow-up audits, and maintain audit history. Generate audit reports and evidence packages. Support for internal audits, external audits, and self-assessments.'),
                },
            ],
            'related_modules': [
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_doc', 'title': _('Document Management')},
                {'name': 'app_asset', 'title': _('Asset Management')},
            ],
        },
        'app_access': {
            'name': 'app_access',
            'title': _('Access Management'),
            'icon': 'fa-lock',
            'color': 'primary',
            'tagline': _('Comprehensive Access Rights and Permissions Management'),
            'description': _('Enterprise access management system for controlling and auditing user access to information systems and resources. Manage access requests, approval workflows, periodic access reviews, segregation of duties, and role-based access control. Ensure least privilege principle, prevent unauthorized access, and maintain comprehensive audit trails for compliance.'),
            'key_benefits': [
                {
                    'icon': 'fa-user-shield',
                    'title': _('Access Request Management'),
                    'description': _('Streamline access request and approval process. Users submit requests through self-service portal. Automated routing to appropriate approvers. Track request status and maintain complete audit trail.'),
                },
                {
                    'icon': 'fa-sync-alt',
                    'title': _('Periodic Access Reviews'),
                    'description': _('Automate periodic access certification campaigns. Access owners review and approve user permissions. Identify and remove excessive or unused access. Meet compliance requirements for regular access reviews.'),
                },
                {
                    'icon': 'fa-users-cog',
                    'title': _('Role-Based Access Control'),
                    'description': _('Implement RBAC with predefined roles and permissions. Assign roles based on job function. Simplify access management at scale. Ensure consistent access across organization.'),
                },
                {
                    'icon': 'fa-balance-scale',
                    'title': _('Segregation of Duties'),
                    'description': _('Enforce segregation of duties (SoD) policies. Detect conflicting access rights. Prevent fraud and errors. Implement compensating controls when SoD conflicts are unavoidable.'),
                },
            ],
            'features': [
                {
                    'category': _('Access Request Management'),
                    'items': [
                        _('Self-service access request portal'),
                        _('Request templates by system or role'),
                        _('Business justification requirement'),
                        _('Temporary vs permanent access'),
                        _('Access expiration dates'),
                        _('Bulk access requests'),
                        _('Request status tracking'),
                        _('Automated notifications'),
                    ]
                },
                {
                    'category': _('Approval Workflows'),
                    'items': [
                        _('Multi-level approval workflows'),
                        _('Manager approval'),
                        _('Resource owner approval'),
                        _('Security team approval'),
                        _('Conditional approval routing'),
                        _('Approval delegation'),
                        _('Escalation for overdue approvals'),
                        _('Approval audit trail'),
                    ]
                },
                {
                    'category': _('Access Provisioning'),
                    'items': [
                        _('Manual provisioning workflow'),
                        _('Integration with identity systems (AD, LDAP)'),
                        _('Automated account creation'),
                        _('Access fulfillment tracking'),
                        _('Provisioning status updates'),
                        _('Notification to requester'),
                        _('Bulk provisioning operations'),
                    ]
                },
                {
                    'category': _('Access Reviews & Certification'),
                    'items': [
                        _('Scheduled access review campaigns'),
                        _('User-by-user access certification'),
                        _('Role membership reviews'),
                        _('Privileged access reviews'),
                        _('Access owner certification'),
                        _('Auto-reminders for pending reviews'),
                        _('Review completion dashboards'),
                        _('Non-compliant access tracking'),
                    ]
                },
                {
                    'category': _('Role Management'),
                    'items': [
                        _('Role definition and catalog'),
                        _('Role-to-permission mapping'),
                        _('Role hierarchy and inheritance'),
                        _('Role owners assignment'),
                        _('Role templates by job function'),
                        _('Role lifecycle management'),
                        _('Role mining from existing access'),
                        _('Role effectiveness analysis'),
                    ]
                },
                {
                    'category': _('Segregation of Duties (SoD)'),
                    'items': [
                        _('SoD policy definition'),
                        _('Conflicting access detection'),
                        _('SoD violation reports'),
                        _('Risk scoring for violations'),
                        _('Compensating controls documentation'),
                        _('SoD approval workflow'),
                        _('Continuous SoD monitoring'),
                    ]
                },
                {
                    'category': _('Access Analytics & Reporting'),
                    'items': [
                        _('User access matrix'),
                        _('Access by system/application'),
                        _('Access by department/team'),
                        _('Orphaned accounts detection'),
                        _('Excessive access identification'),
                        _('Dormant account reports'),
                        _('Access request metrics'),
                        _('Compliance dashboards'),
                        _('Export to Excel, PDF, CSV'),
                    ]
                },
                {
                    'category': _('Integration & Automation'),
                    'items': [
                        _('Active Directory integration'),
                        _('LDAP directory integration'),
                        _('HR system integration'),
                        _('Ticketing system integration'),
                        _('SIEM integration for access events'),
                        _('REST API for external systems'),
                        _('Automated onboarding/offboarding'),
                        _('Webhook notifications'),
                    ]
                },
                {
                    'category': _('Audit & Compliance'),
                    'items': [
                        _('Complete access audit trail'),
                        _('Who-has-access-to-what reports'),
                        _('Access change history'),
                        _('Compliance certification tracking'),
                        _('SOX compliance support'),
                        _('GDPR access rights management'),
                        _('Access review evidence'),
                        _('Audit-ready documentation'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Joiner-Mover-Leaver Process'),
                    'description': _('Automate access provisioning for new employees (joiners), role changes (movers), and access revocation for departing employees (leavers). Integrate with HR systems for automatic triggers. Ensure timely access provisioning and de-provisioning.'),
                },
                {
                    'title': _('Periodic Access Certification'),
                    'description': _('Conduct quarterly or annual access reviews as required by SOX, PCI DSS, or internal policies. Access owners certify that users still require their assigned access. Automatically revoke access that is not certified.'),
                },
                {
                    'title': _('Privileged Access Management'),
                    'description': _('Manage elevated access to critical systems. Require additional approvals for privileged access. Implement time-bound privileged access. Monitor and review privileged account usage regularly.'),
                },
                {
                    'title': _('SOX Compliance'),
                    'description': _('Meet SOX requirements for IT general controls (ITGC). Implement segregation of duties for financial systems. Conduct access reviews. Maintain audit trails. Generate compliance reports for auditors.'),
                },
                {
                    'title': _('Self-Service Access Requests'),
                    'description': _('Reduce IT helpdesk workload with self-service access request portal. Users request access themselves with business justification. Automated routing ensures quick approvals. IT fulfills approved requests efficiently.'),
                },
                {
                    'title': _('Emergency Access'),
                    'description': _('Provide controlled emergency access (break-glass) process. Request and approve emergency access quickly. Automatically expire emergency access. Monitor emergency access usage. Generate emergency access reports.'),
                },
            ],
            'technical_details': {
                'architecture': _('Django application with PostgreSQL for access data. Celery for scheduled tasks (reviews, expirations, notifications). Redis for caching. Integration layer for AD/LDAP, HR systems, and ticketing platforms. Workflow engine for approval processes.'),
                'security': _('Access data encryption at rest. Fine-grained permissions for viewing access information. Audit logging for all operations. Secure API with OAuth 2.0. Protection against privilege escalation. Separation of duties in access management itself.'),
                'scalability': _('Supports thousands of users and systems. Efficient access queries and searches. Background processing for bulk operations. Optimized for large organizations. Handles high-volume access requests. Archive historical access data.'),
                'customization': _('Custom approval workflows by system or role. Configurable access types and categories. Flexible SoD policies. Custom access request forms. White-label branding. Custom notification templates. Integration APIs.'),
            },
            'screenshots': [
                {'title': _('Access Request Portal'), 'description': _('Self-service access requests')},
                {'title': _('Approval Workflow'), 'description': _('Multi-level approvals')},
                {'title': _('Access Matrix'), 'description': _('User access overview')},
                {'title': _('Access Review Campaign'), 'description': _('Certification process')},
                {'title': _('SoD Violations'), 'description': _('Segregation of duties')},
                {'title': _('Access Analytics'), 'description': _('Reports and dashboards')},
            ],
            'faq': [
                {
                    'question': _('How does access request workflow work?'),
                    'answer': _('Users submit access requests through self-service portal specifying system/application and required access level. Requests route through approval workflow (manager → resource owner → security) based on configured rules. Approvers receive notifications and can approve/reject with comments. After all approvals, IT provisions the access and notifies requester. Complete audit trail is maintained.'),
                },
                {
                    'question': _('What is periodic access review?'),
                    'answer': _('Periodic access reviews (access certification) are scheduled campaigns where access owners review and certify that users still need their assigned access. System generates review tasks for each access owner showing users and their access. Owners approve or revoke access. This ensures least privilege and meets compliance requirements like SOX quarterly reviews.'),
                },
                {
                    'question': _('How does segregation of duties work?'),
                    'answer': _('Define SoD policies specifying conflicting access combinations (e.g., create purchase order + approve payment). System automatically detects violations when reviewing access requests or existing access. Violations require additional approval or compensating controls. Continuous monitoring alerts on new SoD conflicts.'),
                },
                {
                    'question': _('Can it integrate with Active Directory?'),
                    'answer': _('Yes, full Active Directory and LDAP integration. Import users and groups, provision accounts automatically, assign group memberships, sync access changes bidirectionally. Can also integrate with Azure AD, Okta, and other identity providers through standard protocols (LDAP, SCIM, REST APIs).'),
                },
                {
                    'question': _('How are role-based access controls implemented?'),
                    'answer': _('Define roles representing job functions (e.g., Accountant, HR Manager). Map roles to permissions across systems. Assign roles to users instead of individual permissions. When user changes role, simply reassign the role. Simplifies access management at scale and ensures consistency.'),
                },
                {
                    'question': _('Does it support temporary access?'),
                    'answer': _('Yes, access requests can specify expiration dates for temporary access needs (contractors, special projects). System automatically revokes access when expiration date is reached. Notifications sent before expiration. Extension requests can be submitted if needed. Useful for time-bound access requirements.'),
                },
            ],
            'related_modules': [
                {'name': 'app_cabinet', 'title': _('User Cabinet & Authentication')},
                {'name': 'app_asset', 'title': _('Asset Management')},
                {'name': 'app_std', 'title': _('Standards & Compliance')},
            ],
        },
        'app_soc': {
            'name': 'app_soc',
            'title': _('Security Operations Center (SOC)'),
            'icon': 'fa-eye',
            'color': 'dark',
            'tagline': _('Real-Time Security Monitoring and Operations'),
            'description': _('Comprehensive Security Operations Center platform for continuous security monitoring, threat detection, and incident response. Integrate with SIEM systems, analyze security events, detect threats in real-time, and coordinate response activities. Centralize security monitoring, improve detection capabilities, and reduce response time to security threats.'),
            'key_benefits': [
                {
                    'icon': 'fa-desktop',
                    'title': _('Unified Dashboard'),
                    'description': _('Centralized view of security posture. Real-time dashboards showing alerts, incidents, and threats. Customizable widgets for different stakeholders. Quick access to critical security information.'),
                },
                {
                    'icon': 'fa-bell',
                    'title': _('Alert Management'),
                    'description': _('Aggregate alerts from multiple sources. Correlate and deduplicate alerts. Prioritize based on severity and impact. Route to appropriate analysts. Track alert-to-incident workflow.'),
                },
                {
                    'icon': 'fa-brain',
                    'title': _('Threat Intelligence'),
                    'description': _('Integrate threat intelligence feeds. Enrich alerts with threat context. Track Indicators of Compromise (IoCs). Identify known threats and TTPs. Share threat information with community.'),
                },
                {
                    'icon': 'fa-chart-line',
                    'title': _('SOC Metrics & KPIs'),
                    'description': _('Track SOC performance metrics. Monitor Mean Time to Detect (MTTD) and Respond (MTTR). Measure alert accuracy and false positive rates. Demonstrate SOC effectiveness to management.'),
                },
            ],
            'features': [
                {
                    'category': _('Security Monitoring'),
                    'items': [
                        _('Real-time security event monitoring'),
                        _('Multi-source log aggregation'),
                        _('Security dashboard and visualizations'),
                        _('Custom monitoring views'),
                        _('Geo-location tracking'),
                        _('Network traffic analysis'),
                        _('Endpoint activity monitoring'),
                        _('Cloud security monitoring'),
                    ]
                },
                {
                    'category': _('SIEM Integration'),
                    'items': [
                        _('Wazuh SIEM integration'),
                        _('Splunk connector'),
                        _('Elastic Stack (ELK) integration'),
                        _('QRadar integration'),
                        _('ArcSight integration'),
                        _('LogRhythm integration'),
                        _('Generic syslog ingestion'),
                        _('Custom SIEM connectors'),
                    ]
                },
                {
                    'category': _('Alert Management'),
                    'items': [
                        _('Alert ingestion from multiple sources'),
                        _('Alert correlation and deduplication'),
                        _('Alert enrichment with context'),
                        _('Priority and severity scoring'),
                        _('Alert escalation workflows'),
                        _('Alert assignment and tracking'),
                        _('Alert suppression rules'),
                        _('Alert lifecycle management'),
                    ]
                },
                {
                    'category': _('Threat Detection'),
                    'items': [
                        _('Anomaly detection'),
                        _('Behavior analytics (UEBA)'),
                        _('Threat hunting capabilities'),
                        _('Indicator of Compromise (IoC) matching'),
                        _('Attack pattern detection (MITRE ATT&CK)'),
                        _('Machine learning-based detection'),
                        _('Custom detection rules'),
                        _('Threat scoring and ranking'),
                    ]
                },
                {
                    'category': _('Threat Intelligence'),
                    'items': [
                        _('Threat intelligence feed integration'),
                        _('IoC database and management'),
                        _('STIX/TAXII support'),
                        _('Threat actor tracking'),
                        _('Campaign identification'),
                        _('TTP (Tactics, Techniques, Procedures) mapping'),
                        _('Threat intelligence sharing'),
                        _('Intelligence-driven alerts'),
                    ]
                },
                {
                    'category': _('Incident Response Integration'),
                    'items': [
                        _('Alert-to-incident escalation'),
                        _('Incident workflow integration'),
                        _('Response playbook automation'),
                        _('Evidence collection'),
                        _('Forensic data preservation'),
                        _('Remediation action tracking'),
                        _('Post-incident analysis'),
                    ]
                },
                {
                    'category': _('Case Management'),
                    'items': [
                        _('Investigation case creation'),
                        _('Case timeline and notes'),
                        _('Evidence attachment'),
                        _('Analyst collaboration'),
                        _('Case status tracking'),
                        _('Case templates by threat type'),
                        _('Case closure and lessons learned'),
                    ]
                },
                {
                    'category': _('Analytics & Reporting'),
                    'items': [
                        _('Real-time security dashboards'),
                        _('Executive summary reports'),
                        _('Threat landscape visualization'),
                        _('Alert volume and trends'),
                        _('SOC performance metrics'),
                        _('Analyst productivity tracking'),
                        _('Compliance reporting'),
                        _('Custom report builder'),
                        _('Export to PDF, Excel, PowerPoint'),
                    ]
                },
                {
                    'category': _('SOC Automation (SOAR)'),
                    'items': [
                        _('Automated response playbooks'),
                        _('Alert enrichment automation'),
                        _('Threat hunting automation'),
                        _('Remediation workflows'),
                        _('Integration orchestration'),
                        _('Scheduled tasks and jobs'),
                        _('API-driven automation'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('24/7 Security Monitoring'),
                    'description': _('Operate round-the-clock SOC for continuous security monitoring. Aggregate logs and events from all security tools. Detect threats in real-time. Alert on-call analysts immediately. Coordinate response across shifts. Maintain situational awareness.'),
                },
                {
                    'title': _('Threat Hunting'),
                    'description': _('Proactively hunt for threats that evaded automated detection. Use threat intelligence and behavioral analytics. Investigate suspicious patterns and anomalies. Discover advanced persistent threats (APTs). Document findings and improve detection rules.'),
                },
                {
                    'title': _('SIEM Augmentation'),
                    'description': _('Enhance existing SIEM capabilities with alert management, case tracking, and response workflows. Provide analyst workspace on top of SIEM. Integrate multiple SIEM platforms. Add threat intelligence context. Improve analyst efficiency.'),
                },
                {
                    'title': _('Managed Security Service Provider (MSSP)'),
                    'description': _('Operate SOC for multiple customers. Tenant isolation for customer data. Customer-specific dashboards and reports. Alert routing by customer. SLA tracking and reporting. Demonstrate value to customers.'),
                },
                {
                    'title': _('Compliance Monitoring'),
                    'description': _('Monitor compliance with security policies and standards. Detect policy violations in real-time. Alert on non-compliant activities. Track compliance metrics. Generate compliance reports for PCI DSS, HIPAA, SOX requirements.'),
                },
                {
                    'title': _('Cloud Security Monitoring'),
                    'description': _('Monitor security across multi-cloud environments (AWS, Azure, GCP). Track cloud configuration changes. Detect unauthorized access to cloud resources. Monitor cloud workload security. Integrate with cloud-native security tools.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django with PostgreSQL for alert and case data. Real-time WebSocket connections for live dashboards. Elasticsearch for log search and analytics. Redis for caching and real-time data. Celery for background tasks and automation. Integration layer for SIEM and security tools.'),
                'security': _('All SOC data encrypted. Access control for sensitive security information. Audit trail for SOC operations. Secure API endpoints. Protection against data leakage. Compliance with security operations best practices.'),
                'scalability': _('Handles millions of events per day. Distributed architecture for high availability. Horizontal scaling for increased load. Efficient data storage and retrieval. Real-time processing pipelines. Archive old data for performance.'),
                'customization': _('Custom dashboards and widgets. Configurable alert rules. Custom detection logic. Flexible case workflows. White-label for MSSPs. Custom integrations via API. Pluggable threat intelligence feeds.'),
            },
            'screenshots': [
                {'title': _('SOC Dashboard'), 'description': _('Real-time security overview')},
                {'title': _('Alert Queue'), 'description': _('Active alerts management')},
                {'title': _('Threat Map'), 'description': _('Geographic threat visualization')},
                {'title': _('Case Investigation'), 'description': _('Investigation workspace')},
                {'title': _('Threat Intelligence'), 'description': _('IoC database and feeds')},
                {'title': _('SOC Metrics'), 'description': _('Performance dashboards')},
            ],
            'faq': [
                {
                    'question': _('What SIEM systems are supported?'),
                    'answer': _('The platform integrates with major SIEM platforms: Wazuh (full integration), Splunk, Elastic Stack (ELK), IBM QRadar, ArcSight, LogRhythm, and any system supporting syslog or REST APIs. Integration allows bidirectional communication: receive alerts from SIEM and send investigation results back.'),
                },
                {
                    'question': _('How does alert correlation work?'),
                    'answer': _('Alert correlation groups related alerts together to reduce noise. System identifies alerts from same source IP, targeting same asset, or matching same threat pattern. Correlated alerts are deduplicated and presented as single incident. This reduces alert fatigue and helps analysts focus on real threats.'),
                },
                {
                    'question': _('Can it detect unknown threats?'),
                    'answer': _('Yes, through behavior analytics and anomaly detection. System baselines normal behavior and alerts on deviations. Machine learning models detect unusual patterns even without known signatures. Threat hunting features help analysts discover sophisticated threats that evaded automated detection.'),
                },
                {
                    'question': _('How does threat intelligence integration work?'),
                    'answer': _('Integrate commercial and open-source threat intelligence feeds (STIX/TAXII, MISP, custom feeds). System automatically enriches alerts with threat context, checks IoCs against known threats, and provides actor/campaign information. Helps analysts quickly understand threat severity and appropriate response.'),
                },
                {
                    'question': _('What automation capabilities are included?'),
                    'answer': _('SOAR (Security Orchestration, Automation, and Response) features include automated alert enrichment, playbook execution for common scenarios, automated threat hunting queries, remediation action orchestration, and integration with security tools. Reduces manual work and accelerates response.'),
                },
                {
                    'question': _('Can it be used by MSSPs?'),
                    'answer': _('Yes, designed for multi-tenant MSSP operations. Customer data isolation, per-customer dashboards and reports, customer-specific alert routing, SLA tracking, and customer portals. Efficient SOC operations for multiple customers from single platform.'),
                },
            ],
            'related_modules': [
                {'name': 'app_incident', 'title': _('Incident Management')},
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_asset', 'title': _('Asset Management')},
            ],
        },
        'app_gophish': {
            'name': 'app_gophish',
            'title': _('Phishing Simulation (GoPhish)'),
            'icon': 'fa-fish',
            'color': 'warning',
            'tagline': _('Test and Improve Employee Phishing Awareness'),
            'description': _('Integrated phishing simulation platform powered by GoPhish for testing and improving employee security awareness. Run realistic phishing campaigns, track user responses, identify vulnerable employees, and deliver targeted training. Measure security culture, reduce phishing risk, and meet compliance requirements for security awareness testing.'),
            'key_benefits': [
                {
                    'icon': 'fa-envelope',
                    'title': _('Realistic Simulations'),
                    'description': _('Create and launch realistic phishing campaigns. Use professional email templates mimicking real attacks. Test employee awareness with various phishing techniques. Simulate spear phishing, whaling, and social engineering attacks.'),
                },
                {
                    'icon': 'fa-chart-pie',
                    'title': _('Comprehensive Analytics'),
                    'description': _('Track campaign performance in real-time. Monitor email open rates, link clicks, and credential submissions. Identify departments and users most vulnerable to phishing. Measure awareness improvement over time.'),
                },
                {
                    'icon': 'fa-graduation-cap',
                    'title': _('Integrated Training'),
                    'description': _('Deliver just-in-time training to users who fall for simulations. Provide immediate feedback and educational content. Link with training module for remedial courses. Track training completion and effectiveness.'),
                },
                {
                    'icon': 'fa-chart-line',
                    'title': _('Risk Reduction'),
                    'description': _('Reduce phishing susceptibility through regular testing. Change employee behavior with repeated simulations. Demonstrate security awareness improvement. Lower organizational risk from phishing attacks.'),
                },
            ],
            'features': [
                {
                    'category': _('Campaign Management'),
                    'items': [
                        _('Create phishing campaigns'),
                        _('Schedule automated campaigns'),
                        _('Target specific users or groups'),
                        _('Bulk user import'),
                        _('Campaign templates'),
                        _('A/B testing different approaches'),
                        _('Recurring campaign scheduling'),
                        _('Campaign cloning and reuse'),
                    ]
                },
                {
                    'category': _('Email Templates'),
                    'items': [
                        _('Professional phishing email templates'),
                        _('Customizable email content'),
                        _('HTML email designer'),
                        _('Variable insertion (name, department, etc.)'),
                        _('Template library by attack type'),
                        _('Import custom templates'),
                        _('Multi-language support'),
                        _('Template effectiveness tracking'),
                    ]
                },
                {
                    'category': _('Landing Pages'),
                    'items': [
                        _('Fake login pages'),
                        _('Credential capture'),
                        _('Educational landing pages'),
                        _('Custom HTML pages'),
                        _('Page templates library'),
                        _('Redirect after capture'),
                        _('Mobile-responsive pages'),
                        _('Page analytics'),
                    ]
                },
                {
                    'category': _('Tracking & Analytics'),
                    'items': [
                        _('Real-time campaign dashboard'),
                        _('Email open tracking'),
                        _('Link click tracking'),
                        _('Credential submission tracking'),
                        _('User timeline and history'),
                        _('Geographic location'),
                        _('Device and browser info'),
                        _('Time-to-click metrics'),
                    ]
                },
                {
                    'category': _('Reporting'),
                    'items': [
                        _('Campaign summary reports'),
                        _('User performance reports'),
                        _('Department/team reports'),
                        _('Trend analysis over time'),
                        _('Vulnerability heat maps'),
                        _('Executive dashboards'),
                        _('Compliance reports'),
                        _('Export to PDF, Excel, CSV'),
                    ]
                },
                {
                    'category': _('Training Integration'),
                    'items': [
                        _('Immediate feedback on failure'),
                        _('Link to training materials'),
                        _('Automated training assignment'),
                        _('Integration with LMS'),
                        _('Track training completion'),
                        _('Behavioral change measurement'),
                        _('Remedial training workflows'),
                    ]
                },
                {
                    'category': _('SMTP & Email'),
                    'items': [
                        _('Multiple SMTP profile support'),
                        _('Custom sending profiles'),
                        _('Email spoofing simulation'),
                        _('SPF/DKIM bypass testing'),
                        _('Bounce and error handling'),
                        _('Email throttling'),
                        _('Delivery status tracking'),
                    ]
                },
                {
                    'category': _('User Management'),
                    'items': [
                        _('User groups and segmentation'),
                        _('Department-based targeting'),
                        _('Role-based campaigns'),
                        _('Whitelist management'),
                        _('User performance history'),
                        _('High-risk user identification'),
                        _('User profile enrichment'),
                    ]
                },
                {
                    'category': _('GoPhish Integration'),
                    'items': [
                        _('Native GoPhish integration'),
                        _('Bidirectional synchronization'),
                        _('GoPhish API connectivity'),
                        _('Campaign import/export'),
                        _('Centralized management'),
                        _('Multi-instance support'),
                        _('Status monitoring'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('Employee Security Awareness Assessment'),
                    'description': _('Assess baseline employee awareness of phishing threats. Run initial campaigns to identify vulnerable users and departments. Establish metrics for awareness improvement. Provide data for security awareness program planning.'),
                },
                {
                    'title': _('Ongoing Phishing Testing'),
                    'description': _('Conduct regular phishing simulations (monthly/quarterly) to maintain employee vigilance. Vary attack techniques and difficulty. Test different departments and roles. Track improvement trends and adjust training accordingly.'),
                },
                {
                    'title': _('Targeted Training Delivery'),
                    'description': _('Identify users who click on phishing links or submit credentials. Automatically enroll them in remedial security training. Provide immediate feedback. Retest after training to measure improvement.'),
                },
                {
                    'title': _('Compliance Requirements'),
                    'description': _('Meet compliance requirements for security awareness testing (PCI DSS, HIPAA, cyber insurance). Document phishing simulation program. Generate audit reports showing testing frequency and results. Demonstrate ongoing awareness efforts.'),
                },
                {
                    'title': _('Executive and VIP Protection'),
                    'description': _('Run specialized spear phishing and whaling campaigns targeting executives. Test C-level susceptibility to targeted attacks. Provide executive-specific training. Reduce risk of high-value target compromise.'),
                },
                {
                    'title': _('Department Benchmarking'),
                    'description': _('Compare phishing susceptibility across departments. Identify high-risk teams needing additional training. Recognize departments with strong awareness. Foster healthy competition for awareness improvement.'),
                },
            ],
            'technical_details': {
                'architecture': _('Integration layer with GoPhish open-source platform. Django application manages campaigns, users, and reporting. PostgreSQL stores campaign data and results. Celery for scheduled campaigns and synchronization. REST API for GoPhish communication. Email tracking infrastructure.'),
                'security': _('Phishing simulations isolated from production email. Clear notification that emails are simulations. No actual malware in tests. Secure credential handling (immediate deletion). User privacy protection. Compliance with anti-phishing best practices. Ethical simulation guidelines.'),
                'scalability': _('Support for thousands of simultaneous recipients. Efficient email sending and tracking. Handles high-volume campaigns. Multiple GoPhish instances for load distribution. Email throttling prevents mail server overload. Archive completed campaigns.'),
                'customization': _('Custom email templates and landing pages. Configurable difficulty levels. Flexible user grouping. Custom reporting metrics. White-label branding. Integration with training platforms. API for custom workflows.'),
            },
            'screenshots': [
                {'title': _('Campaign Dashboard'), 'description': _('Active campaigns overview')},
                {'title': _('Campaign Results'), 'description': _('Detailed analytics')},
                {'title': _('Email Template Designer'), 'description': _('Create phishing emails')},
                {'title': _('Landing Page Builder'), 'description': _('Design fake pages')},
                {'title': _('User Performance'), 'description': _('Individual user history')},
                {'title': _('Department Comparison'), 'description': _('Benchmarking reports')},
            ],
            'faq': [
                {
                    'question': _('Is it legal to send fake phishing emails to employees?'),
                    'answer': _('Yes, when done properly as part of authorized security awareness program. Ensure management approval, inform employees that periodic testing occurs (without revealing timing), include clear indicators in simulation emails, and follow ethical guidelines. Many compliance frameworks require or recommend phishing simulations.'),
                },
                {
                    'question': _('How does GoPhish integration work?'),
                    'answer': _('Platform integrates with GoPhish open-source phishing framework via API. GoPhish handles email sending and tracking infrastructure. Our platform provides campaign management, user management, advanced analytics, and training integration on top of GoPhish. Can integrate existing GoPhish installations or deploy new instances.'),
                },
                {
                    'question': _('What happens when employee clicks phishing link?'),
                    'answer': _('User is directed to landing page (fake login, warning page, or training content). Action is recorded with timestamp, location, and device info. User can receive immediate feedback explaining it was simulation and providing education. High-risk behaviors (credential submission) can trigger automated training assignment.'),
                },
                {
                    'question': _('How do we measure phishing awareness improvement?'),
                    'answer': _('Track metrics over multiple campaigns: click rate (percentage clicking links), credential submission rate, time-to-click, repeat offenders. Compare results between campaigns to show improvement. Benchmark against industry averages. Measure training effectiveness by comparing results before and after training.'),
                },
                {
                    'question': _('Can we simulate specific attack types?'),
                    'answer': _('Yes, create campaigns simulating various attacks: spear phishing (targeted, personalized), whaling (executives), credential harvesting, malicious attachments (no actual malware), business email compromise (BEC), social engineering, and current threat trends. Template library includes common attack patterns.'),
                },
                {
                    'question': _('Does it integrate with security awareness training?'),
                    'answer': _('Yes, full integration with training module. Users failing simulations automatically enrolled in relevant courses. Track training completion. Measure correlation between training and simulation performance. Create remedial training paths. Report on combined phishing testing and training program effectiveness.'),
                },
            ],
            'related_modules': [
                {'name': 'app_study', 'title': _('Security Awareness Training')},
                {'name': 'app_cabinet', 'title': _('User Cabinet & Authentication')},
                {'name': 'app_incident', 'title': _('Incident Management')},
            ],
        },
        'app_gdpr': {
            'name': 'app_gdpr',
            'title': _('GDPR Compliance Management'),
            'icon': 'fa-user-shield',
            'color': 'info',
            'tagline': _('Comprehensive GDPR Compliance and Data Protection'),
            'description': _('Complete GDPR compliance platform for managing personal data protection, data subject rights, consent tracking, and regulatory compliance. Built to help organizations comply with EU General Data Protection Regulation (GDPR) through comprehensive data subject management, consent tracking, breach incident response, and data protection impact assessments.'),
            'key_benefits': [
                {
                    'icon': 'fa-user-shield',
                    'title': _('Data Subject Rights Management'),
                    'description': _('Manage data subject registries, track personal data, and handle data subject requests (access, rectification, erasure, portability) in compliance with GDPR timelines and requirements.'),
                },
                {
                    'icon': 'fa-check-circle',
                    'title': _('Consent Management'),
                    'description': _('Track and manage consent records with full audit trail. Record consent sources, purposes, and withdrawal history. Ensure lawful basis for all data processing activities.'),
                },
                {
                    'icon': 'fa-exclamation-triangle',
                    'title': _('Data Breach Response'),
                    'description': _('Document and manage data breach incidents with structured workflows. Track 72-hour notification deadlines, coordinate breach response, and maintain comprehensive incident documentation for regulatory reporting.'),
                },
                {
                    'icon': 'fa-clipboard-check',
                    'title': _('Compliance Reporting'),
                    'description': _('Generate compliance reports, track regulatory obligations, conduct Data Protection Impact Assessments (DPIA), and maintain records of processing activities as required by GDPR Article 30.'),
                },
            ],
            'features': [
                {
                    'category': _('Data Subject Management'),
                    'items': [
                        _('Comprehensive data subject registry'),
                        _('Personal data inventory'),
                        _('Data subject categorization'),
                        _('Multi-company support'),
                        _('Data subject search and filtering'),
                        _('Personal data anonymization'),
                        _('Data export capabilities'),
                        _('Audit trail for all operations'),
                    ]
                },
                {
                    'category': _('Consent Management'),
                    'items': [
                        _('Detailed consent record tracking'),
                        _('Multiple consent purposes'),
                        _('Consent source documentation'),
                        _('Consent withdrawal workflows'),
                        _('Expiration date tracking'),
                        _('Consent history and audit log'),
                        _('Granular consent management'),
                        _('Marketing consent tracking'),
                    ]
                },
                {
                    'category': _('Data Subject Requests (DSR)'),
                    'items': [
                        _('DSR intake and registration'),
                        _('Request type categorization (Access, Rectification, Erasure, Portability, Restriction)'),
                        _('30-day deadline tracking with alerts'),
                        _('DSR workflow and status management'),
                        _('Request processing documentation'),
                        _('Deadline extension procedures'),
                        _('Automated email notifications'),
                        _('DSR dashboard and reporting'),
                    ]
                },
                {
                    'category': _('Data Breach Management'),
                    'items': [
                        _('Breach incident registration'),
                        _('72-hour notification deadline tracking'),
                        _('Severity assessment (Low, Medium, High, Critical)'),
                        _('Affected individuals tracking'),
                        _('Regulatory authority reporting'),
                        _('Containment action documentation'),
                        _('Breach investigation workflows'),
                        _('Notification management'),
                    ]
                },
                {
                    'category': _('Data Protection Impact Assessment (DPIA)'),
                    'items': [
                        _('DPIA creation and management'),
                        _('Risk assessment methodology'),
                        _('Processing activity evaluation'),
                        _('Necessity and proportionality analysis'),
                        _('Risk identification and mitigation'),
                        _('DPIA approval workflow'),
                        _('High-risk processing identification'),
                        _('Review and update procedures'),
                    ]
                },
                {
                    'category': _('Processing Activities (Article 30)'),
                    'items': [
                        _('Records of processing activities'),
                        _('Processing purpose documentation'),
                        _('Data category identification'),
                        _('Recipient and third-party tracking'),
                        _('Data transfer documentation'),
                        _('Security measures description'),
                        _('Retention period definition'),
                        _('Legal basis documentation'),
                    ]
                },
                {
                    'category': _('Data Retention Policies'),
                    'items': [
                        _('Retention policy definition'),
                        _('Data category-specific retention'),
                        _('Retention period calculation'),
                        _('Automated retention alerts'),
                        _('Deletion procedure documentation'),
                        _('Legal hold management'),
                        _('Archive procedures'),
                        _('Retention compliance tracking'),
                    ]
                },
                {
                    'category': _('Reporting & Compliance'),
                    'items': [
                        _('Compliance dashboard with key metrics'),
                        _('Overdue DSR tracking'),
                        _('Breach notification status'),
                        _('DPIA coverage reporting'),
                        _('Consent statistics and analytics'),
                        _('Regulatory compliance reports'),
                        _('Audit-ready documentation'),
                        _('Export capabilities (PDF, Excel)'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('GDPR Compliance Program Implementation'),
                    'description': _('Implement comprehensive GDPR compliance program from scratch. Register data subjects, document processing activities, establish consent management procedures, and set up data subject request workflows. Track compliance progress and generate audit documentation.'),
                },
                {
                    'title': _('Data Subject Request Processing'),
                    'description': _('Handle data subject requests efficiently and within regulatory timelines. Receive access requests, compile personal data, coordinate with departments, document processing steps, and deliver responses within 30-day deadline. Track request status and maintain audit trails.'),
                },
                {
                    'title': _('Data Breach Response and Notification'),
                    'description': _('Respond to data breach incidents systematically. Document breach details, assess severity and impact, notify supervisory authority within 72 hours when required, coordinate breach containment, communicate with affected individuals, and maintain comprehensive incident records.'),
                },
                {
                    'title': _('Consent Management for Marketing'),
                    'description': _('Manage marketing consent for email campaigns, newsletters, and promotional activities. Track consent sources, purposes, and timestamps. Handle consent withdrawal requests. Maintain audit trails proving lawful processing basis for all marketing communications.'),
                },
                {
                    'title': _('Third-Party Data Processor Management'),
                    'description': _('Document data processing activities involving third-party processors. Maintain records of processor contracts, data transfer mechanisms, security measures, and sub-processor arrangements. Track processor compliance with data protection obligations.'),
                },
                {
                    'title': _('Data Protection Impact Assessment (DPIA)'),
                    'description': _('Conduct systematic DPIAs for high-risk processing activities. Evaluate necessity and proportionality of processing, identify privacy risks, assess mitigation measures, document findings, and obtain DPO or management approval. Maintain DPIA records for audit purposes.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django framework with PostgreSQL database for GDPR-compliant data storage. Implements data encryption at rest and in transit. Role-based access control for sensitive personal data. Celery for automated deadline tracking and notifications. Comprehensive audit logging for all operations. Export functionality for data portability.'),
                'security': _('Personal data encryption and pseudonymization. Fine-grained access control based on data protection roles. Complete audit trail for all data access and modifications. Secure data deletion and anonymization procedures. Session management and authentication. Compliance with security requirements of GDPR Article 32.'),
                'scalability': _('Handles large volumes of data subjects and processing activities. Efficient data queries and filtering. Optimized for multi-company and multi-department structures. Archive functionality for historical records. Performance optimized for large-scale GDPR compliance operations.'),
                'customization': _('Configurable data subject fields and categories. Custom consent purposes and types. Flexible DSR workflows. Customizable breach severity criteria. Tailored DPIA templates. Company-specific retention policies. Custom reports and dashboards. Multi-language support for international operations.'),
            },
            'screenshots': [
                {'title': _('Compliance Dashboard'), 'description': _('Overview of GDPR compliance status')},
                {'title': _('Data Subject Registry'), 'description': _('Manage data subjects')},
                {'title': _('DSR Processing'), 'description': _('Handle data subject requests')},
                {'title': _('Breach Management'), 'description': _('Track data breaches')},
                {'title': _('DPIA Assessment'), 'description': _('Conduct impact assessments')},
                {'title': _('Compliance Reports'), 'description': _('Generate audit documentation')},
            ],
            'faq': [
                {
                    'question': _('What is GDPR and who needs to comply?'),
                    'answer': _('GDPR (General Data Protection Regulation) is EU regulation protecting personal data. Any organization processing personal data of EU residents must comply, regardless of where the organization is located. This includes businesses, non-profits, government agencies, and any entity collecting, storing, or processing EU personal data.'),
                },
                {
                    'question': _('What are data subject rights under GDPR?'),
                    'answer': _('GDPR grants individuals: Right to Access (obtain copy of data), Right to Rectification (correct inaccurate data), Right to Erasure ("right to be forgotten"), Right to Data Portability (receive data in structured format), Right to Restriction (limit processing), Right to Object (object to processing), and Rights related to automated decision-making and profiling.'),
                },
                {
                    'question': _('What is the 72-hour breach notification rule?'),
                    'answer': _('Under GDPR Article 33, organizations must notify supervisory authority of data breaches within 72 hours of becoming aware, unless breach is unlikely to result in risk to individuals. Notification must include breach nature, affected individuals, likely consequences, and remediation measures. Module tracks 72-hour deadline and helps prepare required documentation.'),
                },
                {
                    'question': _('What is Data Protection Impact Assessment (DPIA)?'),
                    'answer': _('DPIA is systematic assessment required for processing operations likely to result in high risk to individuals\' rights and freedoms. Required for large-scale processing of sensitive data, systematic monitoring, or new technologies. DPIA evaluates necessity, proportionality, risks, and safeguards. Module provides structured DPIA workflow with templates.'),
                },
                {
                    'question': _('What are Records of Processing Activities (Article 30)?'),
                    'answer': _('GDPR Article 30 requires organizations to maintain written records of processing activities. Records must document processing purposes, data categories, recipients, data transfers, retention periods, and security measures. Module provides structured template for maintaining comprehensive Article 30 records.'),
                },
                {
                    'question': _('How does consent management work?'),
                    'answer': _('GDPR requires specific, informed, unambiguous, and freely given consent. Module tracks consent with timestamps, sources, purposes, and duration. Records consent withdrawal with full history. Ensures audit trail proving valid consent at any point in time. Supports granular consent for multiple purposes.'),
                },
            ],
            'related_modules': [
                {'name': 'app_std', 'title': _('Standards & Compliance')},
                {'name': 'app_doc', 'title': _('Document Management')},
                {'name': 'app_incident', 'title': _('Incident Management')},
            ],
        },
        'app_compliance': {
            'name': 'app_compliance',
            'title': _('Framework Compliance'),
            'icon': 'fa-balance-scale',
            'color': 'primary',
            'tagline': _('Multi-Framework Compliance Management'),
            'description': _('Comprehensive compliance management platform supporting multiple security frameworks including NIST Cybersecurity Framework (CSF), CIS Controls, ISO 27001, and other industry standards. Perform maturity assessments, track control implementations, identify compliance gaps, and demonstrate security posture across frameworks.'),
            'key_benefits': [
                {
                    'icon': 'fa-list-check',
                    'title': _('Multi-Framework Support'),
                    'description': _('Manage compliance across multiple frameworks simultaneously with unified control mapping and cross-framework alignment capabilities.'),
                },
                {
                    'icon': 'fa-chart-bar',
                    'title': _('Maturity Assessment'),
                    'description': _('Evaluate organizational security maturity against framework requirements with structured assessment workflows and scoring.'),
                },
                {
                    'icon': 'fa-magnifying-glass-chart',
                    'title': _('Gap Analysis'),
                    'description': _('Identify compliance gaps, prioritize remediation activities, and track progress toward full framework compliance.'),
                },
                {
                    'icon': 'fa-file-lines',
                    'title': _('Compliance Reporting'),
                    'description': _('Generate comprehensive compliance reports, dashboards, and audit-ready documentation for stakeholders and regulators.'),
                },
            ],
            'features': [
                {
                    'title': _('Framework Library'),
                    'items': [
                        _('NIST Cybersecurity Framework (CSF 1.1 and 2.0)'),
                        _('CIS Controls v8'),
                        _('ISO/IEC 27001:2022'),
                        _('Custom framework support'),
                        _('Framework versioning and updates'),
                        _('Control taxonomy and categories'),
                    ]
                },
                {
                    'title': _('Compliance Assessment'),
                    'items': [
                        _('Structured assessment workflows'),
                        _('Control-by-control evaluation'),
                        _('Maturity level scoring (0-5 scale)'),
                        _('Evidence collection and attachment'),
                        _('Assessor comments and notes'),
                        _('Historical assessment tracking'),
                    ]
                },
                {
                    'title': _('Gap Analysis & Remediation'),
                    'items': [
                        _('Automated gap identification'),
                        _('Risk-based gap prioritization'),
                        _('Remediation plan creation'),
                        _('Action item tracking'),
                        _('Deadline and milestone management'),
                        _('Progress monitoring'),
                    ]
                },
                {
                    'title': _('Control Mapping'),
                    'items': [
                        _('Cross-framework control mapping'),
                        _('Control to asset linkage'),
                        _('Control to risk linkage'),
                        _('Implementation evidence tracking'),
                        _('Responsible party assignment'),
                        _('Control effectiveness measurement'),
                    ]
                },
                {
                    'title': _('Reporting & Dashboards'),
                    'items': [
                        _('Executive compliance dashboards'),
                        _('Framework maturity heatmaps'),
                        _('Compliance trend analysis'),
                        _('Gap analysis reports'),
                        _('Audit-ready documentation'),
                        _('Export capabilities (PDF, Excel)'),
                    ]
                },
            ],
            'use_cases': [
                {
                    'title': _('NIST CSF Implementation'),
                    'description': _('Implement NIST Cybersecurity Framework across your organization. Assess current maturity across five functions (Identify, Protect, Detect, Respond, Recover), identify gaps, prioritize improvements, and track progress toward target maturity levels. Generate executive dashboards showing compliance posture.'),
                },
                {
                    'title': _('CIS Controls Assessment'),
                    'description': _('Evaluate implementation of CIS Critical Security Controls v8. Assess all 18 control families, document safeguard implementations, identify missing controls, prioritize based on Implementation Groups (IG1, IG2, IG3), and demonstrate security best practices.'),
                },
                {
                    'title': _('ISO 27001 Certification'),
                    'description': _('Prepare for ISO 27001 certification audit. Document implementation of Annex A controls, track evidence, perform internal assessments, identify gaps, implement corrective actions, and generate audit-ready documentation demonstrating ISMS compliance.'),
                },
                {
                    'title': _('Multi-Framework Compliance'),
                    'description': _('Manage compliance with multiple frameworks simultaneously. Map common controls across NIST CSF, CIS Controls, and ISO 27001. Eliminate duplicate efforts. Demonstrate unified security posture. Generate framework-specific reports from single control implementation.'),
                },
                {
                    'title': _('Regulatory Compliance Tracking'),
                    'description': _('Track compliance with regulatory requirements mapped to frameworks. Link controls to specific regulations, track implementation status, generate compliance reports for auditors, demonstrate due diligence, and maintain continuous compliance monitoring.'),
                },
                {
                    'title': _('Security Maturity Improvement'),
                    'description': _('Establish baseline security maturity, set target maturity levels, create improvement roadmap, track remediation activities, measure progress over time, and demonstrate continuous security improvement to stakeholders and leadership.'),
                },
            ],
            'technical_details': {
                'architecture': _('Built on Django framework with structured compliance data models. PostgreSQL database for compliance records and assessments. Framework definitions stored as fixtures for easy updates. RESTful API for integrations. Celery for automated compliance monitoring and notifications.'),
                'security': _('Role-based access control for compliance data. Audit logging for all assessments and changes. Secure evidence storage. Compliance data encryption. Fine-grained permissions for frameworks and controls. Protected against unauthorized compliance modifications.'),
                'scalability': _('Supports unlimited frameworks and controls. Efficient queries for large compliance datasets. Optimized assessment workflows. Archive functionality for historical assessments. Performance optimized for enterprise-scale compliance operations.'),
                'customization': _('Custom framework definition support. Configurable maturity scales. Flexible control categorization. Custom gap prioritization criteria. Tailored remediation workflows. Company-specific compliance templates. Customizable dashboards and reports.'),
            },
            'screenshots': [
                {'title': _('Compliance Dashboard'), 'description': _('Overview of multi-framework compliance')},
                {'title': _('Framework Assessment'), 'description': _('Control-by-control evaluation')},
                {'title': _('Maturity Heatmap'), 'description': _('Visual maturity across functions')},
                {'title': _('Gap Analysis'), 'description': _('Identify compliance gaps')},
                {'title': _('Control Mapping'), 'description': _('Cross-framework control alignment')},
                {'title': _('Compliance Reports'), 'description': _('Audit-ready documentation')},
            ],
            'faq': [
                {
                    'question': _('What frameworks are supported?'),
                    'answer': _('Currently supports NIST Cybersecurity Framework (CSF 1.1 and 2.0), CIS Controls v8, ISO/IEC 27001:2022, and custom frameworks. Framework library is extensible, and new frameworks can be added through fixture imports or API.'),
                },
                {
                    'question': _('How does maturity assessment work?'),
                    'answer': _('Maturity assessment uses 0-5 scale: 0 (Not Implemented), 1 (Initial), 2 (Developing), 3 (Defined), 4 (Managed), 5 (Optimized). Each control is evaluated, evidence is collected, and maturity score is assigned. Historical assessments track improvement over time.'),
                },
                {
                    'question': _('Can I map controls across frameworks?'),
                    'answer': _('Yes, module supports cross-framework control mapping. Many controls are common across frameworks (e.g., access control, encryption, monitoring). Mapping enables single implementation to satisfy multiple framework requirements, reducing duplication and effort.'),
                },
                {
                    'question': _('How does gap analysis work?'),
                    'answer': _('Gap analysis compares current maturity against target maturity for each control. Module identifies controls below target, calculates gap size, prioritizes based on risk and impact, and generates remediation recommendations. Track remediation progress and re-assess to close gaps.'),
                },
                {
                    'question': _('Can I customize frameworks?'),
                    'answer': _('Yes, you can create custom frameworks, modify existing frameworks, add custom controls, define custom maturity scales, and tailor assessment questions. Module is flexible to support organization-specific compliance requirements and internal standards.'),
                },
                {
                    'question': _('How do I prepare for audits?'),
                    'answer': _('Module generates audit-ready documentation including compliance status reports, control implementation evidence, maturity scores, gap analysis, remediation plans, and historical assessment records. Export reports in PDF or Excel format for auditors and regulators.'),
                },
            ],
            'related_modules': [
                {'name': 'app_std', 'title': _('Standards & Compliance')},
                {'name': 'app_risk', 'title': _('Risk Assessment & Management')},
                {'name': 'app_doc', 'title': _('Document Management')},
                {'name': 'app_asset', 'title': _('Asset Management')},
            ],
        },
    }
    
    # Get module details or return 404
    if module_name not in modules_details:
        raise Http404(_('Module not found'))
    
    module = modules_details[module_name]
    
    context = {
        'module': module,
        'page_title': module['title'],
        'meta_description': f"{module['title']} - {module['description'][:150]}...",
        'meta_keywords': f"SecBoard, {module['title']}, information security, {module_name}",
    }
    
    return render(request, 'app_conf/module_detail.html', context)


def faq(request):
    """Public FAQ page with frequently asked questions"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_faq_page:
        raise Http404()

    # Organize FAQs by category
    faq_categories = [
        {
            'category': _('General Questions'),
            'icon': 'fa-question-circle',
            'color': 'primary',
            'questions': [
                {
                    'question': _('What is SecBoard?'),
                    'answer': _('SecBoard is a comprehensive information security management platform that integrates multiple security modules including risk assessment, incident management, compliance tracking, security awareness training, and more. It provides organizations with a unified solution for managing their cybersecurity posture.')
                },
                {
                    'question': _('Is SecBoard customizable?'),
                    'answer': _('Yes, SecBoard is highly flexible and allows quick customization and adaptation to meet specific client requirements and business needs.')
                },
                {
                    'question': _('What technologies does SecBoard use?'),
                    'answer': _('SecBoard is built on Django (Python web framework), Bootstrap 5 for UI, PostgreSQL/SQLite for database, Celery for async tasks, Redis for caching, and integrates with various security tools like Wazuh and GoPhish.')
                },
                {
                    'question': _('Who can use SecBoard?'),
                    'answer': _('SecBoard is designed for security professionals, compliance officers, risk managers, IT administrators, and organizations of any size looking to implement comprehensive information security management.')
                },
            ]
        },
        {
            'category': _('Security & Access'),
            'icon': 'fa-shield-alt',
            'color': 'success',
            'questions': [
                {
                    'question': _('How secure is SecBoard?'),
                    'answer': _('SecBoard implements multiple security layers including multi-factor authentication (MFA), role-based access control (RBAC), session management, encrypted data storage, CSRF protection, XSS prevention, and comprehensive audit logging. All security best practices are followed.')
                },
                {
                    'question': _('Does SecBoard support multi-factor authentication?'),
                    'answer': _('Yes, SecBoard supports multi-factor authentication to enhance account security and prevent unauthorized access.')
                },
                {
                    'question': _('How does role-based access control work?'),
                    'answer': _('SecBoard uses Django\'s permission system with custom groups and permissions. Administrators can create roles, assign specific permissions to each role, and control what users can see and do based on their role assignments.')
                },
                {
                    'question': _('Can I control who has access to specific modules?'),
                    'answer': _('Yes, access to each module and feature can be controlled through the permission system. You can grant or revoke access at a granular level.')
                },
            ]
        },
        {
            'category': _('Features & Modules'),
            'icon': 'fa-puzzle-piece',
            'color': 'info',
            'questions': [
                {
                    'question': _('What modules are included in SecBoard?'),
                    'answer': _('SecBoard includes 11 main modules: Security Awareness Training, User Cabinet, Document Management, Risk Assessment, Asset Management, Key/Certificate Management, Incident Management, Standards & Compliance, Access Management, SOC (Security Operations Center), and Phishing Simulation (GoPhish integration).')
                },
                {
                    'question': _('Can I use only specific modules?'),
                    'answer': _('Yes, SecBoard is modular. You can enable or disable specific modules based on your organization\'s needs.')
                },
                {
                    'question': _('Does SecBoard integrate with existing security tools?'),
                    'answer': _('Yes, SecBoard can integrate with various security tools. Currently, it supports integration with Wazuh (SIEM), GoPhish (phishing simulation), and provides REST APIs for custom integrations.')
                },
                {
                    'question': _('What compliance standards does SecBoard support?'),
                    'answer': _('SecBoard supports multiple compliance frameworks including ISO 27001, ISO 27002, NIST Cybersecurity Framework, PCI DSS, and GDPR. The Standards & Compliance module includes templates and controls for these frameworks.')
                },
            ]
        },
        {
            'category': _('Risk Assessment'),
            'icon': 'fa-exclamation-triangle',
            'color': 'warning',
            'questions': [
                {
                    'question': _('How does risk assessment work in SecBoard?'),
                    'answer': _('SecBoard provides a comprehensive risk assessment module that allows you to identify assets, threats, and vulnerabilities, calculate risk levels using customizable matrices, implement risk treatment plans, and track risk over time with detailed reporting.')
                },
                {
                    'question': _('Can I customize risk matrices?'),
                    'answer': _('Yes, you can fully customize risk assessment methodologies, impact scales, likelihood scales, and risk matrices to match your organization\'s risk management framework.')
                },
                {
                    'question': _('Does SecBoard support threat modeling?'),
                    'answer': _('Yes, the Risk Assessment module includes threat modeling capabilities where you can identify potential threats to your assets and assess their impact.')
                },
            ]
        },
        {
            'category': _('Training & Awareness'),
            'icon': 'fa-graduation-cap',
            'color': 'danger',
            'questions': [
                {
                    'question': _('What training features are available?'),
                    'answer': _('SecBoard includes a complete Learning Management System (LMS) with interactive courses, quizzes, certification tracking, progress monitoring, and customizable training materials. You can create custom courses or use pre-built security awareness content.')
                },
                {
                    'question': _('Can I create custom training courses?'),
                    'answer': _('Yes, the Training module allows you to create custom courses with text, images, videos, and interactive quizzes. You can organize content into modules and track learner progress.')
                },
                {
                    'question': _('Does SecBoard support phishing simulation?'),
                    'answer': _('Yes, through GoPhish integration, you can run phishing simulation campaigns, create custom email templates and landing pages, and track user responses to improve security awareness.')
                },
            ]
        },
        {
            'category': _('Incident Management'),
            'icon': 'fa-bug',
            'color': 'secondary',
            'questions': [
                {
                    'question': _('How does incident management work?'),
                    'answer': _('The Incident Management module provides a complete workflow for handling security incidents including incident registration, classification, investigation tracking, escalation procedures, remediation actions, and post-incident reporting.')
                },
                {
                    'question': _('Can I customize incident workflows?'),
                    'answer': _('Yes, you can customize incident types, severity levels, status workflows, escalation rules, and notification procedures to match your incident response plan.')
                },
                {
                    'question': _('Does SecBoard track incident metrics?'),
                    'answer': _('Yes, the system provides comprehensive incident analytics including response times, resolution rates, incident trends, and compliance metrics.')
                },
            ]
        },
        {
            'category': _('Installation & Setup'),
            'icon': 'fa-download',
            'color': 'dark',
            'questions': [
                {
                    'question': _('What are the system requirements?'),
                    'answer': _('SecBoard requires Python 3.8+, Django 5.0+, a database (PostgreSQL recommended, SQLite for development), Redis for caching and Celery tasks, and a modern web browser. Minimum 2GB RAM and 10GB disk space recommended.')
                },
                {
                    'question': _('How do I install SecBoard?'),
                    'answer': _('Installation involves cloning the repository, installing Python dependencies, configuring the database, running migrations, creating a superuser, and starting the Django development server. Detailed installation instructions are provided in the documentation.')
                },
                {
                    'question': _('Can SecBoard be deployed in production?'),
                    'answer': _('Yes, SecBoard can be deployed in production using WSGI servers like Gunicorn or uWSGI with Nginx as a reverse proxy. It includes production-ready security settings and can be containerized with Docker.')
                },
                {
                    'question': _('Is there a demo available?'),
                    'answer': _('Yes, you can access a live demo at demo.secboard.online to explore the platform\'s features before installation.')
                },
            ]
        },
        {
            'category': _('Support & Community'),
            'icon': 'fa-users',
            'color': 'primary',
            'questions': [
                {
                    'question': _('Where can I get help?'),
                    'answer': _('You can get help through the project documentation, GitHub issues, community forums, or by contacting the SecBoard team directly via email or Telegram.')
                },
                {
                    'question': _('How can I contribute to SecBoard?'),
                    'answer': _('Contributions are welcome! You can contribute by submitting bug reports, feature requests, pull requests, documentation improvements, or translations. Check the GitHub repository for contribution guidelines.')
                },
                {
                    'question': _('Is commercial support available?'),
                    'answer': _('Yes, commercial support, customization services, and consulting are available. Contact the SecBoard team for more information.')
                },
                {
                    'question': _('What languages does SecBoard support?'),
                    'answer': _('SecBoard currently supports English, Ukrainian, and Russian. The platform is built with internationalization support, making it easy to add new languages.')
                },
            ]
        },
    ]
    
    context = {
        'faq_categories': faq_categories,
        'page_title': _('Frequently Asked Questions'),
        'meta_description': _('Find answers to frequently asked questions about SecBoard - the comprehensive information security management platform. Learn about features, installation, security, and more.'),
        'meta_keywords': _('SecBoard FAQ, security questions, information security help, cybersecurity platform questions, SecBoard support'),
    }
    
    return render(request, 'app_conf/faq.html', context)


def knowledge_base_list(request):
    """Public Knowledge Base - list of articles"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_knowledge_base:
        raise Http404()

    from .models import KnowledgeBaseArticle, KnowledgeBaseCategory
    from django.db.models import Q
    
    # Get filter parameters
    category_slug = request.GET.get('category')
    search_query = request.GET.get('q')
    article_type = request.GET.get('type')
    priority = request.GET.get('priority')
    
    # Base queryset - only published articles
    articles = KnowledgeBaseArticle.objects.filter(is_published=True).select_related('category', 'author')
    
    # Apply filters
    if category_slug:
        articles = articles.filter(category__slug=category_slug)
    
    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query) |
            Q(summary__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(tags__icontains=search_query)
        )
    
    if article_type:
        articles = articles.filter(article_type=article_type)
    
    if priority:
        articles = articles.filter(priority=priority)
    
    # Get all active categories with article counts
    categories = KnowledgeBaseCategory.objects.filter(is_active=True).prefetch_related('articles')
    
    # Get featured articles
    featured_articles = KnowledgeBaseArticle.objects.filter(
        is_published=True, 
        is_featured=True
    ).select_related('category')[:3]
    
    # Get most viewed articles
    popular_articles = KnowledgeBaseArticle.objects.filter(
        is_published=True
    ).order_by('-views_count')[:5]
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(articles, 12)  # 12 articles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'featured_articles': featured_articles,
        'popular_articles': popular_articles,
        'current_category': category_slug,
        'search_query': search_query,
        'article_type': article_type,
        'priority': priority,
        'page_title': _('Security Knowledge Base'),
        'meta_description': _('Explore our comprehensive security knowledge base with articles about threats, protection methods, standards, and best practices.'),
        'meta_keywords': _('security knowledge base, cybersecurity articles, security threats, protection methods, security standards'),
    }
    
    return render(request, 'app_conf/knowledge_base_list.html', context)


def knowledge_base_detail(request, slug):
    """Public Knowledge Base - article detail"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_knowledge_base:
        raise Http404()

    from .models import KnowledgeBaseArticle
    from django.shortcuts import get_object_or_404
    
    article = get_object_or_404(
        KnowledgeBaseArticle.objects.select_related('category', 'author'),
        slug=slug,
        is_published=True
    )
    
    # Increment views count
    article.increment_views()
    
    # Get related articles
    related_articles = article.get_related_articles(limit=6)
    
    # Get next and previous articles in the same category
    next_article = KnowledgeBaseArticle.objects.filter(
        category=article.category,
        is_published=True,
        published_at__gt=article.published_at
    ).order_by('published_at').first()
    
    prev_article = KnowledgeBaseArticle.objects.filter(
        category=article.category,
        is_published=True,
        published_at__lt=article.published_at
    ).order_by('-published_at').first()
    
    context = {
        'article': article,
        'related_articles': related_articles,
        'next_article': next_article,
        'prev_article': prev_article,
        'page_title': article.title,
        'meta_description': article.meta_description or article.summary,
        'meta_keywords': article.meta_keywords or article.tags,
    }
    
    return render(request, 'app_conf/knowledge_base_detail.html', context)


def knowledge_base_category(request, slug):
    """Public Knowledge Base - category view"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_knowledge_base:
        raise Http404()

    from .models import KnowledgeBaseCategory
    from django.shortcuts import get_object_or_404
    
    category = get_object_or_404(
        KnowledgeBaseCategory,
        slug=slug,
        is_active=True
    )
    
    # Redirect to list view with category filter
    from django.shortcuts import redirect
    return redirect(f'/knowledge-base/?category={slug}')

@login_required
def get_mail_servers(request):
    """Get list of available mail servers"""
    try:
        servers = MailServer.objects.filter().values('id', 'name', 'smtp_host', 'smtp_port')
        
        servers_data = []
        for server in servers:
            servers_data.append({
                'id': server['id'],
                'name': server['name'],
                'smtp_host': server['smtp_host'],
                'smtp_port': server['smtp_port']
            })
        
        return JsonResponse({
            'status': 'success',
            'data': servers_data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def get_mail_accounts(request):
    """Get list of available mail accounts"""
    try:
        server_id = request.GET.get('server_id')
        
        if server_id:
            accounts = MailAccount.objects.filter(
                server_id=server_id, 
                is_active=True
            ).select_related('server').values(
                'id', 'username', 'server__name'
            )
        else:
            accounts = MailAccount.objects.filter(
                is_active=True
            ).select_related('server').values(
                'id', 'username', 'server__name'
            )
        
        accounts_data = []
        for account in accounts:
            accounts_data.append({
                'id': account['id'],
                'username': account['username'],
                'server_name': account['server__name']
            })
        
        return JsonResponse({
            'status': 'success',
            'data': accounts_data
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def contact(request):
    """Public Contact page with contact form"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_contact_page:
        raise Http404()

    if request.method == 'POST':
        # Anti-bot honeypot check
        honeypot = request.POST.get('website', '')
        if honeypot:
            # Bot detected - silently reject
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Bot detected in contact form from IP: {request.META.get('REMOTE_ADDR')}")
            messages.success(request, _('Thank you for your message! We will get back to you as soon as possible.'))
            return redirect('app_conf:contact')
        
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save(commit=False)
            
            # Get IP address and user agent
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                contact_message.ip_address = x_forwarded_for.split(',')[0]
            else:
                contact_message.ip_address = request.META.get('REMOTE_ADDR')
            
            contact_message.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            contact_message.save()
            
            # Get contact settings
            try:
                contact_settings = ContactSettings.get_settings()
            except:
                contact_settings = None
            
            # Get site settings for URLs
            if site_settings is None:
                try:
                    site_settings = SiteSettings.get_settings()
                except Exception:
                    site_settings = None
            
            # Send notification emails to selected Cabinet Users based on inquiry type
            recipient_emails = []
            
            if contact_settings:
                # Get recipients based on inquiry type (use the actual field value, not display name)
                recipients = contact_settings.get_notification_recipients_for_inquiry_type(
                    contact_message.subject_type
                )
                
                for recipient in recipients:
                    if hasattr(recipient, 'user') and recipient.user and recipient.user.email:
                        recipient_emails.append(recipient.user.email)
                    elif hasattr(recipient, 'email'):
                        recipient_emails.append(recipient.email)
            
            # Send notification email if we have recipients
            if recipient_emails:
                try:
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    # Remove duplicates
                    recipient_emails = list(set(recipient_emails))
                    
                    # Log for debugging
                    logger.info(f"Sending contact notification to {len(recipient_emails)} recipients: {recipient_emails}")
                    logger.info(f"Inquiry type: {contact_message.subject_type}")
                    
                    # Use Auto-Reply Email Account for sending notifications
                    if contact_settings and contact_settings.contact_auto_reply_account:
                        mail_account = contact_settings.contact_auto_reply_account
                        
                        admin_url = site_settings.get_site_url() if site_settings else 'https://secboard.online'
                        
                        # Prepare notification email content
                        notification_subject = f"[SecBoard Contact] {contact_message.subject}"
                        notification_body = (
                            f"New contact form submission:\n\n"
                            f"From: {contact_message.name} <{contact_message.email}>\n"
                            f"Company: {contact_message.company or 'N/A'}\n"
                            f"Phone: {contact_message.phone or 'N/A'}\n"
                            f"Type: {contact_message.get_subject_type_display()}\n\n"
                            f"Subject: {contact_message.subject}\n\n"
                            f"Message:\n{contact_message.message}\n\n"
                            f"---\n"
                            f"You can view and manage this message in Admin Panel:\n"
                            f"{admin_url}/secboard_admin/app_conf/contactmessage/"
                        )
                        
                        logger.info(f"Using mail account: {mail_account.username}")
                        
                        # Send email using the configured mail account
                        import smtplib
                        from email.mime.text import MIMEText
                        from email.mime.multipart import MIMEMultipart
                        
                        for recipient_email in recipient_emails:
                            try:
                                msg = MIMEMultipart()
                                msg['From'] = mail_account.username
                                msg['To'] = recipient_email
                                msg['Subject'] = notification_subject
                                msg.attach(MIMEText(notification_body, 'plain'))
                                
                                # Connect to SMTP server
                                if mail_account.server.use_ssl:
                                    import ssl
                                    context = ssl.create_default_context()
                                    context.check_hostname = False
                                    context.verify_mode = ssl.CERT_NONE
                                    smtp = smtplib.SMTP_SSL(
                                        host=mail_account.server.smtp_host,
                                        port=mail_account.server.smtp_port,
                                        context=context
                                    )
                                else:
                                    smtp = smtplib.SMTP(
                                        host=mail_account.server.smtp_host,
                                        port=mail_account.server.smtp_port
                                    )
                                    if mail_account.server.use_tls:
                                        smtp.starttls()
                                
                                # Login and send
                                smtp.login(mail_account.username, mail_account.password)
                                smtp.send_message(msg)
                                smtp.quit()
                                
                                logger.info(f"Notification sent successfully to {recipient_email}")
                            except Exception as email_error:
                                logger.error(f"Failed to send notification to {recipient_email}: {str(email_error)}")
                        
                        logger.info(f"Contact notification process completed for {len(recipient_emails)} recipients")
                    else:
                        logger.warning("No contact auto-reply account configured. Cannot send notifications.")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send contact notification: {str(e)}")
                    logger.error(f"Recipients: {recipient_emails}")
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"No recipients found for contact message type: {contact_message.subject_type}")
                logger.warning(f"Contact settings: {contact_settings}")
            
            # Send auto-reply to user
            if contact_settings and contact_settings.enable_contact_auto_reply and contact_settings.contact_auto_reply_account:
                try:
                    mail_account = contact_settings.contact_auto_reply_account
                    
                    # Use custom subject or default
                    auto_reply_subject = contact_settings.auto_reply_subject
                    
                    # Use custom body with variable substitution
                    auto_reply_body = contact_settings.auto_reply_body.format(
                        name=contact_message.name,
                        subject=contact_message.subject
                    )
                    
                    # Send email using the configured mail account
                    import smtplib
                    from email.mime.text import MIMEText
                    from email.mime.multipart import MIMEMultipart
                    
                    msg = MIMEMultipart()
                    msg['From'] = mail_account.username
                    msg['To'] = contact_message.email
                    msg['Subject'] = auto_reply_subject
                    msg.attach(MIMEText(auto_reply_body, 'plain'))
                    
                    # Connect to SMTP server
                    if mail_account.server.use_ssl:
                        import ssl
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        smtp = smtplib.SMTP_SSL(
                            host=mail_account.server.smtp_host,
                            port=mail_account.server.smtp_port,
                            context=context
                        )
                    else:
                        smtp = smtplib.SMTP(
                            host=mail_account.server.smtp_host,
                            port=mail_account.server.smtp_port
                        )
                        if mail_account.server.use_tls:
                            smtp.starttls()
                    
                    # Login and send
                    smtp.login(mail_account.username, mail_account.password)
                    smtp.send_message(msg)
                    smtp.quit()
                except Exception as e:
                    # Log error but don't show to user
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send contact auto-reply: {str(e)}")
            
            messages.success(request, _('Thank you for your message! We will get back to you as soon as possible.'))
            return redirect('app_conf:contact')
    else:
        form = ContactForm()
    
    # Get contact settings for contact information
    try:
        contact_settings = ContactSettings.get_settings()
    except:
        contact_settings = None
    
    context = {
        'form': form,
        'contact_settings': contact_settings,
        'page_title': _('Contact Us'),
        'meta_description': _('Get in touch with SecBoard team. Send us your questions, feedback, or partnership inquiries. We are here to help with your information security needs.'),
        'meta_keywords': _('contact SecBoard, security platform support, get in touch, partnership, demo request'),
    }
    
    return render(request, 'app_conf/contact.html', context)


def partnership(request):
    """Public Partnership page describing cooperation opportunities"""
    
    try:
        site_settings = SiteSettings.get_settings()
    except Exception:
        site_settings = None

    if site_settings and not site_settings.show_partnership_page:
        raise Http404()

    partnership_types = [
        {
            'type': 'implementation',
            'title': _('Implementation Partner'),
            'icon': 'fa-cogs',
            'color': 'primary',
            'description': _('Organizations ready to implement SecBoard for testing and practical application in their infrastructure.'),
            'benefits': [
                _('Early access to new features and modules'),
                _('Direct technical support from development team'),
                _('Opportunity to influence product roadmap'),
                _('Free technical consulting during implementation'),
                _('Your feedback shapes the platform development'),
                _('Case study and success story publication'),
            ],
            'requirements': [
                _('Active information security program'),
                _('Technical team capable of platform deployment'),
                _('Willingness to provide regular feedback'),
                _('Participation in beta testing programs'),
            ]
        },
        {
            'type': 'reseller',
            'title': _('IT Partner & Reseller'),
            'icon': 'fa-handshake',
            'color': 'success',
            'description': _('IT companies ready to act as representatives and provide full support on partnership terms.'),
            'benefits': [
                _('Attractive partner discount programs'),
                _('Marketing materials and sales support'),
                _('Technical training and certification'),
                _('Co-branding opportunities'),
                _('Priority technical support channel'),
                _('Revenue sharing model'),
                _('Lead generation support'),
            ],
            'requirements': [
                _('Experience in information security solutions'),
                _('Customer base in target markets'),
                _('Technical support capabilities'),
                _('Sales and marketing resources'),
            ]
        },
        {
            'type': 'development',
            'title': _('Development Partner'),
            'icon': 'fa-code',
            'color': 'info',
            'description': _('Development teams and contributors interested in platform enhancement and feature development.'),
            'benefits': [
                _('Access to complete source code'),
                _('Collaboration on new modules and features'),
                _('Recognition in contributor community'),
                _('Direct communication with core team'),
                _('Opportunity to commercialize custom modules'),
            ],
            'requirements': [
                _('Python/Django development experience'),
                _('Understanding of information security concepts'),
                _('Commitment to code quality standards'),
                _('Open source contribution experience (preferred)'),
            ]
        },
        {
            'type': 'integration',
            'title': _('Integration Partner'),
            'icon': 'fa-plug',
            'color': 'warning',
            'description': _('Technology vendors interested in integrating their solutions with SecBoard platform.'),
            'benefits': [
                _('API documentation and integration support'),
                _('Joint solution marketing'),
                _('Technical integration assistance'),
                _('Co-development of integration modules'),
                _('Visibility in partner ecosystem'),
            ],
            'requirements': [
                _('Compatible product or service offering'),
                _('API or integration capabilities'),
                _('Technical resources for integration'),
                _('Mutual customer benefit'),
            ]
        },
    ]
    
    context = {
        'partnership_types': partnership_types,
        'page_title': _('Partnership & Collaboration'),
        'meta_description': _('Join SecBoard partnership program. Implementation partners, IT companies, development teams, and technology vendors - explore collaboration opportunities in developing and promoting our information security platform.'),
        'meta_keywords': _('SecBoard partnership, IT partner program, implementation partner, reseller program, development collaboration, integration partnership'),
    }
    
    return render(request, 'app_conf/partnership.html', context)


def license_activate(request):
    """
    View для активації ліцензії через веб-інтерфейс
    """
    from app_conf.license_manager import LicenseActivator
    from app_conf.hardware_binding import HardwareFingerprint
    
    error_message = None
    success_message = None
    server_id = HardwareFingerprint.get_server_id().strip()  # Server ID = хеш(Hardware ID + HTTP_HOST)
    
    # Перевірка довжини Server ID (має бути 64 символи для SHA256)
    if len(server_id) != 64:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Server ID has wrong length: {len(server_id)} (expected 64). Value: {server_id[:32]}...")
        # Обрізати до 64 символів якщо занадто довгий
        if len(server_id) > 64:
            server_id = server_id[:64]
            logger.warning(f"Server ID truncated to 64 characters")
    
    hardware_info = HardwareFingerprint.get_fingerprint_info()
    
    license_data = None
    # enabled_modules = None  # Disabled
    
    if request.method == 'POST':
        license_key = request.POST.get('license_key', '').strip()
        
        if not license_key:
            error_message = _("Please enter a license key")
        else:
            # Спроба активації
            success, license_obj, error = LicenseActivator.activate_license(license_key, request)
            
            if success:
                success_message = _("License activated successfully! Please restart the server.")
                # Отримуємо дані ліцензії для відображення
                try:
                    # from app_conf.license_manager import ModuleAccessController  # Disabled
                    from django.utils import timezone
                    from datetime import datetime
                    
                    license_data = license_obj.get_license_data()
                    if license_data:
                        # Створюємо копію для безпечної модифікації
                        license_data = dict(license_data)
                        # Джерело (Source): у нових ключах — у підписаному payload; у старих — з API сервера ліцензій
                        if not (license_data.get('source') or '').strip():
                            from app_conf.license_crypto import LicenseKeyFormatter
                            from app_conf.license_server_api import LicenseServerAPI
                            clean_key = LicenseKeyFormatter.normalize_license_key(license_key)
                            _ok, vd = LicenseServerAPI.validate_online(clean_key)
                            if vd:
                                src = (vd.get('source') or '').strip()
                                if not src and isinstance(vd.get('license_data'), dict):
                                    src = (vd['license_data'].get('source') or '').strip()
                                if src:
                                    license_data['source'] = src
                        # Обчислюємо дні до закінчення
                        expiration_str = license_data.get('expiration_date')
                        if expiration_str:
                            try:
                                expiration_date = datetime.strptime(expiration_str, '%Y-%m-%d').date()
                                today = timezone.now().date()
                                days_remaining = (expiration_date - today).days
                                license_data['days_remaining'] = days_remaining
                            except Exception as date_error:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Error calculating days remaining: {str(date_error)}")
                    
                    # Отримуємо список увімкнених модулів - DISABLED
                    # enabled_modules = ModuleAccessController.get_enabled_modules(license_obj)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error getting license data for display: {str(e)}")
            else:
                error_message = error or _("License activation failed")
    
    context = {
        'hardware_id': server_id,  # Передаємо Server ID (для сумісності з шаблоном використовуємо hardware_id)
        'hardware_info': hardware_info,
        'error_message': error_message,
        'success_message': success_message,
        'license_data': license_data,
        # 'enabled_modules': enabled_modules,  # Disabled
    }
    
    return render(request, 'app_conf/license_activate.html', context)
