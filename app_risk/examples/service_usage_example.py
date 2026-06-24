# SecBoard/app_risk/examples/service_usage_example.py

"""
Example of using the new refactored report services.
This demonstrates how to use the service layer for report generation.
"""

from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from ..services.report_service import ReportService
from ..services.report_config import ReportConfig
from ..services.report_data_service import ReportDataService
from ..services.report_generator_factory import ReportGeneratorFactory
from ..services.report_validators import validate_report_config


def example_basic_report_generation():
    """Example: Basic report generation"""
    
    # Get user (in real code, this would come from request)
    user = User.objects.first()  # Replace with actual user
    if not user:
        print("No users found. Please create a user first.")
        return
    
    # Create report configuration
    config = ReportConfig(
        report_type='full',
        format='pdf',
        language='uk',
        start_date=timezone.now().date() - timedelta(days=30),
        end_date=timezone.now().date(),
        include_charts=True,
        include_detailed_tables=True
    )
    
    # Create report service
    report_service = ReportService(user)
    
    # Generate report
    result = report_service.generate_report(config)
    
    if result['success']:
        print(f"Report generated successfully!")
        print(f"Generation time: {result['generation_time']:.2f} seconds")
        print(f"Filename: {result['report']['filename']}")
        
        # Save to file (optional)
        with open(result['report']['filename'], 'wb') as f:
            f.write(result['report']['content'])
    else:
        print(f"Report generation failed: {result['errors']}")


def example_report_preview():
    """Example: Get report preview before generation"""
    
    user = User.objects.first()
    if not user:
        print("No users found.")
        return
    
    config = ReportConfig(
        report_type='summary',
        format='excel',
        language='uk'
    )
    
    report_service = ReportService(user)
    
    # Get preview
    preview_result = report_service.get_report_preview(config)
    
    if preview_result['success']:
        preview = preview_result['preview']
        print(f"Preview statistics:")
        print(f"- Total assets: {preview['statistics']['total_assets']}")
        print(f"- Estimated size: {preview['estimated_size']}")
        print(f"- Generation time estimate: {preview['generation_time_estimate']}")
        print(f"- Available formats: {preview['available_formats']}")
    else:
        print(f"Preview failed: {preview_result['errors']}")


def example_configuration_validation():
    """Example: Validate report configuration"""
    
    user = User.objects.first()
    if not user:
        print("No users found.")
        return
    
    # Create configuration with potential issues
    config = ReportConfig(
        report_type='invalid_type',  # This will cause validation error
        format='pdf',
        language='uk',
        start_date=timezone.now().date() + timedelta(days=10),  # Future date - warning
        end_date=timezone.now().date()
    )
    
    # Validate configuration
    validation_result = validate_report_config(config, user)
    
    print(f"Configuration valid: {validation_result['is_valid']}")
    if validation_result['errors']:
        print(f"Errors: {validation_result['errors']}")
    if validation_result['warnings']:
        print(f"Warnings: {validation_result['warnings']}")


def example_supported_formats():
    """Example: Check supported formats"""
    
    user = User.objects.first()
    if not user:
        print("No users found.")
        return
        
    report_service = ReportService(user)
    
    # Get all supported formats with availability
    formats = report_service.get_supported_formats()
    
    print("Supported formats:")
    for format_info in formats:
        status = "✓" if format_info['available'] else "✗"
        print(f"{status} {format_info['name']} ({format_info['format']}) - {format_info['description']}")


def example_report_templates():
    """Example: Use report templates"""
    
    user = User.objects.first()
    if not user:
        print("No users found.")
        return
        
    report_service = ReportService(user)
    
    # Get available templates
    templates = report_service.get_report_templates()
    
    print("Available templates:")
    for template in templates:
        print(f"- {template['name']}: {template['description']}")
        enabled_sections = [k for k, v in template['sections'].items() if v]
        print(f"  Sections: {', '.join(enabled_sections)}")


if __name__ == '__main__':
    # Run examples
    print("=== Basic Report Generation ===")
    example_basic_report_generation()
    
    print("\n=== Report Preview ===")
    example_report_preview()
    
    print("\n=== Configuration Validation ===")
    example_configuration_validation()
    
    print("\n=== Supported Formats ===")
    example_supported_formats()
    
    print("\n=== Report Templates ===")
    example_report_templates()