import os
import sys
import time
import signal
import platform
import subprocess
from django.core.management.base import BaseCommand
from django.core.management.commands.runserver import Command as RunserverCommand
from django.utils.translation import gettext as _
from app_conf.models import CelerySettings


class Command(RunserverCommand):
    help = 'Run Django development server with Celery worker and beat'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.celery_processes = []
        self.celery_settings = None
    
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--no-celery',
            action='store_true',
            help='Disable Celery worker and beat auto-start'
        )
        parser.add_argument(
            '--celery-only',
            action='store_true',
            help='Start only Celery processes without Django server'
        )
        parser.add_argument(
            '--force-windows',
            action='store_true',
            help='Force Windows-specific commands even on non-Windows systems'
        )
    
    def handle(self, *args, **options):
        # Load Celery settings
        try:
            self.celery_settings = CelerySettings.get_settings()
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not load Celery settings: {e}')
            )
            self.celery_settings = None
        
        # Set up signal handlers for cleanup
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Start Celery processes if enabled and not disabled by option
            if not options.get('no_celery') and self.should_start_celery():
                self.start_celery_processes(options)
            
            # Start Django server unless celery-only mode
            if not options.get('celery_only'):
                self.stdout.write(
                    self.style.SUCCESS('Starting Django development server...')
                )
                super().handle(*args, **options)
            else:
                self.stdout.write(
                    self.style.SUCCESS('Celery processes started. Press Ctrl+C to stop.')
                )
                # Keep the process alive
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup_processes()
    
    def should_start_celery(self):
        """Check if Celery should be started based on settings"""
        if not self.celery_settings:
            return False
        
        return (
            self.celery_settings.is_active and 
            self.celery_settings.auto_start_with_runserver and
            (self.celery_settings.enable_worker or self.celery_settings.enable_beat)
        )
    
    def start_celery_processes(self, options):
        """Start Celery worker and beat processes"""
        self.stdout.write(
            self.style.HTTP_INFO('Starting Celery processes...')
        )
        
        # Kill existing processes if enabled
        if self.celery_settings.kill_existing_processes:
            self.kill_existing_celery_processes()
        
        # Determine if we should use Windows commands
        use_windows = (
            options.get('force_windows') or 
            self.celery_settings.use_windows_commands or 
            platform.system() == 'Windows'
        )
        
        # Start Celery worker
        if self.celery_settings.enable_worker:
            worker_cmd = self.celery_settings.get_worker_command()
            if use_windows and '--pool=solo' not in worker_cmd:
                worker_cmd += ' --pool=solo'
            
            self.stdout.write(f'Starting Celery worker: {worker_cmd}')
            worker_process = self.start_process(worker_cmd, 'worker')
            if worker_process:
                self.celery_processes.append(('worker', worker_process))
        
        # Start Celery beat
        if self.celery_settings.enable_beat:
            beat_cmd = self.celery_settings.get_beat_command()
            self.stdout.write(f'Starting Celery beat: {beat_cmd}')
            beat_process = self.start_process(beat_cmd, 'beat')
            if beat_process:
                self.celery_processes.append(('beat', beat_process))
        
        # Give processes time to start
        time.sleep(2)
        
        # Check if processes are running
        self.check_process_status()
    
    def start_process(self, command, process_type):
        """Start a subprocess with the given command"""
        try:
            # Set up environment variables
            env = os.environ.copy()
            
            # Set PYTHONPATH and DJANGO_SETTINGS_MODULE
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            secboard_dir = os.path.join(base_dir, 'SecBoard')
            
            env['PYTHONPATH'] = secboard_dir
            env['DJANGO_SETTINGS_MODULE'] = 'SecBoard.settings'
            
            # For commands with environment variables, run them through shell
            if '&&' in command:
                # Start the process through shell
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1,
                    env=env
                )
            else:
                # For simple commands, split and run directly
                cmd_list = command.split()
                
                # Start the process
                process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1,
                    env=env
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Started Celery {process_type} (PID: {process.pid})')
            )
            return process
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[ERROR] Failed to start Celery {process_type}: {e}')
            )
            return None
    
    def kill_existing_celery_processes(self):
        """Kill existing Celery processes"""
        self.stdout.write('Killing existing Celery processes...')
        
        if platform.system() == 'Windows':
            # Windows commands
            commands = [
                'taskkill /f /im celery.exe 2>nul',
                'taskkill /f /im python.exe /fi "WINDOWTITLE eq celery*" 2>nul'
            ]
        else:
            # Unix commands
            commands = [
                'pkill -f "celery.*worker"',
                'pkill -f "celery.*beat"'
            ]
        
        for cmd in commands:
            try:
                subprocess.run(cmd, shell=True, capture_output=True)
            except Exception:
                pass
    
    def check_process_status(self):
        """Check if Celery processes are running"""
        for process_type, process in self.celery_processes:
            if process.poll() is None:
                self.stdout.write(
                    self.style.SUCCESS(f'[OK] Celery {process_type} is running (PID: {process.pid})')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'[ERROR] Celery {process_type} failed to start')
                )
                # Try to get error output
                try:
                    stderr = process.stderr.read()
                    if stderr:
                        self.stdout.write(f'Error: {stderr}')
                except:
                    pass
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals"""
        self.stdout.write('\nReceived interrupt signal. Cleaning up...')
        self.cleanup_processes()
        sys.exit(0)
    
    def cleanup_processes(self):
        """Clean up Celery processes"""
        if not self.celery_processes:
            return
        
        self.stdout.write('Stopping Celery processes...')
        
        for process_type, process in self.celery_processes:
            try:
                if process.poll() is None:  # Process is still running
                    self.stdout.write(f'Stopping Celery {process_type} (PID: {process.pid})')
                    
                    # Try graceful shutdown first
                    process.terminate()
                    
                    # Wait a bit for graceful shutdown
                    try:
                        process.wait(timeout=5)
                        self.stdout.write(f'[OK] Celery {process_type} stopped gracefully')
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful shutdown failed
                        self.stdout.write(f'Force killing Celery {process_type}')
                        process.kill()
                        process.wait()
                        self.stdout.write(f'[OK] Celery {process_type} force stopped')
                        
            except Exception as e:
                self.stdout.write(f'Error stopping Celery {process_type}: {e}')
        
        self.celery_processes = []
        self.stdout.write('[OK] All Celery processes stopped')
    
    def inner_run(self, *args, **options):
        """Override inner_run to add Celery status info"""
        if self.celery_processes:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f'Celery processes running: {len(self.celery_processes)} '
                    f'({", ".join([p[0] for p in self.celery_processes])})'
                )
            )
        
        return super().inner_run(*args, **options) 