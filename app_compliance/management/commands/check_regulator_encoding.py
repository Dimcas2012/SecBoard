"""
Перевірка та виправлення кодування регуляторів
"""
from django.core.management.base import BaseCommand
from app_compliance.models import LocalComplianceRegulator


class Command(BaseCommand):
    help = 'Check and display encoding issues in LocalComplianceRegulator'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix encoding (requires manual verification)',
        )
    
    def handle(self, *args, **options):
        """Перевірити кодування"""
        
        regulators = LocalComplianceRegulator.objects.all()
        
        self.stdout.write(f"\n📋 Checking {regulators.count()} regulators...\n")
        
        issues_found = []
        
        for reg in regulators:
            has_issue = False
            issue_info = {
                'id': reg.id,
                'name': reg.name,
                'name_local': reg.name_local,
                'name_local_bytes': None
            }
            
            # Перевірити name_local
            if reg.name_local:
                # Шукати не-ASCII символи які виглядають неправильно
                suspicious_chars = ['Р', 'Рѕ', 'Р°', 'Р†', 'Сѓ', 'С–', 'С,']
                if any(char in reg.name_local for char in suspicious_chars):
                    has_issue = True
                    # Показати як bytes
                    try:
                        issue_info['name_local_bytes'] = reg.name_local.encode('utf-8')
                    except:
                        issue_info['name_local_bytes'] = 'Cannot encode'
            
            if has_issue:
                issues_found.append(issue_info)
                self.stdout.write(
                    self.style.ERROR(f"❌ {reg.id}: {reg.name}")
                )
                self.stdout.write(f"   Local Name (current): {reg.name_local}")
                self.stdout.write(f"   Bytes: {issue_info['name_local_bytes']}")
                
                # Спробувати різні варіанти декодування
                if options['fix']:
                    attempts = [
                        ('latin1→utf8', lambda x: x.encode('latin1').decode('utf-8')),
                        ('cp1251→utf8', lambda x: x.encode('cp1251', errors='ignore').decode('utf-8')),
                        ('iso-8859-1→utf8', lambda x: x.encode('iso-8859-1').decode('utf-8')),
                    ]
                    
                    self.stdout.write("   Trying fixes:")
                    for method_name, method in attempts:
                        try:
                            fixed = method(reg.name_local)
                            self.stdout.write(f"   - {method_name}: {fixed}")
                        except Exception as e:
                            self.stdout.write(f"   - {method_name}: Failed ({str(e)})")
                
                self.stdout.write("")
        
        # Summary
        self.stdout.write("=" * 80)
        if issues_found:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Found {len(issues_found)} regulators with encoding issues")
            )
            self.stdout.write("\n📝 To fix manually:")
            self.stdout.write("   1. Go to Django Admin")
            self.stdout.write("   2. Edit each regulator")
            self.stdout.write("   3. Re-enter the Local Name field with correct text")
            self.stdout.write("   4. Save")
            self.stdout.write("\n💡 Or use --fix flag to see suggested fixes")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ No encoding issues found!")
            )

