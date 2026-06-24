from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _, gettext, gettext_lazy as _lazy
from cryptography.fernet import Fernet
from django.conf import settings
import json
import base64
import logging

logger = logging.getLogger(__name__)


class FIMSettings(models.Model):
    """
    Global settings for FIM (File Integrity Monitoring) system
    """
    # Database management
    max_records = models.PositiveIntegerField(
        default=100000, 
        verbose_name=_("Maximum FIM Alerts"), 
        help_text=_("Maximum number of FIM alerts to keep. When exceeded, oldest records will be automatically deleted.")
    )
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Created by"))
    
    class Meta:
        verbose_name = _("FIM Settings")
        verbose_name_plural = _("FIM Settings")
    
    def __str__(self):
        return f"FIM Settings (Max Records: {self.max_records})"
    
    @classmethod
    def get_settings(cls):
        """Get or create FIM settings singleton"""
        settings, created = cls.objects.get_or_create(
            id=1,  # Single settings record
            defaults={'max_records': 100000}
        )
        return settings
    
    def cleanup_old_records(self):
        """Remove old FIM alerts when max_records limit is exceeded"""
        try:
            # Count current FIM alerts
            current_count = WazuhFIMAlert.objects.count()
            
            if current_count > self.max_records:
                # Calculate how many records to delete
                records_to_delete = current_count - self.max_records
                
                # Get IDs of oldest alerts to delete (ordered by timestamp)
                old_alert_ids = list(WazuhFIMAlert.objects.order_by('timestamp').values_list('id', flat=True)[:records_to_delete])
                
                # Delete the old alerts by ID
                deleted_count = WazuhFIMAlert.objects.filter(id__in=old_alert_ids).delete()[0]
                
                logger.info(f"FIM Settings: Deleted {deleted_count} old FIM alerts (limit: {self.max_records})")
                
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error cleaning up old FIM alerts: {str(e)}")
            return 0


