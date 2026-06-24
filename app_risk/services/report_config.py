# SecBoard/app_risk/services/report_config.py

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.utils.translation import get_language


@dataclass
class ReportConfig:
    """Configuration class for report generation"""
    
    # Basic configuration
    report_type: str = 'full'  # 'full', 'summary', 'compliance'
    format: str = 'pdf'  # 'pdf', 'word'
    language: str = field(default_factory=lambda: get_language()[:2])
    
    # Filtering options
    company_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_deleted: bool = False
    
    # Report sections (for customizable reports)
    sections: Dict[str, bool] = field(default_factory=lambda: {
        'executive_summary': True,
        'risk_statistics': True,
        'vulnerability_analysis': True,
        'compliance_status': True,
        'risk_treatments': True,
        'recommendations': True,
        'appendices': True
    })
    
    # Sections configuration (for profile-based reports)
    sections_config: Dict[str, bool] = field(default_factory=dict)
    
    # Additional options
    notes: str = ''
    include_charts: bool = True
    include_detailed_tables: bool = True
    
    # Scheduling options (for scheduled reports)
    is_scheduled: bool = False
    schedule_name: str = ''
    schedule_description: str = ''
    
    # Email options
    send_email: bool = False
    email_recipients: List[str] = field(default_factory=list)
    email_subject: str = ''
    email_body: str = ''
    
    def __post_init__(self):
        """Post-initialization validation and defaults"""
        if self.start_date is None:
            self.start_date = timezone.now().date() - timedelta(days=365)
        
        if self.end_date is None:
            self.end_date = timezone.now().date()
        
        # Ensure dates are datetime objects
        if isinstance(self.start_date, str):
            self.start_date = datetime.strptime(self.start_date, '%Y-%m-%d').date()
        
        if isinstance(self.end_date, str):
            self.end_date = datetime.strptime(self.end_date, '%Y-%m-%d').date()
    
    @property
    def hash(self) -> str:
        """Generate hash for caching purposes"""
        config_dict = {
            'report_type': self.report_type,
            'format': self.format,
            'language': self.language,
            'company_id': self.company_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'include_deleted': self.include_deleted,
            'sections': self.sections,
            'include_charts': self.include_charts,
            'include_detailed_tables': self.include_detailed_tables,
        }
        
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_json.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'report_type': self.report_type,
            'format': self.format,
            'language': self.language,
            'company_id': self.company_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'include_deleted': self.include_deleted,
            'sections': self.sections,
            'notes': self.notes,
            'include_charts': self.include_charts,
            'include_detailed_tables': self.include_detailed_tables,
            'is_scheduled': self.is_scheduled,
            'schedule_name': self.schedule_name,
            'schedule_description': self.schedule_description,
            'send_email': self.send_email,
            'email_recipients': self.email_recipients,
            'email_subject': self.email_subject,
            'email_body': self.email_body,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReportConfig':
        """Create from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_request(cls, request) -> 'ReportConfig':
        """Create from Django request object"""
        if request.method == 'POST':
            if request.content_type == 'application/json':
                import json
                data = json.loads(request.body) if request.body else {}
            else:
                data = request.POST.dict()
        else:
            data = request.GET.dict()
        
        # Map request parameters to config fields
        config_data = {
            'report_type': data.get('reportType', data.get('report_type', 'full')),
            'format': data.get('reportFormat', data.get('format', 'pdf')),
            'language': data.get('reportLanguage', data.get('language', get_language()[:2])),
            'company_id': data.get('reportCompany', data.get('company_id', '')),
            'start_date': data.get('startDate', data.get('start_date')),
            'end_date': data.get('endDate', data.get('end_date')),
            'include_deleted': data.get('includeDeleted', data.get('include_deleted', False)),
            'notes': data.get('reportNotes', data.get('notes', '')),
            'include_charts': data.get('includeCharts', data.get('include_charts', True)),
            'include_detailed_tables': data.get('includeDetailedTables', data.get('include_detailed_tables', True)),
        }
        
        # Remove None values
        config_data = {k: v for k, v in config_data.items() if v is not None and v != ''}
        
        return cls(**config_data)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate report type
        valid_types = ['full', 'summary', 'compliance']
        if self.report_type not in valid_types:
            errors.append(f'Invalid report type: {self.report_type}')
        
        # Validate format
        valid_formats = ['pdf', 'word']
        if self.format not in valid_formats:
            errors.append(f'Invalid format: {self.format}')
        
        # Validate language
        valid_languages = ['uk', 'en', 'ru']
        if self.language not in valid_languages:
            errors.append(f'Invalid language: {self.language}')
        
        # Validate date range
        if self.start_date and self.end_date and self.start_date > self.end_date:
            errors.append('Start date cannot be after end date')
        
        # Validate sections
        if not any(self.sections.values()):
            errors.append('At least one report section must be selected')
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return len(self.validate()) == 0
    
    def get_cache_key(self, prefix: str = 'report') -> str:
        """Generate cache key for this configuration"""
        return f"{prefix}_{self.hash}"
    
    def __str__(self) -> str:
        return f"ReportConfig(type={self.report_type}, format={self.format}, language={self.language})"
    
    def __repr__(self) -> str:
        return self.__str__() 