"""
File and Security Validation Service
Provides comprehensive validation for file uploads and security checks
"""

import os
import magic
import hashlib
import mimetypes
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from pathlib import Path
import tempfile
import shutil
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .validation_service import ValidationError as CustomValidationError, ValidationSeverity, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about an uploaded file"""
    name: str
    size: int
    mime_type: str
    extension: str
    hash_md5: str
    hash_sha256: str
    is_safe: bool
    scan_results: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class SecurityScanResult:
    """Result of security scan"""
    is_safe: bool
    threats_found: List[str]
    warnings: List[str]
    scan_time: datetime
    scanner_version: str
    details: Dict[str, Any]


class FileSecurityValidator:
    """Comprehensive file security validator"""
    
    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.vbe', '.js', '.jse',
        '.wsf', '.wsh', '.msc', '.msi', '.msp', '.dll', '.application', '.gadget',
        '.msp', '.jar', '.ps1', '.ps1xml', '.ps2', '.ps2xml', '.psc1', '.psc2',
        '.msh', '.msh1', '.msh2', '.mshxml', '.msh1xml', '.msh2xml', '.scf', '.lnk',
        '.inf', '.reg', '.app', '.deb', '.pkg', '.dmg', '.iso', '.img', '.bin',
        '.run', '.action', '.apk', '.paf', '.workflow', '.service', '.socket',
        '.device', '.mount', '.automount', '.swap', '.target', '.path', '.timer',
        '.slice', '.scope'
    }
    
    # Allowed MIME types for different categories
    ALLOWED_MIME_TYPES = {
        'documents': [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/msword',
            'application/vnd.ms-excel',
            'application/vnd.ms-powerpoint',
            'text/plain',
            'text/csv',
            'text/rtf',
            'application/rtf'
        ],
        'images': [
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/tiff',
            'image/svg+xml',
            'image/webp'
        ],
        'archives': [
            'application/zip',
            'application/x-rar-compressed',
            'application/x-7z-compressed',
            'application/x-tar',
            'application/gzip'
        ]
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        'documents': 50 * 1024 * 1024,  # 50MB
        'images': 10 * 1024 * 1024,     # 10MB
        'archives': 100 * 1024 * 1024,  # 100MB
        'default': 25 * 1024 * 1024     # 25MB
    }
    
    # Virus signature patterns (simplified examples)
    VIRUS_SIGNATURES = [
        b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE',
        b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR',
        b'$MZ',  # PE header start
        b'!<arch>',  # AR archive header
    ]
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='secboard_upload_')
        self.quarantine_dir = os.path.join(self.temp_dir, 'quarantine')
        os.makedirs(self.quarantine_dir, exist_ok=True)
    
    def validate_file(self, uploaded_file: UploadedFile, 
                     allowed_categories: List[str] = None,
                     max_size: int = None,
                     perform_security_scan: bool = True) -> ValidationResult:
        """
        Comprehensive file validation
        
        Args:
            uploaded_file: Django UploadedFile object
            allowed_categories: List of allowed file categories
            max_size: Maximum file size in bytes
            perform_security_scan: Whether to perform security scanning
        
        Returns:
            ValidationResult with file validation results
        """
        try:
            errors = []
            warnings = []
            file_info = None
            
            # Basic file validation
            basic_validation = self._validate_basic_properties(uploaded_file, max_size)
            if basic_validation.errors:
                errors.extend(basic_validation.errors)
            if basic_validation.warnings:
                warnings.extend(basic_validation.warnings)
            
            # If basic validation failed, don't proceed
            if errors:
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    cleaned_data={}
                )
            
            # Create temporary file for analysis
            temp_file_path = self._create_temp_file(uploaded_file)
            
            try:
                # Get file information
                file_info = self._analyze_file(temp_file_path, uploaded_file)
                
                # Validate file type
                type_validation = self._validate_file_type(file_info, allowed_categories)
                if type_validation.errors:
                    errors.extend(type_validation.errors)
                if type_validation.warnings:
                    warnings.extend(type_validation.warnings)
                
                # Security scan
                if perform_security_scan:
                    security_validation = self._perform_security_scan(temp_file_path, file_info)
                    if security_validation.errors:
                        errors.extend(security_validation.errors)
                    if security_validation.warnings:
                        warnings.extend(security_validation.warnings)
                
                # Content validation
                content_validation = self._validate_file_content(temp_file_path, file_info)
                if content_validation.errors:
                    errors.extend(content_validation.errors)
                if content_validation.warnings:
                    warnings.extend(content_validation.warnings)
                
            finally:
                # Clean up temporary file
                self._cleanup_temp_file(temp_file_path)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                cleaned_data={'file_info': file_info.metadata if file_info else {}}
            )
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[CustomValidationError(
                    field='file',
                    message=_("File validation error occurred"),
                    severity=ValidationSeverity.CRITICAL,
                    code="file_validation_exception",
                    details={'exception': str(e)}
                )],
                warnings=[],
                cleaned_data={}
            )
    
    def _validate_basic_properties(self, uploaded_file: UploadedFile, 
                                 max_size: int = None) -> ValidationResult:
        """Validate basic file properties"""
        errors = []
        warnings = []
        
        # Check file name
        if not uploaded_file.name:
            errors.append(CustomValidationError(
                field='file',
                message=_("File name is required"),
                severity=ValidationSeverity.ERROR,
                code="no_filename"
            ))
        else:
            # Check for dangerous characters in filename
            dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/', '\0']
            if any(char in uploaded_file.name for char in dangerous_chars):
                errors.append(CustomValidationError(
                    field='file',
                    message=_("File name contains dangerous characters"),
                    severity=ValidationSeverity.ERROR,
                    code="dangerous_filename"
                ))
            
            # Check filename length
            if len(uploaded_file.name) > 255:
                errors.append(CustomValidationError(
                    field='file',
                    message=_("File name is too long (maximum 255 characters)"),
                    severity=ValidationSeverity.ERROR,
                    code="filename_too_long"
                ))
            
            # Check for dangerous extensions
            file_ext = Path(uploaded_file.name).suffix.lower()
            if file_ext in self.DANGEROUS_EXTENSIONS:
                errors.append(CustomValidationError(
                    field='file',
                    message=_("File extension '{ext}' is not allowed for security reasons").format(ext=file_ext),
                    severity=ValidationSeverity.ERROR,
                    code="dangerous_extension"
                ))
        
        # Check file size
        if uploaded_file.size == 0:
            errors.append(CustomValidationError(
                field='file',
                message=_("File is empty"),
                severity=ValidationSeverity.ERROR,
                code="empty_file"
            ))
        elif max_size and uploaded_file.size > max_size:
            errors.append(CustomValidationError(
                field='file',
                message=_("File size ({size}) exceeds maximum allowed size ({max_size})").format(
                    size=self._format_file_size(uploaded_file.size),
                    max_size=self._format_file_size(max_size)
                ),
                severity=ValidationSeverity.ERROR,
                code="file_too_large"
            ))
        
        # Warn about large files
        if uploaded_file.size > 10 * 1024 * 1024:  # 10MB
            warnings.append(CustomValidationError(
                field='file',
                message=_("Large file detected ({size}). Processing may take longer.").format(
                    size=self._format_file_size(uploaded_file.size)
                ),
                severity=ValidationSeverity.WARNING,
                code="large_file"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data={}
        )
    
    def _create_temp_file(self, uploaded_file: UploadedFile) -> str:
        """Create temporary file for analysis"""
        temp_file = tempfile.NamedTemporaryFile(
            dir=self.temp_dir,
            delete=False,
            suffix=Path(uploaded_file.name).suffix
        )
        
        # Copy file content
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        
        temp_file.close()
        return temp_file.name
    
    def _analyze_file(self, file_path: str, uploaded_file: UploadedFile) -> FileInfo:
        """Analyze file and extract information"""
        # Get file stats
        file_stat = os.stat(file_path)
        
        # Detect MIME type
        mime_type = magic.from_file(file_path, mime=True)
        
        # Get file extension
        extension = Path(uploaded_file.name).suffix.lower()
        
        # Calculate hashes
        md5_hash = self._calculate_file_hash(file_path, 'md5')
        sha256_hash = self._calculate_file_hash(file_path, 'sha256')
        
        # Extract metadata
        metadata = self._extract_metadata(file_path, mime_type)
        
        return FileInfo(
            name=uploaded_file.name,
            size=file_stat.st_size,
            mime_type=mime_type,
            extension=extension,
            hash_md5=md5_hash,
            hash_sha256=sha256_hash,
            is_safe=True,  # Will be updated by security scan
            scan_results={},
            metadata=metadata
        )
    
    def _calculate_file_hash(self, file_path: str, algorithm: str) -> str:
        """Calculate file hash"""
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _extract_metadata(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Extract file metadata"""
        metadata = {
            'created_at': timezone.now().isoformat(),
            'mime_type': mime_type,
            'size': os.path.getsize(file_path)
        }
        
        # Add file-specific metadata
        if mime_type.startswith('image/'):
            metadata.update(self._extract_image_metadata(file_path))
        elif mime_type == 'application/pdf':
            metadata.update(self._extract_pdf_metadata(file_path))
        
        return metadata
    
    def _extract_image_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract image metadata"""
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode
                }
        except Exception as e:
            logger.warning(f"Could not extract image metadata: {str(e)}")
            return {}
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF metadata"""
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                return {
                    'pages': len(reader.pages),
                    'encrypted': reader.is_encrypted,
                    'metadata': dict(reader.metadata) if reader.metadata else {}
                }
        except Exception as e:
            logger.warning(f"Could not extract PDF metadata: {str(e)}")
            return {}
    
    def _validate_file_type(self, file_info: FileInfo, 
                           allowed_categories: List[str] = None) -> ValidationResult:
        """Validate file type against allowed categories"""
        errors = []
        warnings = []
        
        if not allowed_categories:
            allowed_categories = ['documents', 'images']
        
        # Get all allowed MIME types
        allowed_mime_types = []
        for category in allowed_categories:
            if category in self.ALLOWED_MIME_TYPES:
                allowed_mime_types.extend(self.ALLOWED_MIME_TYPES[category])
        
        # Check MIME type
        if file_info.mime_type not in allowed_mime_types:
            errors.append(CustomValidationError(
                field='file',
                message=_("File type '{mime_type}' is not allowed").format(mime_type=file_info.mime_type),
                severity=ValidationSeverity.ERROR,
                code="invalid_mime_type",
                details={'mime_type': file_info.mime_type, 'allowed_types': allowed_mime_types}
            ))
        
        # Check file size against category limits
        for category in allowed_categories:
            if category in self.MAX_FILE_SIZES:
                max_size = self.MAX_FILE_SIZES[category]
                if file_info.size > max_size:
                    errors.append(CustomValidationError(
                        field='file',
                        message=_("File size exceeds limit for {category} files ({max_size})").format(
                            category=category,
                            max_size=self._format_file_size(max_size)
                        ),
                        severity=ValidationSeverity.ERROR,
                        code="category_size_exceeded"
                    ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data={}
        )
    
    def _perform_security_scan(self, file_path: str, file_info: FileInfo) -> ValidationResult:
        """Perform security scan on file"""
        errors = []
        warnings = []
        
        # Check for virus signatures
        virus_check = self._check_virus_signatures(file_path)
        if virus_check['threats_found']:
            errors.append(CustomValidationError(
                field='file',
                message=_("Security threat detected in file"),
                severity=ValidationSeverity.CRITICAL,
                code="security_threat",
                details={'threats': virus_check['threats_found']}
            ))
        
        # Check file header consistency
        header_check = self._check_file_header_consistency(file_path, file_info)
        if not header_check['is_consistent']:
            warnings.append(CustomValidationError(
                field='file',
                message=_("File header does not match extension"),
                severity=ValidationSeverity.WARNING,
                code="header_mismatch",
                details=header_check
            ))
        
        # Check for embedded content
        embedded_check = self._check_embedded_content(file_path, file_info)
        if embedded_check['suspicious_content']:
            warnings.append(CustomValidationError(
                field='file',
                message=_("File contains embedded content that may be suspicious"),
                severity=ValidationSeverity.WARNING,
                code="suspicious_embedded_content",
                details=embedded_check
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data={}
        )
    
    def _check_virus_signatures(self, file_path: str) -> Dict[str, Any]:
        """Check file for known virus signatures"""
        threats_found = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
                for signature in self.VIRUS_SIGNATURES:
                    if signature in content:
                        threats_found.append(f"Signature match: {signature[:20]}...")
        
        except Exception as e:
            logger.error(f"Error checking virus signatures: {str(e)}")
        
        return {
            'threats_found': threats_found,
            'scan_time': timezone.now().isoformat()
        }
    
    def _check_file_header_consistency(self, file_path: str, file_info: FileInfo) -> Dict[str, Any]:
        """Check if file header matches the extension"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(512)  # Read first 512 bytes
            
            # Common file signatures
            file_signatures = {
                '.pdf': [b'%PDF'],
                '.jpg': [b'\xff\xd8\xff'],
                '.jpeg': [b'\xff\xd8\xff'],
                '.png': [b'\x89PNG\r\n\x1a\n'],
                '.gif': [b'GIF87a', b'GIF89a'],
                '.zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
                '.docx': [b'PK\x03\x04'],  # DOCX is a ZIP file
                '.xlsx': [b'PK\x03\x04'],  # XLSX is a ZIP file
            }
            
            extension = file_info.extension.lower()
            if extension in file_signatures:
                expected_signatures = file_signatures[extension]
                is_consistent = any(header.startswith(sig) for sig in expected_signatures)
            else:
                is_consistent = True  # Unknown extension, assume consistent
            
            return {
                'is_consistent': is_consistent,
                'extension': extension,
                'header_hex': header[:16].hex()
            }
        
        except Exception as e:
            logger.error(f"Error checking file header: {str(e)}")
            return {'is_consistent': True, 'error': str(e)}
    
    def _check_embedded_content(self, file_path: str, file_info: FileInfo) -> Dict[str, Any]:
        """Check for suspicious embedded content"""
        suspicious_content = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Check for suspicious patterns
            suspicious_patterns = [
                b'javascript:',
                b'<script',
                b'eval(',
                b'document.write',
                b'<iframe',
                b'<object',
                b'<embed',
                b'shell32.dll',
                b'cmd.exe',
                b'powershell'
            ]
            
            for pattern in suspicious_patterns:
                if pattern in content.lower():
                    suspicious_content.append(pattern.decode('utf-8', errors='ignore'))
        
        except Exception as e:
            logger.error(f"Error checking embedded content: {str(e)}")
        
        return {
            'suspicious_content': suspicious_content,
            'scan_time': timezone.now().isoformat()
        }
    
    def _validate_file_content(self, file_path: str, file_info: FileInfo) -> ValidationResult:
        """Validate file content structure"""
        errors = []
        warnings = []
        
        try:
            # Validate based on file type
            if file_info.mime_type == 'application/pdf':
                pdf_validation = self._validate_pdf_content(file_path)
                errors.extend(pdf_validation['errors'])
                warnings.extend(pdf_validation['warnings'])
            
            elif file_info.mime_type.startswith('image/'):
                image_validation = self._validate_image_content(file_path)
                errors.extend(image_validation['errors'])
                warnings.extend(image_validation['warnings'])
            
            elif file_info.mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                office_validation = self._validate_office_content(file_path)
                errors.extend(office_validation['errors'])
                warnings.extend(office_validation['warnings'])
        
        except Exception as e:
            logger.error(f"Error validating file content: {str(e)}")
            warnings.append(CustomValidationError(
                field='file',
                message=_("Could not validate file content structure"),
                severity=ValidationSeverity.WARNING,
                code="content_validation_error"
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data={}
        )
    
    def _validate_pdf_content(self, file_path: str) -> Dict[str, List[CustomValidationError]]:
        """Validate PDF file content"""
        errors = []
        warnings = []
        
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                
                # Check if PDF is encrypted
                if reader.is_encrypted:
                    warnings.append(CustomValidationError(
                        field='file',
                        message=_("PDF file is encrypted"),
                        severity=ValidationSeverity.WARNING,
                        code="encrypted_pdf"
                    ))
                
                # Check for suspicious JavaScript
                for page_num, page in enumerate(reader.pages):
                    try:
                        if '/JS' in page.get_contents() or '/JavaScript' in page.get_contents():
                            warnings.append(CustomValidationError(
                                field='file',
                                message=_("PDF contains JavaScript on page {page}").format(page=page_num + 1),
                                severity=ValidationSeverity.WARNING,
                                code="pdf_javascript"
                            ))
                    except:
                        pass  # Skip if page content cannot be read
        
        except Exception as e:
            logger.error(f"Error validating PDF content: {str(e)}")
            errors.append(CustomValidationError(
                field='file',
                message=_("Invalid PDF file structure"),
                severity=ValidationSeverity.ERROR,
                code="invalid_pdf"
            ))
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_image_content(self, file_path: str) -> Dict[str, List[CustomValidationError]]:
        """Validate image file content"""
        errors = []
        warnings = []
        
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                # Check image dimensions
                if img.width > 10000 or img.height > 10000:
                    warnings.append(CustomValidationError(
                        field='file',
                        message=_("Image dimensions are very large ({width}x{height})").format(
                            width=img.width, height=img.height
                        ),
                        severity=ValidationSeverity.WARNING,
                        code="large_image_dimensions"
                    ))
                
                # Check for EXIF data
                if hasattr(img, '_getexif') and img._getexif():
                    warnings.append(CustomValidationError(
                        field='file',
                        message=_("Image contains EXIF metadata"),
                        severity=ValidationSeverity.WARNING,
                        code="image_exif_data"
                    ))
        
        except Exception as e:
            logger.error(f"Error validating image content: {str(e)}")
            errors.append(CustomValidationError(
                field='file',
                message=_("Invalid image file"),
                severity=ValidationSeverity.ERROR,
                code="invalid_image"
            ))
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_office_content(self, file_path: str) -> Dict[str, List[CustomValidationError]]:
        """Validate Office document content"""
        errors = []
        warnings = []
        
        try:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for macros
                if any('vbaProject.bin' in name for name in zip_file.namelist()):
                    warnings.append(CustomValidationError(
                        field='file',
                        message=_("Office document contains macros"),
                        severity=ValidationSeverity.WARNING,
                        code="office_macros"
                    ))
                
                # Check for external links
                for name in zip_file.namelist():
                    if 'externalLinks' in name:
                        warnings.append(CustomValidationError(
                            field='file',
                            message=_("Office document contains external links"),
                            severity=ValidationSeverity.WARNING,
                            code="office_external_links"
                        ))
                        break
        
        except Exception as e:
            logger.error(f"Error validating Office content: {str(e)}")
            errors.append(CustomValidationError(
                field='file',
                message=_("Invalid Office document"),
                severity=ValidationSeverity.ERROR,
                code="invalid_office_document"
            ))
        
        return {'errors': errors, 'warnings': warnings}
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Could not remove temporary file {file_path}: {str(e)}")
    
    def cleanup(self):
        """Clean up temporary directory"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.warning(f"Could not remove temporary directory {self.temp_dir}: {str(e)}")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup()


# Global file security validator instance
file_security_validator = FileSecurityValidator() 