"""
Management command to monitor login security events and generate security reports.
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from app_cabinet.models import UserActivity
from collections import defaultdict
import json


class Command(BaseCommand):
    help = 'Monitor login security events and generate security reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to look back for security events (default: 24)'
        )
        parser.add_argument(
            '--show-lockouts',
            action='store_true',
            help='Show current IP and user lockouts'
        )
        parser.add_argument(
            '--clear-lockouts',
            action='store_true',
            help='Clear all current lockouts (use with caution)'
        )
        parser.add_argument(
            '--suspicious-threshold',
            type=int,
            default=5,
            help='Threshold for flagging suspicious activity (default: 5 failed attempts)'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        since = timezone.now() - timedelta(hours=hours)
        
        self.stdout.write(
            self.style.SUCCESS(f'\n=== SecBoard Login Security Report ===')
        )
        self.stdout.write(f'Report Period: Last {hours} hours')
        self.stdout.write(f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        
        if options['show_lockouts']:
            self.show_current_lockouts()
        
        if options['clear_lockouts']:
            self.clear_all_lockouts()
            return
        
        # Analyze failed login attempts
        failed_attempts = UserActivity.objects.filter(
            action='failed_login',
            timestamp__gte=since
        ).select_related('user')
        
        # Group by IP address
        ip_attempts = defaultdict(list)
        user_attempts = defaultdict(list)
        
        for attempt in failed_attempts:
            ip = attempt.details.get('ip_address', 'Unknown')
            ip_attempts[ip].append(attempt)
            if attempt.user:
                user_attempts[attempt.user.email].append(attempt)
        
        # Report suspicious IPs
        suspicious_ips = {
            ip: attempts for ip, attempts in ip_attempts.items() 
            if len(attempts) >= options['suspicious_threshold']
        }
        
        if suspicious_ips:
            self.stdout.write(f'\n🚨 SUSPICIOUS IP ADDRESSES (>= {options["suspicious_threshold"]} failed attempts):')
            for ip, attempts in sorted(suspicious_ips.items(), key=lambda x: len(x[1]), reverse=True):
                unique_users = set(a.user.email for a in attempts if a.user)
                self.stdout.write(
                    f'  • {ip}: {len(attempts)} attempts targeting {len(unique_users)} different accounts'
                )
                for user_email in list(unique_users)[:3]:  # Show first 3 targeted accounts
                    user_attempts_count = len([a for a in attempts if a.user and a.user.email == user_email])
                    self.stdout.write(f'    - {user_email}: {user_attempts_count} attempts')
                if len(unique_users) > 3:
                    self.stdout.write(f'    - ... and {len(unique_users) - 3} other accounts')
        
        # Report targeted accounts
        targeted_accounts = {
            email: attempts for email, attempts in user_attempts.items() 
            if len(attempts) >= options['suspicious_threshold']
        }
        
        if targeted_accounts:
            self.stdout.write(f'\n🎯 TARGETED ACCOUNTS (>= {options["suspicious_threshold"]} failed attempts):')
            for email, attempts in sorted(targeted_accounts.items(), key=lambda x: len(x[1]), reverse=True):
                unique_ips = set(a.details.get('ip_address', 'Unknown') for a in attempts)
                self.stdout.write(
                    f'  • {email}: {len(attempts)} attempts from {len(unique_ips)} different IPs'
                )
                if len(unique_ips) <= 3:
                    for ip in unique_ips:
                        ip_attempts_count = len([a for a in attempts if a.details.get('ip_address') == ip])
                        self.stdout.write(f'    - {ip}: {ip_attempts_count} attempts')
        
        # Successful logins
        successful_logins = UserActivity.objects.filter(
            action='login',
            timestamp__gte=since
        ).count()
        
        # Summary statistics
        total_failed = sum(len(attempts) for attempts in ip_attempts.values())
        unique_ips = len(ip_attempts)
        unique_users_targeted = len(user_attempts)
        
        self.stdout.write(f'\n📊 SUMMARY STATISTICS:')
        self.stdout.write(f'  • Total failed login attempts: {total_failed}')
        self.stdout.write(f'  • Successful logins: {successful_logins}')
        self.stdout.write(f'  • Unique IP addresses with failed attempts: {unique_ips}')
        self.stdout.write(f'  • Unique accounts targeted: {unique_users_targeted}')
        self.stdout.write(f'  • Success rate: {successful_logins/(successful_logins + total_failed)*100:.1f}%' if (successful_logins + total_failed) > 0 else '  • Success rate: N/A')
        
        # Recent activity pattern
        if total_failed > 0:
            self.stdout.write(f'\n⏱️  RECENT ACTIVITY PATTERN:')
            # Group by hour
            hourly_attempts = defaultdict(int)
            for attempts in ip_attempts.values():
                for attempt in attempts:
                    hour = attempt.timestamp.strftime('%Y-%m-%d %H:00')
                    hourly_attempts[hour] += 1
            
            # Show last 12 hours
            for i in range(12):
                hour_time = timezone.now() - timedelta(hours=i)
                hour_key = hour_time.strftime('%Y-%m-%d %H:00')
                count = hourly_attempts.get(hour_key, 0)
                bar = '█' * min(count // 2, 20)  # Visual bar
                self.stdout.write(f'  {hour_key}: {count:3d} attempts {bar}')
    
    def show_current_lockouts(self):
        """Show current IP and user lockouts from cache"""
        self.stdout.write(f'\n🔒 CURRENT LOCKOUTS:')
        
        # This is a simplified way to check lockouts
        # In a real implementation, you might want to iterate through cache keys
        # For now, we'll show a placeholder
        self.stdout.write('  (Lockout information requires cache key enumeration)')
        self.stdout.write('  Use Django admin or check cache directly for detailed lockout status')
    
    def clear_all_lockouts(self):
        """Clear all lockouts (use with caution)"""
        if input('Are you sure you want to clear ALL security lockouts? (yes/no): ').lower() != 'yes':
            self.stdout.write('Operation cancelled.')
            return
        
        # This would require iterating through cache keys
        # For security reasons, we'll just show a warning
        self.stdout.write(
            self.style.WARNING('⚠️  To clear lockouts, you need to manually clear cache keys matching:')
        )
        self.stdout.write('  - login_attempts_*')
        self.stdout.write('  - login_lockout_*')
        self.stdout.write('  - user_login_attempts_*')
        self.stdout.write('\nExample Redis commands:')
        self.stdout.write('  redis-cli --scan --pattern "login_attempts_*" | xargs redis-cli del')
        self.stdout.write('  redis-cli --scan --pattern "login_lockout_*" | xargs redis-cli del')
        self.stdout.write('  redis-cli --scan --pattern "user_login_attempts_*" | xargs redis-cli del') 