class WazuhFIMAlert(models.Model):
    """
    Model to store FIM (File Integrity Monitoring) alerts from Wazuh
    """
    ALERT_TYPES = [
        ('added', 'File Added'),
        ('modified', 'File Modified'),
        ('deleted', 'File Deleted'),
        ('read', 'File Read'),
    ]
    
    SEVERITY_LEVELS = [
        (0, 'Emergency'),
        (1, 'Alert'),
        (2, 'Critical'),
        (3, 'Error'),
        (4, 'Warning'),
        (5, 'Notice'),
        (6, 'Info'),
        (7, 'Debug'),
    ]
    
    # Basic alert information
    alert_id = models.CharField(max_length=100, unique=True, help_text="Unique alert ID from Wazuh")
    rule_id = models.IntegerField(help_text="Wazuh rule ID")
    rule_name = models.CharField(max_length=255, help_text="Name of the triggered rule")
    level = models.IntegerField(choices=SEVERITY_LEVELS, help_text="Alert severity level")
    description = models.TextField(help_text="Alert description")
    
    # File information
    file_path = models.CharField(max_length=1000, help_text="Path to the monitored file")
    file_name = models.CharField(max_length=255, help_text="Name of the file")
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    file_hash_md5 = models.CharField(max_length=32, null=True, blank=True, help_text="MD5 hash of the file")
    file_hash_sha1 = models.CharField(max_length=40, null=True, blank=True, help_text="SHA1 hash of the file")
    file_hash_sha256 = models.CharField(max_length=64, null=True, blank=True, help_text="SHA256 hash of the file")
    
    # Alert type and status
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, help_text="Type of file operation")
    status = models.CharField(max_length=50, default='active', help_text="Alert status")
    
    # Agent and location information
    agent_id = models.CharField(max_length=50, help_text="Wazuh agent ID")
    agent_name = models.CharField(max_length=255, help_text="Name of the agent")
    agent_ip = models.GenericIPAddressField(help_text="IP address of the agent")
    
    # Client information
    client = models.ForeignKey('WebhookClient', on_delete=models.SET_NULL, null=True, blank=True, help_text="Webhook client that sent this alert")
    
    # Timestamps
    timestamp = models.DateTimeField(help_text="When the alert was generated")
    received_at = models.DateTimeField(default=timezone.now, help_text="When the alert was received by SecBoard")
    
    # Additional data
    raw_data = models.JSONField(default=dict, help_text="Raw JSON data from Wazuh")
    tags = models.JSONField(default=list, help_text="Tags associated with the alert")
    
    # Processing status
    processed = models.BooleanField(default=False, help_text="Whether the alert has been processed")
    processed_at = models.DateTimeField(null=True, blank=True, help_text="When the alert was processed")
    processed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, help_text="User who processed the alert")
    
    # Event processing details
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('confirmed', 'Confirmed Incident'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('ignored', 'Ignored'),
    ]
    
    processing_status = models.CharField(
        max_length=20, 
        choices=PROCESSING_STATUS_CHOICES, 
        default='pending',
        help_text="Current processing status of the alert"
    )
    
    # Investigation details
    investigation_notes = models.TextField(blank=True, help_text="Notes from investigation")
    false_positive_reason = models.CharField(max_length=255, blank=True, help_text="Reason for marking as false positive")
    resolution_notes = models.TextField(blank=True, help_text="Resolution details")
    
    # Escalation
    escalation_level = models.IntegerField(default=0, help_text="Escalation level (0 = no escalation)")
    escalation_reason = models.CharField(max_length=255, blank=True, help_text="Reason for escalation")
    escalated_to = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='escalated_alerts', help_text="User escalated to")
    
    # Risk assessment
    RISK_ASSESSMENT_CHOICES = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    risk_assessment = models.CharField(
        max_length=10,
        choices=RISK_ASSESSMENT_CHOICES,
        blank=True,
        help_text="Risk assessment of the alert"
    )
    
    # Impact assessment
    impact_description = models.TextField(blank=True, help_text="Description of potential impact")
    business_impact = models.CharField(max_length=255, blank=True, help_text="Business impact assessment")
    
    # Remediation
    remediation_actions = models.TextField(blank=True, help_text="Actions taken to remediate")
    prevention_measures = models.TextField(blank=True, help_text="Measures to prevent recurrence")
    
    # Follow-up
    requires_followup = models.BooleanField(default=False, help_text="Whether this alert requires follow-up")
    followup_date = models.DateTimeField(null=True, blank=True, help_text="Date for follow-up")
    followup_notes = models.TextField(blank=True, help_text="Follow-up notes")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Wazuh FIM Alert"
        verbose_name_plural = "Wazuh FIM Alerts"
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['agent_id']),
            models.Index(fields=['rule_id']),
            models.Index(fields=['level']),
            models.Index(fields=['processed']),
            models.Index(fields=['processing_status']),
            models.Index(fields=['escalation_level']),
            models.Index(fields=['risk_assessment']),
            models.Index(fields=['requires_followup']),
        ]
    
    def __str__(self):
        return f"FIM Alert {self.alert_id} - {self.file_name} ({self.alert_type})"
    
    def get_severity_display(self):
        """Get human-readable severity level"""
        return dict(self.SEVERITY_LEVELS).get(self.level, 'Unknown')
    
    def get_alert_type_display(self):
        """Get human-readable alert type"""
        return dict(self.ALERT_TYPES).get(self.alert_type, 'Unknown')
    
    def is_critical(self):
        """Check if alert is critical (level <= 3)"""
        return self.level <= 3
    
    def is_high_severity(self):
        """Check if alert is high severity (level <= 5)"""
        return self.level <= 5
    
    def get_processing_status_display(self):
        """Get human-readable processing status"""
        return dict(self.PROCESSING_STATUS_CHOICES).get(self.processing_status, 'Unknown')
    
    def get_risk_assessment_display(self):
        """Get human-readable risk assessment"""
        return dict(self.RISK_ASSESSMENT_CHOICES).get(self.risk_assessment, 'Not Assessed')
    
    def is_false_positive(self):
        """Check if alert is marked as false positive"""
        return self.processing_status == 'false_positive'
    
    def is_escalated(self):
        """Check if alert is escalated"""
        return self.escalation_level > 0
    
    def needs_followup(self):
        """Check if alert needs follow-up"""
        return self.requires_followup and self.followup_date and timezone.now() >= self.followup_date
    
    def get_client_info(self):
        """Get client information from direct relationship or fallback to IP matching"""
        try:
            # First try direct relationship
            if self.client:
                return {
                    'name': self.client.name,
                    'type': self.client.client_type,
                    'environment': self.client.environment,
                    'enabled': self.client.enabled,
                    'company_name': self.client.company.name if self.client.company else None
                }
            
            # Fallback: try to find a webhook client with matching IP
            # Note: This matches agent IP with client IP, which might not be correct
            # The agent IP is the IP of the monitored system, not the SecBoard server
            client = WebhookClient.objects.filter(ip_address=self.agent_ip).first()
            if client:
                return {
                    'name': client.name,
                    'type': client.client_type,
                    'environment': client.environment,
                    'enabled': client.enabled,
                    'company_name': client.company.name if client.company else None
                }
            
            # Additional fallback: try to find any enabled client
            # This is a temporary solution until all alerts have proper client links
            client = WebhookClient.objects.filter(enabled=True).first()
            if client:
                return {
                    'name': f"{client.name} (auto-matched)",
                    'type': client.client_type,
                    'environment': client.environment,
                    'enabled': client.enabled,
                    'company_name': client.company.name if client.company else None
                }
        except Exception as e:
            print(f"Error in get_client_info: {e}")
        return None


class WazuhAgent(models.Model):
    """
    Model to store information about Wazuh agents
    """
    agent_id = models.CharField(max_length=50, unique=True, help_text="Unique agent ID")
    agent_name = models.CharField(max_length=255, help_text="Agent name")
    agent_ip = models.GenericIPAddressField(help_text="Agent IP address")
    agent_version = models.CharField(max_length=50, null=True, blank=True, help_text="Agent version")
    platform = models.CharField(max_length=100, null=True, blank=True, help_text="Operating system platform")
    os_name = models.CharField(max_length=100, null=True, blank=True, help_text="Operating system name")
    os_version = models.CharField(max_length=100, null=True, blank=True, help_text="Operating system version")
    
    # Status information
    status = models.CharField(max_length=50, default='active', help_text="Agent status")
    last_seen = models.DateTimeField(null=True, blank=True, help_text="Last time agent was seen")
    first_seen = models.DateTimeField(default=timezone.now, help_text="First time agent was seen")
    
    # Additional metadata
    metadata = models.JSONField(default=dict, help_text="Additional agent metadata")
    
    class Meta:
        ordering = ['agent_name']
        verbose_name = "Wazuh Agent"
        verbose_name_plural = "Wazuh Agents"
    
    def __str__(self):
        return f"{self.agent_name} ({self.agent_id})"
    
    def get_alert_count(self):
        """Get total number of alerts from this agent"""
        return WazuhFIMAlert.objects.filter(agent_id=self.agent_id).count()
    
    def get_recent_alerts(self, days=7):
        """Get recent alerts from this agent"""
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return WazuhFIMAlert.objects.filter(
            agent_id=self.agent_id,
            timestamp__gte=since
        ).order_by('-timestamp')


