from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json


class Command(BaseCommand):
    help = 'Monitor and manage session security'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up expired sessions'
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate session security report'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Show sessions for specific user (by username)'
        )
        parser.add_argument(
            '--kill-user-sessions',
            type=str,
            help='Kill all sessions for specific user (by username)'
        )
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=24,
            help='Maximum session age in hours for cleanup (default: 24)'
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.cleanup_sessions(options['max_age_hours'])
        elif options['report']:
            self.generate_report()
        elif options['user']:
            self.show_user_sessions(options['user'])
        elif options['kill_user_sessions']:
            self.kill_user_sessions(options['kill_user_sessions'])
        else:
            self.show_help()

    def cleanup_sessions(self, max_age_hours):
        """Clean up expired and old sessions"""
        self.stdout.write("Cleaning up sessions...")
        
        # Clean up expired sessions
        expired_count = Session.objects.filter(
            expire_date__lt=timezone.now()
        ).count()
        
        Session.objects.filter(expire_date__lt=timezone.now()).delete()
        
        # Clean up old sessions based on max age
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        old_sessions = Session.objects.filter(expire_date__lt=cutoff_time)
        old_count = old_sessions.count()
        old_sessions.delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleaned up {expired_count} expired sessions and "
                f"{old_count} sessions older than {max_age_hours} hours"
            )
        )

    def generate_report(self):
        """Generate session security report"""
        self.stdout.write("Session Security Report")
        self.stdout.write("=" * 50)
        
        # Total active sessions
        total_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        ).count()
        
        # Sessions by user
        user_sessions = {}
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                session_data = session.get_decoded()
                user_id = session_data.get('_auth_user_id')
                if user_id:
                    try:
                        user = User.objects.get(id=user_id)
                        if user.username not in user_sessions:
                            user_sessions[user.username] = {
                                'count': 0,
                                'sessions': []
                            }
                        user_sessions[user.username]['count'] += 1
                        
                        # Get session details
                        session_info = {
                            'session_key': session.session_key[:8] + '...',
                            'expire_date': session.expire_date,
                            'login_time': session_data.get('login_time', 'Unknown'),
                            'session_ip': session_data.get('session_ip', 'Unknown'),
                            'last_activity': session_data.get('last_activity', 'Unknown')
                        }
                        user_sessions[user.username]['sessions'].append(session_info)
                    except User.DoesNotExist:
                        pass
            except Exception as e:
                continue
        
        self.stdout.write(f"Total active sessions: {total_sessions}")
        self.stdout.write(f"Users with active sessions: {len(user_sessions)}")
        self.stdout.write("")
        
        # Show users with multiple sessions
        multi_session_users = {
            username: data for username, data in user_sessions.items() 
            if data['count'] > 1
        }
        
        if multi_session_users:
            self.stdout.write("Users with multiple sessions:")
            for username, data in multi_session_users.items():
                self.stdout.write(f"  {username}: {data['count']} sessions")
                for session in data['sessions']:
                    self.stdout.write(f"    - {session['session_key']} "
                                    f"(IP: {session['session_ip']}, "
                                    f"Expires: {session['expire_date']})")
        else:
            self.stdout.write("No users with multiple sessions found.")

    def show_user_sessions(self, username):
        """Show sessions for a specific user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"User '{username}' not found")
            )
            return
        
        self.stdout.write(f"Sessions for user: {username}")
        self.stdout.write("=" * 50)
        
        user_sessions = []
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') == str(user.id):
                    user_sessions.append({
                        'session_key': session.session_key,
                        'expire_date': session.expire_date,
                        'session_data': session_data
                    })
            except Exception:
                continue
        
        if user_sessions:
            for i, session in enumerate(user_sessions, 1):
                self.stdout.write(f"Session {i}:")
                self.stdout.write(f"  Session Key: {session['session_key']}")
                self.stdout.write(f"  Expires: {session['expire_date']}")
                self.stdout.write(f"  Login Time: {session['session_data'].get('login_time', 'Unknown')}")
                self.stdout.write(f"  IP Address: {session['session_data'].get('session_ip', 'Unknown')}")
                self.stdout.write(f"  Last Activity: {session['session_data'].get('last_activity', 'Unknown')}")
                self.stdout.write("")
        else:
            self.stdout.write("No active sessions found for this user.")

    def kill_user_sessions(self, username):
        """Kill all sessions for a specific user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"User '{username}' not found")
            )
            return
        
        killed_count = 0
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') == str(user.id):
                    session.delete()
                    killed_count += 1
            except Exception:
                continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Killed {killed_count} sessions for user '{username}'"
            )
        )

    def show_help(self):
        """Show available options"""
        self.stdout.write("Session Security Management")
        self.stdout.write("=" * 50)
        self.stdout.write("Available options:")
        self.stdout.write("  --cleanup                Clean up expired sessions")
        self.stdout.write("  --report                 Generate session report")
        self.stdout.write("  --user <username>        Show sessions for user")
        self.stdout.write("  --kill-user-sessions <username>  Kill all user sessions")
        self.stdout.write("  --max-age-hours <hours>  Max session age for cleanup")
        self.stdout.write("")
        self.stdout.write("Examples:")
        self.stdout.write("  python manage.py session_security --cleanup")
        self.stdout.write("  python manage.py session_security --report")
        self.stdout.write("  python manage.py session_security --user admin")
        self.stdout.write("  python manage.py session_security --kill-user-sessions admin") 