# -*- coding: utf-8 -*-
import os
import sys
import time
import signal
import platform
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from app_conf.models import CelerySettings


class Command(BaseCommand):
    help = 'Control Celery worker and beat processes'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.celery_processes = []
        self.celery_settings = None
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['start', 'stop', 'restart', 'status'],
            help='Action to perform on Celery processes'
        )
        parser.add_argument(
            '--worker-only',
            action='store_true',
            help='Only affect Celery worker'
        )
        parser.add_argument(
            '--beat-only',
            action='store_true',
            help='Only affect Celery beat'
        )
        parser.add_argument(
            '--force-windows',
            action='store_true',
            help='Force Windows-specific commands'
        )
        parser.add_argument(
            '--no-kill',
            action='store_true',
            help='Do not kill existing processes before starting'
        )
    
    def handle(self, *args, **options):
        # Load Celery settings
        try:
            self.celery_settings = CelerySettings.get_settings()
        except Exception as e:
            raise CommandError(f'Could not load Celery settings: {e}')
        
        action = options['action']
        
        if action == 'start':
            self.start_celery(options)
        elif action == 'stop':
            self.stop_celery(options)
        elif action == 'restart':
            self.stop_celery(options)
            time.sleep(2)
            self.start_celery(options)
        elif action == 'status':
            self.show_status(options)
    
    def start_celery(self, options):
        """Start Celery processes"""
        self.stdout.write(
            self.style.HTTP_INFO('Starting Celery processes...')
        )
        
        # Kill existing processes if enabled and not disabled
        if self.celery_settings.kill_existing_processes and not options.get('no_kill'):
            self.kill_existing_celery_processes()
        
        # Determine which processes to start
        start_worker = (
            self.celery_settings.enable_worker and 
            not options.get('beat_only')
        )
        start_beat = (
            self.celery_settings.enable_beat and 
            not options.get('worker_only')
        )
        
        if not start_worker and not start_beat:
            self.stdout.write(
                self.style.WARNING('No Celery processes enabled in settings')
            )
            return
        
        # Determine if we should use Windows commands
        use_windows = (
            options.get('force_windows') or 
            self.celery_settings.use_windows_commands or 
            platform.system() == 'Windows'
        )
        
        # Start Celery worker
        if start_worker:
            worker_cmd = self.celery_settings.get_worker_command()
            if use_windows and '--pool=solo' not in worker_cmd:
                worker_cmd += ' --pool=solo'
            
            self.stdout.write(f'Starting Celery worker: {worker_cmd}')
            if self.start_background_process(worker_cmd, 'worker'):
                self.stdout.write(
                    self.style.SUCCESS('[OK] Celery worker started')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('[ERROR] Failed to start Celery worker')
                )
        
        # Start Celery beat
        if start_beat:
            beat_cmd = self.celery_settings.get_beat_command()
            self.stdout.write(f'Starting Celery beat: {beat_cmd}')
            if self.start_background_process(beat_cmd, 'beat'):
                self.stdout.write(
                    self.style.SUCCESS('[OK] Celery beat started')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('[ERROR] Failed to start Celery beat')
                )
        
        # Show status after starting
        time.sleep(2)
        self.show_status(options)
    
    def stop_celery(self, options):
        """Stop Celery processes"""
        self.stdout.write('Stopping Celery processes...')
        
        # Determine which processes to stop
        stop_worker = not options.get('beat_only')
        stop_beat = not options.get('worker_only')
        
        if platform.system() == 'Windows':
            # Windows commands
            commands = []
            if stop_worker:
                commands.extend([
                    'taskkill /f /im celery.exe 2>nul',
                    'wmic process where "name=\'python.exe\' and commandline like \'%celery%worker%\'" delete 2>nul'
                ])
            if stop_beat:
                commands.append(
                    'wmic process where "name=\'python.exe\' and commandline like \'%celery%beat%\'" delete 2>nul'
                )
        else:
            # Unix commands
            commands = []
            if stop_worker:
                commands.append('pkill -f "celery.*worker"')
            if stop_beat:
                commands.append('pkill -f "celery.*beat"')
        
        stopped_any = False
        for cmd in commands:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    stopped_any = True
            except Exception:
                pass
        
        if stopped_any:
            self.stdout.write(
                self.style.SUCCESS('[OK] Celery processes stopped')
            )
        else:
            self.stdout.write(
                self.style.WARNING('No Celery processes were running')
            )
    
    def show_status(self, options):
        """Show status of Celery processes"""
        self.stdout.write('Checking Celery process status...')
        
        if platform.system() == 'Windows':
            # Windows commands
            worker_cmd = 'wmic process where "name=\'python.exe\' and commandline like \'%celery%worker%\'" get processid,commandline /format:csv'
            beat_cmd = 'wmic process where "name=\'python.exe\' and commandline like \'%celery%beat%\'" get processid,commandline /format:csv'
        else:
            # Unix commands
            worker_cmd = 'pgrep -f "celery.*worker"'
            beat_cmd = 'pgrep -f "celery.*beat"'
        
        # Check worker status
        if not options.get('beat_only'):
            try:
                result = subprocess.run(worker_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    if platform.system() == 'Windows':
                        lines = [line for line in result.stdout.split('\n') if line.strip() and 'Node' not in line]
                        worker_count = len(lines) - 1 if lines else 0
                    else:
                        worker_count = len(result.stdout.strip().split('\n'))
                    
                    if worker_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f'[OK] Celery worker running ({worker_count} processes)')
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR('[ERROR] Celery worker not running')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR('[ERROR] Celery worker not running')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error checking worker status: {e}')
                )
        
        # Check beat status
        if not options.get('worker_only'):
            try:
                result = subprocess.run(beat_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    if platform.system() == 'Windows':
                        lines = [line for line in result.stdout.split('\n') if line.strip() and 'Node' not in line]
                        beat_count = len(lines) - 1 if lines else 0
                    else:
                        beat_count = len(result.stdout.strip().split('\n'))
                    
                    if beat_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f'[OK] Celery beat running ({beat_count} processes)')
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR('[ERROR] Celery beat not running')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR('[ERROR] Celery beat not running')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error checking beat status: {e}')
                )
    
    def start_background_process(self, command, process_type):
        """Start a process in the background"""
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
                if platform.system() == 'Windows':
                    # On Windows, start process detached
                    subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    # On Unix, start process detached
                    subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        preexec_fn=os.setsid
                    )
            else:
                # For simple commands, split and run directly
                cmd_list = command.split()
                
                if platform.system() == 'Windows':
                    # On Windows, start process detached
                    subprocess.Popen(
                        cmd_list,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    # On Unix, start process detached
                    subprocess.Popen(
                        cmd_list,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,
                        preexec_fn=os.setsid
                    )
            
            return True
            
        except Exception as e:
            self.stdout.write(f'Error starting {process_type}: {e}')
            return False
    
    def kill_existing_celery_processes(self):
        """Kill existing Celery processes"""
        self.stdout.write('Killing existing Celery processes...')
        
        if platform.system() == 'Windows':
            # Windows commands
            commands = [
                'taskkill /f /im celery.exe 2>nul',
                'wmic process where "name=\'python.exe\' and commandline like \'%celery%\'" delete 2>nul'
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