class WebhookClient(models.Model):
    """
    Model to store webhook client configurations
    """
    CLIENT_TYPES = [
        ('wazuh', 'Wazuh Server'),
        ('siem', 'SIEM System'),
        ('monitoring', 'Monitoring Tool'),
        ('custom', 'Custom System'),
    ]
    
    ENVIRONMENTS = [
        ('production', 'Production'),
        ('staging', 'Staging'),
        ('development', 'Development'),
        ('testing', 'Testing'),
    ]
    
    # Basic client information
    client_id = models.CharField(max_length=100, unique=True, help_text="Unique client identifier")
    name = models.CharField(max_length=255, help_text="Client name")
    ip_address = models.CharField(max_length=255, help_text="Client IP address or domain name")
    port = models.IntegerField(default=8000, help_text="Client port")
    protocol = models.CharField(max_length=5, choices=[('http', 'HTTP'), ('https', 'HTTPS')], default='http', help_text="Protocol (HTTP/HTTPS)")
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPES, default='wazuh', help_text="Type of client system")
    environment = models.CharField(max_length=20, choices=ENVIRONMENTS, default='production', help_text="Environment")
    description = models.TextField(blank=True, help_text="Client description")
    
    # Company association
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Company this client belongs to"
    )
    
    # Status and metadata
    enabled = models.BooleanField(default=True, help_text="Whether the client is enabled")
    created_at = models.DateTimeField(default=timezone.now, help_text="When the client was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the client was last updated")
    
    # Additional metadata
    metadata = models.JSONField(default=dict, help_text="Additional client metadata")
    
    class Meta:
        ordering = ['name']
        verbose_name = "Webhook Client"
        verbose_name_plural = "Webhook Clients"
        indexes = [
            models.Index(fields=['client_id']),
            models.Index(fields=['enabled']),
            models.Index(fields=['client_type']),
            models.Index(fields=['environment']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.ip_address}:{self.port})"
    
    def get_webhook_url(self):
        """Generate webhook URL for this client"""
        # Don't show port for standard ports
        if (self.protocol == 'http' and self.port == 80) or (self.protocol == 'https' and self.port == 443):
            return f"{self.protocol}://{self.ip_address}/app_soc/webhook/{self.client_id}/fim/"
        else:
            return f"{self.protocol}://{self.ip_address}:{self.port}/app_soc/webhook/{self.client_id}/fim/"
    
    def get_auth_config(self):
        """Get authentication configuration for this client"""
        try:
            return self.webhookauthconfig
        except WebhookAuthConfig.DoesNotExist:
            return None


