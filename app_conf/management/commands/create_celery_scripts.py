import os
import platform
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from app_conf.models import CelerySettings


class Command(BaseCommand):
    help = 'Create platform-specific scripts for running Django with Celery'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='.',
            help='Directory to create scripts in (default: current directory)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing scripts'
        )
    
    def handle(self, *args, **options):
        output_dir = options['output_dir']
        force = options['force']
        
        # Load Celery settings
        try:
            celery_settings = CelerySettings.get_settings()
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not load Celery settings: {e}')
            )
            celery_settings = None
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Generate scripts for different platforms
        self.create_windows_scripts(output_dir, force, celery_settings)
        self.create_unix_scripts(output_dir, force, celery_settings)
        
        self.stdout.write(
            self.style.SUCCESS(f'Scripts created in {output_dir}')
        )
    
    def create_windows_scripts(self, output_dir, force, celery_settings):
        """Create Windows batch files"""
        
        # runserver_with_celery.bat
        bat_content = f"""@echo off
echo Starting Django development server with Celery...

REM Kill existing Celery processes
taskkill /f /im celery.exe 2>nul
wmic process where "name='python.exe' and commandline like '%%celery%%'" delete 2>nul

REM Start Celery worker in background
echo Starting Celery worker...
start /b python manage.py runserver_with_celery --celery-only --force-windows

REM Wait a moment for Celery to start
timeout /t 3 /nobreak >nul

REM Start Django development server
echo Starting Django development server...
python manage.py runserver

REM Cleanup on exit
echo Stopping Celery processes...
taskkill /f /im celery.exe 2>nul
wmic process where "name='python.exe' and commandline like '%%celery%%'" delete 2>nul
"""
        
        # celery_start.bat
        celery_start_content = """@echo off
echo Starting Celery processes...

REM Kill existing processes
taskkill /f /im celery.exe 2>nul
wmic process where "name='python.exe' and commandline like '%%celery%%'" delete 2>nul

REM Start Celery worker
echo Starting Celery worker...
start "Celery Worker" python manage.py celery_control start --worker-only --force-windows

REM Start Celery beat
echo Starting Celery beat...
start "Celery Beat" python manage.py celery_control start --beat-only --force-windows

echo Celery processes started.
echo Use celery_stop.bat to stop them.
"""
        
        # celery_stop.bat
        celery_stop_content = """@echo off
echo Stopping Celery processes...

taskkill /f /im celery.exe 2>nul
wmic process where "name='python.exe' and commandline like '%%celery%%'" delete 2>nul

echo Celery processes stopped.
"""
        
        # celery_status.bat
        celery_status_content = """@echo off
echo Checking Celery process status...

python manage.py celery_control status
"""
        
        # Write files
        scripts = {
            'runserver_with_celery.bat': bat_content,
            'celery_start.bat': celery_start_content,
            'celery_stop.bat': celery_stop_content,
            'celery_status.bat': celery_status_content,
        }
        
        for filename, content in scripts.items():
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath) and not force:
                self.stdout.write(
                    self.style.WARNING(f'Skipping {filename} (already exists, use --force to overwrite)')
                )
                continue
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created {filename}')
            )
    
    def create_unix_scripts(self, output_dir, force, celery_settings):
        """Create Unix shell scripts"""
        
        # runserver_with_celery.sh
        sh_content = f"""#!/bin/bash
echo "Starting Django development server with Celery..."

# Function to cleanup on exit
cleanup() {{
    echo "Stopping Celery processes..."
    pkill -f "celery.*worker"
    pkill -f "celery.*beat"
    exit 0
}}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Kill existing Celery processes
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Start Celery processes in background
echo "Starting Celery worker and beat..."
python manage.py runserver_with_celery --celery-only &
CELERY_PID=$!

# Wait a moment for Celery to start
sleep 3

# Start Django development server
echo "Starting Django development server..."
python manage.py runserver

# Cleanup will be called automatically on exit
"""
        
        # celery_start.sh
        celery_start_content = """#!/bin/bash
echo "Starting Celery processes..."

# Kill existing processes
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Start Celery worker
echo "Starting Celery worker..."
python manage.py celery_control start --worker-only &

# Start Celery beat
echo "Starting Celery beat..."
python manage.py celery_control start --beat-only &

echo "Celery processes started."
echo "Use ./celery_stop.sh to stop them."
"""
        
        # celery_stop.sh
        celery_stop_content = """#!/bin/bash
echo "Stopping Celery processes..."

pkill -f "celery.*worker"
pkill -f "celery.*beat"

echo "Celery processes stopped."
"""
        
        # celery_status.sh
        celery_status_content = """#!/bin/bash
echo "Checking Celery process status..."

python manage.py celery_control status
"""
        
        # Write files
        scripts = {
            'runserver_with_celery.sh': sh_content,
            'celery_start.sh': celery_start_content,
            'celery_stop.sh': celery_stop_content,
            'celery_status.sh': celery_status_content,
        }
        
        for filename, content in scripts.items():
            filepath = os.path.join(output_dir, filename)
            if os.path.exists(filepath) and not force:
                self.stdout.write(
                    self.style.WARNING(f'Skipping {filename} (already exists, use --force to overwrite)')
                )
                continue
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Make shell scripts executable
            os.chmod(filepath, 0o755)
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created {filename}')
            ) 