class WebhookAuthConfig(models.Model):
    """
    Model to store encrypted authentication configurations for webhook clients
    """
    AUTH_TYPES = [
        ('none', 'None'),
        ('basic', 'Basic Auth'),
        ('token', 'API Token'),
        ('custom', 'Custom Header'),
    ]
    
    # Foreign key to client
    client = models.OneToOneField(WebhookClient, on_delete=models.CASCADE, related_name='webhookauthconfig')
    
    # Authentication settings
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES, default='none', help_text="Type of authentication")
    enabled = models.BooleanField(default=True, help_text="Whether authentication is enabled")
    
    # Encrypted sensitive data
    encrypted_data = models.TextField(blank=True, help_text="Encrypted authentication data (JSON)")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, help_text="When the auth config was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the auth config was last updated")
    
    class Meta:
        verbose_name = "Webhook Authentication Configuration"
        verbose_name_plural = "Webhook Authentication Configurations"
    
    def __str__(self):
        return f"Auth Config for {self.client.name} ({self.get_auth_type_display()})"
    
    def get_auth_type_display(self):
        """Get human-readable auth type"""
        return dict(self.AUTH_TYPES).get(self.auth_type, 'Unknown')
    
    def _get_encryption_key(self):
        """Get encryption key from Django settings"""
        key = getattr(settings, 'WEBHOOK_ENCRYPTION_KEY', None)
        if not key:
            # Generate a new key if not set (for development)
            key = Fernet.generate_key()
            print(f"WARNING: WEBHOOK_ENCRYPTION_KEY not set. Generated key: {key.decode()}")
        return key
    
    def _encrypt_data(self, data):
        """Encrypt sensitive data"""
        if not data:
            return ""
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            json_data = json.dumps(data)
            encrypted_data = fernet.encrypt(json_data.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            raise ValidationError(f"Failed to encrypt data: {str(e)}")
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt sensitive data"""
        if not encrypted_data:
            return {}
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            raise ValidationError(f"Failed to decrypt data: {str(e)}")
    
    def set_auth_data(self, auth_data):
        """Set authentication data (will be encrypted)"""
        self.encrypted_data = self._encrypt_data(auth_data)
    
    def get_auth_data(self):
        """Get authentication data (decrypted)"""
        return self._decrypt_data(self.encrypted_data)
    
    def get_auth_headers(self):
        """Get HTTP headers for authentication"""
        if not self.enabled or self.auth_type == 'none':
            return {}
        
        auth_data = self.get_auth_data()
        headers = {}
        
        if self.auth_type == 'basic':
            username = auth_data.get('username', '')
            password = auth_data.get('password', '')
            if username and password:
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers['Authorization'] = f"Basic {credentials}"
        
        elif self.auth_type == 'token':
            token = auth_data.get('token', '')
            header_name = auth_data.get('header_name', 'Authorization')
            if token and header_name:
                headers[header_name] = token
        
        elif self.auth_type == 'custom':
            header_name = auth_data.get('header_name', '')
            header_value = auth_data.get('header_value', '')
            if header_name and header_value:
                headers[header_name] = header_value
        
        return headers
    
    def clean(self):
        """Validate the authentication configuration"""
        if self.enabled and self.auth_type != 'none':
            auth_data = self.get_auth_data()
            
            if self.auth_type == 'basic':
                if not auth_data.get('username') or not auth_data.get('password'):
                    raise ValidationError("Basic auth requires both username and password")
            
            elif self.auth_type == 'token':
                if not auth_data.get('token') or not auth_data.get('header_name'):
                    raise ValidationError("Token auth requires both token and header name")
            
            elif self.auth_type == 'custom':
                if not auth_data.get('header_name') or not auth_data.get('header_value'):
                    raise ValidationError("Custom auth requires both header name and value")


class AccessFIM(models.Model):
    """Model for controlling access to FIM (File Integrity Monitoring) dashboard"""
    group = models.ForeignKey('auth.Group', on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to FIM Dashboard"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit FIM alerts"))
    can_add = models.BooleanField(default=False, verbose_name=_("Can add new webhook clients"))
    can_delete = models.BooleanField(default=False, verbose_name=_("Can delete webhook clients"))
    can_configure = models.BooleanField(default=False, verbose_name=_("Can configure webhook settings"))
    companies = models.ManyToManyField('app_conf.Company', blank=True, related_name='access_fim', verbose_name=_("Companies"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Access to FIM")
        verbose_name_plural = _("Access to FIM")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit Access: {self.can_edit}"


class AnalysisConfig(models.Model):
    """Model for storing analysis configuration (e.g., VirusTotal API settings)"""
    HTTP_METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    
    DATA_TYPES = [
        ('file_hash_md5', _('File Hash - MD5')),
        ('file_hash_sha1', _('File Hash - SHA1')),
        ('file_hash_sha256', _('File Hash - SHA256')),
        ('ip_address', _('IP Address')),
        ('url', _('URL')),
        ('domain', _('Domain')),
        ('file_path', _('File Path')),
        ('file_name', _('File Name')),
        ('email', _('Email Address')),
        ('registry_key', _('Registry Key')),
        ('process_name', _('Process Name')),
        ('custom', _('Custom')),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Configuration Name"), help_text=_("Unique name for this analysis configuration"))
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='file_hash_sha256', verbose_name=_("Data Type"), help_text=_("Type of data to be analyzed"))
    method = models.CharField(max_length=10, choices=HTTP_METHODS, default='GET', verbose_name=_("HTTP Method"))
    url = models.URLField(max_length=500, verbose_name=_("API URL"), help_text=_("API endpoint URL (supports template variables like {{ json.sha256 }})"))
    
    # Encrypted credential storage
    encrypted_credential = models.TextField(blank=True, verbose_name=_("API Credential"), help_text=_("Encrypted API token or credential"))
    
    # Configuration settings
    enabled = models.BooleanField(default=True, verbose_name=_("Enabled"))
    timeout = models.PositiveIntegerField(default=30, verbose_name=_("Timeout (seconds)"))
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Created by"))

    class Meta:
        verbose_name = _("Analysis Configuration")
        verbose_name_plural = _("Analysis Configurations")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_data_type_display()}) - {self.method}"

    def _get_encryption_key(self):
        """Get encryption key from Django settings"""
        key = getattr(settings, 'WEBHOOK_ENCRYPTION_KEY', None)
        if not key:
            # Generate a new key if not set (for development)
            key = Fernet.generate_key()
            print(f"WARNING: WEBHOOK_ENCRYPTION_KEY not set. Generated key: {key.decode()}")
        return key

    def _encrypt_credential(self, credential):
        """Encrypt credential data"""
        if not credential:
            return ""
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(credential.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            print(f"Error encrypting credential: {e}")
            return ""

    def _decrypt_credential(self, encrypted_credential):
        """Decrypt credential data"""
        if not encrypted_credential:
            return ""
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = base64.b64decode(encrypted_credential.encode())
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data.decode()
        except Exception as e:
            print(f"Error decrypting credential: {e}")
            return ""

    def set_credential(self, credential):
        """Set and encrypt the credential"""
        self.encrypted_credential = self._encrypt_credential(credential)

    def get_credential(self):
        """Get and decrypt the credential"""
        return self._decrypt_credential(self.encrypted_credential)


class AnalysisResult(models.Model):
    """Model for storing analysis results"""
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('timeout', _('Timeout')),
    ]
    
    THREAT_LEVEL_CHOICES = [
        ('clean', _('Clean')),
        ('low', _('Low Risk')),
        ('medium', _('Medium Risk')),
        ('high', _('High Risk')),
        ('critical', _('Critical Risk')),
    ]
    
    # Analysis identification
    analysis_id = models.CharField(max_length=100, unique=True, verbose_name=_("Analysis ID"))
    alert = models.ForeignKey(WazuhFIMAlert, on_delete=models.CASCADE, related_name='analysis_results', verbose_name=_("FIM Alert"))
    analysis_config = models.ForeignKey(AnalysisConfig, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Analysis Configuration"))
    
    # Analysis data
    hash_type = models.CharField(max_length=10, verbose_name=_("Hash Type"))
    hash_value = models.CharField(max_length=128, verbose_name=_("Hash Value"))
    analysis_service = models.CharField(max_length=100, verbose_name=_("Analysis Service"))
    
    # Results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_("Status"))
    threat_level = models.CharField(max_length=20, choices=THREAT_LEVEL_CHOICES, null=True, blank=True, verbose_name=_("Threat Level"))
    detections = models.PositiveIntegerField(default=0, verbose_name=_("Detection Count"))
    total_engines = models.PositiveIntegerField(default=0, verbose_name=_("Total Engines"))
    detection_rate = models.FloatField(default=0.0, verbose_name=_("Detection Rate (%)"))
    
    # Detailed results
    raw_response = models.JSONField(null=True, blank=True, verbose_name=_("Raw API Response"))
    engine_results = models.JSONField(null=True, blank=True, verbose_name=_("Engine Results"))
    file_info = models.JSONField(null=True, blank=True, verbose_name=_("File Information"))
    behavior_analysis = models.JSONField(null=True, blank=True, verbose_name=_("Behavior Analysis"))
    
    # Metadata
    analysis_url = models.URLField(max_length=500, blank=True, verbose_name=_("Analysis URL"))
    permalink = models.URLField(max_length=500, blank=True, verbose_name=_("Permalink"))
    scan_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Scan Date"))
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))
    analyzed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Analyzed by"))
    
    class Meta:
        verbose_name = _("Analysis Result")
        verbose_name_plural = _("Analysis Results")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert', 'created_at']),
            models.Index(fields=['hash_value', 'hash_type']),
            models.Index(fields=['status', 'threat_level']),
        ]
    
    def __str__(self):
        return f"{self.analysis_service} - {self.hash_type.upper()}: {self.hash_value[:16]}... ({self.status})"
    
    def get_detection_rate_display(self):
        """Get formatted detection rate"""
        return f"{self.detection_rate:.1f}%"
    
    def get_threat_level_badge_class(self):
        """Get Bootstrap badge class for threat level"""
        classes = {
            'clean': 'bg-success',
            'low': 'bg-info',
            'medium': 'bg-warning',
            'high': 'bg-danger',
            'critical': 'bg-dark',
        }
        return classes.get(self.threat_level, 'bg-secondary')
    
    def get_status_badge_class(self):
        """Get Bootstrap badge class for status"""
        classes = {
            'pending': 'bg-warning',
            'completed': 'bg-success',
            'failed': 'bg-danger',
            'timeout': 'bg-secondary',
        }
        return classes.get(self.status, 'bg-secondary')
    
    def save(self, *args, **kwargs):
        # Calculate detection rate
        if self.total_engines > 0:
            self.detection_rate = (self.detections / self.total_engines) * 100
        super().save(*args, **kwargs)


class AIAnalysisResult(models.Model):
    """Model for storing AI analysis results"""
    
    RISK_LEVEL_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    CONFIDENCE_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
    ]
    
    ANALYSIS_TYPE_CHOICES = [
        ('threat_assessment', _('Threat Assessment')),
        ('risk_assessment', _('Risk Assessment')),
        ('behavioral_analysis', _('Behavioral Analysis')),
        ('comprehensive_analysis', _('Comprehensive Analysis')),
    ]
    
    # Analysis identification
    analysis_id = models.CharField(max_length=100, unique=True, verbose_name=_("AI Analysis ID"))
    alert = models.ForeignKey(WazuhFIMAlert, on_delete=models.CASCADE, related_name='ai_analysis_results', verbose_name=_("FIM Alert"))
    
    # AI Provider information
    ai_provider = models.CharField(max_length=50, verbose_name=_("AI Provider"))
    ai_model = models.CharField(max_length=100, verbose_name=_("AI Model"))
    analysis_type = models.CharField(max_length=50, choices=ANALYSIS_TYPE_CHOICES, verbose_name=_("Analysis Type"))
    analysis_depth = models.CharField(max_length=20, verbose_name=_("Analysis Depth"))
    temperature = models.FloatField(default=0.7, verbose_name=_("Temperature"))
    
    # Analysis results
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, verbose_name=_("Risk Level"))
    confidence = models.PositiveIntegerField(default=0, verbose_name=_("Confidence (%)"), help_text=_("Confidence level from 0 to 100"))
    summary = models.TextField(verbose_name=_("Summary"))
    detailed_analysis = models.TextField(blank=True, verbose_name=_("Detailed Analysis"))
    key_findings = models.JSONField(default=list, verbose_name=_("Key Findings"))
    recommendations = models.JSONField(default=list, verbose_name=_("Recommendations"))
    
    # Analysis context
    alert_context = models.JSONField(default=dict, verbose_name=_("Alert Context"))
    custom_prompt = models.TextField(blank=True, verbose_name=_("Custom Prompt"))
    
    # Configuration details
    included_info = models.JSONField(default=dict, verbose_name=_("Included Information"))
    analysis_config = models.JSONField(default=dict, verbose_name=_("Analysis Configuration"))
    
    # Full raw response
    raw_response = models.TextField(verbose_name=_("Raw AI Response"))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    analyzed_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, verbose_name=_("Analyzed By"))
    
    class Meta:
        verbose_name = _("AI Analysis Result")
        verbose_name_plural = _("AI Analysis Results")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"AI Analysis {self.analysis_id} for Alert {self.alert.alert_id} - {self.risk_level}"
    
    def get_risk_level_badge_class(self):
        """Get Bootstrap badge class for risk level"""
        classes = {
            'low': 'bg-success',
            'medium': 'bg-warning',
            'high': 'bg-danger',
            'critical': 'bg-dark',
        }
        return classes.get(self.risk_level, 'bg-secondary')
    
    def get_confidence_badge_class(self):
        """Get Bootstrap badge class for confidence"""
        classes = {
            'low': 'bg-warning',
            'medium': 'bg-info',
            'high': 'bg-success',
        }
        return classes.get(self.confidence, 'bg-secondary')


class OutgoingWebhook(models.Model):
    """Model for configuring outgoing webhooks to external systems like N8N"""
    
    TRIGGER_EVENTS = [
        ('new_alert', _('New FIM Alert')),
        ('high_risk_alert', _('High Risk Alert')),
        ('critical_alert', _('Critical Alert')),
        ('ai_analysis_complete', _('AI Analysis Complete')),
        ('analysis_complete', _('Hash Analysis Complete')),
        ('all_events', _('All Events')),
    ]
    
    HTTP_METHODS = [
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
    ]
    
    CONTENT_TYPES = [
        ('application/json', 'JSON'),
        ('application/x-www-form-urlencoded', 'Form Data'),
        ('text/plain', 'Plain Text'),
    ]
    
    # Basic configuration
    name = models.CharField(max_length=255, verbose_name=_("Webhook Name"), help_text=_("Descriptive name for this webhook"))
    enabled = models.BooleanField(default=True, verbose_name=_("Enabled"))
    url = models.URLField(max_length=500, verbose_name=_("Webhook URL"), help_text=_("Full URL where the webhook will be sent"))
    
    # HTTP configuration
    method = models.CharField(max_length=10, choices=HTTP_METHODS, default='POST', verbose_name=_("HTTP Method"))
    content_type = models.CharField(max_length=50, choices=CONTENT_TYPES, default='application/json', verbose_name=_("Content Type"))
    
    # Authentication (encrypted)
    auth_type = models.CharField(max_length=20, choices=WebhookAuthConfig.AUTH_TYPES, default='none', verbose_name=_("Authentication Type"))
    encrypted_auth_data = models.TextField(blank=True, verbose_name=_("Encrypted Auth Data"), help_text=_("Encrypted authentication credentials"))
    
    # Trigger configuration
    trigger_events = models.JSONField(default=list, verbose_name=_("Trigger Events"), help_text=_("List of events that will trigger this webhook"))
    
    # Payload configuration
    custom_payload_template = models.TextField(blank=True, verbose_name=_("Custom Payload Template"), 
        help_text=_("Jinja2 template for custom payload. Leave empty for default payload."))
    include_alert_data = models.BooleanField(default=True, verbose_name=_("Include Alert Data"))
    include_analysis_data = models.BooleanField(default=True, verbose_name=_("Include Analysis Data"))
    include_ai_analysis = models.BooleanField(default=False, verbose_name=_("Include AI Analysis"))
    
    # Headers configuration
    custom_headers = models.JSONField(default=dict, verbose_name=_("Custom Headers"), 
        help_text=_("Additional HTTP headers to send with webhook"))
    
    # Retry configuration
    max_retries = models.PositiveIntegerField(default=3, verbose_name=_("Max Retries"))
    retry_delay = models.PositiveIntegerField(default=5, verbose_name=_("Retry Delay (seconds)"))
    timeout = models.PositiveIntegerField(default=30, verbose_name=_("Timeout (seconds)"))
    
    # Company association (REQUIRED)
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.CASCADE,
        verbose_name=_("Company"),
        help_text=_("Company this webhook belongs to")
    )
    
    # FILTERING CRITERIA (all optional)
    # Filter by webhook clients
    filter_clients = models.ManyToManyField(
        'WebhookClient',
        blank=True,
        verbose_name=_("Filter by Clients"),
        help_text=_("Only send webhooks for alerts from these clients. Leave empty for all clients.")
    )
    
    # Filter by alert types
    filter_alert_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Filter by Alert Types"),
        help_text=_("Only send webhooks for these alert types (added, modified, deleted, read). Leave empty for all types.")
    )
    
    # Filter by severity levels
    filter_severity_levels = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Filter by Severity Levels"),
        help_text=_("Only send webhooks for these severity levels (0-7). Leave empty for all levels.")
    )
    
    # Filter by rule IDs
    filter_rule_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Filter by Rule IDs"),
        help_text=_("Only send webhooks for these Wazuh rule IDs. Leave empty for all rules.")
    )
    
    # Filter by agents
    filter_agent_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Filter by Agent IDs"),
        help_text=_("Only send webhooks for alerts from these agent IDs. Leave empty for all agents.")
    )
    
    # Filter by processing status
    filter_statuses = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Filter by Processing Status"),
        help_text=_("Only send webhooks for alerts with these processing statuses. Leave empty for all statuses.")
    )
    
    # Metadata
    description = models.TextField(blank=True, verbose_name=_("Description"))
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Created By"))
    
    # Statistics
    total_sent = models.PositiveIntegerField(default=0, verbose_name=_("Total Sent"))
    last_sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Sent At"))
    last_error = models.TextField(blank=True, verbose_name=_("Last Error"))
    
    class Meta:
        verbose_name = _("Outgoing Webhook")
        verbose_name_plural = _("Outgoing Webhooks")
        ordering = ['name']
        indexes = [
            models.Index(fields=['enabled']),
            models.Index(fields=['company']),
        ]
    
    def __str__(self):
        return f"{self.name} → {self.url}"
    
    def _get_encryption_key(self):
        """Get encryption key from Django settings"""
        key = getattr(settings, 'WEBHOOK_ENCRYPTION_KEY', None)
        if not key:
            # Generate a new key if not set (for development)
            key = Fernet.generate_key()
            print(f"WARNING: WEBHOOK_ENCRYPTION_KEY not set. Generated key: {key.decode()}")
        return key
    
    def _encrypt_auth_data(self, auth_data):
        """Encrypt authentication data"""
        if not auth_data:
            return ""
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            auth_json = json.dumps(auth_data)
            encrypted_data = fernet.encrypt(auth_json.encode())
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            print(f"Error encrypting auth data: {e}")
            return ""
    
    def _decrypt_auth_data(self):
        """Decrypt authentication data"""
        if not self.encrypted_auth_data:
            return {}
        
        try:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_data = base64.b64decode(self.encrypted_auth_data.encode())
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Error decrypting auth data: {e}")
            return {}
    
    def set_auth_data(self, auth_data):
        """Set and encrypt authentication data"""
        self.encrypted_auth_data = self._encrypt_auth_data(auth_data)
    
    def get_auth_data(self):
        """Get and decrypt authentication data"""
        return self._decrypt_auth_data()
    
    def should_trigger_for_event(self, event_type):
        """Check if this webhook should trigger for given event"""
        if not self.enabled:
            return False
        return event_type in self.trigger_events or 'all_events' in self.trigger_events
    
    def should_trigger_for_alert(self, alert, event_type):
        """Check if this webhook should trigger for given alert based on filters"""
        # First check event type
        if not self.should_trigger_for_event(event_type):
            return False
        
        # Check client filter
        if self.filter_clients.exists():
            if not alert.client or alert.client not in self.filter_clients.all():
                return False
        
        # Check alert type filter
        if self.filter_alert_types:
            if alert.alert_type not in self.filter_alert_types:
                return False
        
        # Check severity level filter
        if self.filter_severity_levels:
            if alert.level not in self.filter_severity_levels:
                return False
        
        # Check rule ID filter
        if self.filter_rule_ids:
            if alert.rule_id not in self.filter_rule_ids:
                return False
        
        # Check agent ID filter
        if self.filter_agent_ids:
            if alert.agent_id not in self.filter_agent_ids:
                return False
        
        # Check processing status filter
        if self.filter_statuses:
            if alert.processing_status not in self.filter_statuses:
                return False
        
        return True
    
    def build_payload(self, alert, analysis_results=None, ai_analysis=None):
        """Build webhook payload from alert and analysis data"""
        payload = {
            'event_type': 'fim_alert',
            'timestamp': timezone.now().isoformat(),
            'webhook_name': self.name,
        }
        
        if self.include_alert_data and alert:
            payload['alert'] = {
                'alert_id': alert.alert_id,
                'rule_name': alert.rule_name,
                'description': alert.description,
                'level': alert.level,
                'file_path': alert.file_path,
                'file_name': alert.file_name,
                'operation': alert.alert_type,
                'agent_name': alert.agent_name,
                'agent_ip': alert.agent_ip,
                'timestamp': alert.timestamp.isoformat(),
                'received_at': alert.received_at.isoformat(),
                'file_hash_md5': alert.file_hash_md5,
                'file_hash_sha1': alert.file_hash_sha1,
                'file_hash_sha256': alert.file_hash_sha256,
            }
        
        if self.include_analysis_data and analysis_results:
            payload['analysis_results'] = []
            for result in analysis_results:
                payload['analysis_results'].append({
                    'analysis_id': result.analysis_id,
                    'hash_type': result.hash_type,
                    'hash_value': result.hash_value,
                    'analysis_service': result.analysis_service,
                    'status': result.status,
                    'threat_level': result.threat_level,
                    'detections': result.detections,
                    'total_engines': result.total_engines,
                    'detection_rate': result.detection_rate,
                })
        
        if self.include_ai_analysis and ai_analysis:
            payload['ai_analysis'] = {
                'analysis_id': ai_analysis.analysis_id,
                'ai_provider': ai_analysis.ai_provider,
                'ai_model': ai_analysis.ai_model,
                'analysis_type': ai_analysis.analysis_type,
                'risk_level': ai_analysis.risk_level,
                'confidence': ai_analysis.confidence,
                'summary': ai_analysis.summary,
                'key_findings': ai_analysis.key_findings,
                'recommendations': ai_analysis.recommendations,
            }
        
        # Apply custom template if provided
        if self.custom_payload_template:
            try:
                from jinja2 import Template
                template = Template(self.custom_payload_template)
                custom_payload = template.render(
                    alert=alert,
                    analysis_results=analysis_results,
                    ai_analysis=ai_analysis,
                    payload=payload
                )
                # Try to parse as JSON, fallback to string
                try:
                    import json
                    payload = json.loads(custom_payload)
                except json.JSONDecodeError:
                    payload = {'custom_payload': custom_payload}
            except Exception as e:
                print(f"Error applying custom template: {e}")
        
        return payload
    
    def get_headers(self):
        """Get HTTP headers for the webhook request"""
        headers = {
            'Content-Type': self.content_type,
            'User-Agent': 'SecBoard-Webhook/1.0',
        }
        
        # Add authentication headers
        auth_data = self.get_auth_data()
        if self.auth_type == 'basic' and auth_data.get('username') and auth_data.get('password'):
            import base64
            credentials = f"{auth_data['username']}:{auth_data['password']}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f'Basic {encoded_credentials}'
        elif self.auth_type == 'token' and auth_data.get('token'):
            token_header = auth_data.get('header_name', 'Authorization')
            token_prefix = auth_data.get('token_prefix', 'Bearer')
            headers[token_header] = f'{token_prefix} {auth_data["token"]}'
        elif self.auth_type == 'custom' and auth_data.get('header_name') and auth_data.get('header_value'):
            headers[auth_data['header_name']] = auth_data['header_value']
        
        # Add custom headers
        if self.custom_headers:
            headers.update(self.custom_headers)
        
        return headers


class OutgoingWebhookLog(models.Model):
    """Model to log outgoing webhook attempts"""
    
    STATUS_CHOICES = [
        ('success', _('Success')),
        ('failed', _('Failed')),
        ('retry', _('Retry')),
    ]
    
    webhook = models.ForeignKey(OutgoingWebhook, on_delete=models.CASCADE, related_name='logs', verbose_name=_("Webhook"))
    alert = models.ForeignKey(WazuhFIMAlert, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Alert"))
    
    # Request details
    url = models.URLField(max_length=500, verbose_name=_("Request URL"))
    method = models.CharField(max_length=10, verbose_name=_("HTTP Method"))
    payload = models.JSONField(verbose_name=_("Payload"))
    headers = models.JSONField(default=dict, verbose_name=_("Headers"))
    
    # Response details
    status_code = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("HTTP Status Code"))
    response_body = models.TextField(blank=True, verbose_name=_("Response Body"))
    response_time_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Response Time (ms)"))
    
    # Status and error info
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name=_("Status"))
    error_message = models.TextField(blank=True, verbose_name=_("Error Message"))
    retry_count = models.PositiveIntegerField(default=0, verbose_name=_("Retry Count"))
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created At"))
    
    class Meta:
        verbose_name = _("Outgoing Webhook Log")
        verbose_name_plural = _("Outgoing Webhook Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['alert']),
        ]
    
    def __str__(self):
        return f"{self.webhook.name} → {self.status} ({self.created_at})"


class AutoStatusRule(models.Model):
    """
    Model for storing auto-status rules for FIM alerts
    """
    RULE_TYPE_CHOICES = [
        ('file_name', 'File Name'),
        ('file_path', 'File Path'),
        ('file_hash_md5', 'MD5 Hash'),
        ('file_hash_sha1', 'SHA1 Hash'),
        ('file_hash_sha256', 'SHA256 Hash'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('confirmed', 'Confirmed Incident'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('ignored', 'Ignored'),
    ]
    
    RISK_ASSESSMENT_CHOICES = [
        ('', 'Not Assessed'),
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES)
    rule_value = models.CharField(max_length=255)
    agent_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    risk_assessment = models.CharField(max_length=20, choices=RISK_ASSESSMENT_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['rule_type', 'rule_value', 'agent_name']
        indexes = [
            models.Index(fields=['rule_type', 'agent_name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_rule_type_display()}: {self.rule_value} ({self.agent_name}) → {self.get_status_display()}"


from tinymce.models import HTMLField


class FimDashboardGuide(models.Model):
    """Base Guide for FIM Dashboard. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("FIM Dashboard Guide")
        verbose_name_plural = _lazy("FIM Dashboard Guides")

    def __str__(self):
        return gettext("FIM Dashboard Guide")


class FimDashboardGuideTranslation(models.Model):
    """Per-country (language) translations of the FIM Dashboard Guide."""
    guide = models.ForeignKey(
        FimDashboardGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="fim_dashboard_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("FIM Dashboard Guide Translation")
        verbose_name_plural = _lazy("FIM Dashboard Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"
