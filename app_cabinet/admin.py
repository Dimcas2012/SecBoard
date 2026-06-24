# SecBoard/app_cabinet/admin.py


from django.contrib import admin
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django import forms
from django.contrib import messages
from mptt.admin import DraggableMPTTAdmin

from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField
from .models import (
    CabinetUser,
    CabinetTaskReminderSchedule,
    CabinetPasswordCompanyLink,
    CabinetADConnection,
    CabinetSettings,
    Department,
    Position,
    CabinetGroup,
    PlatformRole,
    PlatformRoleDashboardConfig,
    UserSession,
    UserActivity,
    AccessOptions,
    OrgStructureGuide,
    OrgStructureGuideTranslation,
    CabinetUsersGuide,
    CabinetUsersGuideTranslation,
    CabinetGroupsGuide,
    CabinetGroupsGuideTranslation,
)
from app_conf.models import Company


class PositionAdminForm(forms.ModelForm):
    """Form for Position admin with validation for department/parent_position mutual exclusivity"""
    
    class Meta:
        model = Position
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        parent_position = cleaned_data.get('parent_position')
        company = cleaned_data.get('company')
        
        # Check that department and parent_position are not both selected
        if department and parent_position:
            raise forms.ValidationError({
                'department': _('You can select either Department or Parent Position, but not both')
            })
        
        # Validate parent_position if provided
        if parent_position:
            if company and parent_position.company_id != company.id:
                raise forms.ValidationError({
                    'parent_position': _('Parent position must be from the same company')
                })
            
            # Check if position is being set as its own parent
            if self.instance and self.instance.pk and parent_position.id == self.instance.id:
                raise forms.ValidationError({
                    'parent_position': _('Position cannot be its own parent')
                })
        
        return cleaned_data


class CabinetUserAdminForm(forms.ModelForm):
    """Form for CabinetUser admin with parent_position field"""
    parent_position = forms.ModelChoiceField(
        queryset=Position.objects.all(),
        required=False,
        label=_('Parent Position'),
        help_text=_('Parent position for the selected position. Must be from the same company.')
    )
    
    class Meta:
        model = CabinetUser
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value for parent_position from position.parent_position
        # Need to handle both existing instances and when position might change
        if self.instance and self.instance.pk:
            # Get position from initial data if available (when position is being changed)
            # Otherwise use instance.position
            if self.initial.get('position'):
                try:
                    position = Position.objects.get(pk=self.initial['position'])
                    self.fields['parent_position'].initial = position.parent_position
                except (Position.DoesNotExist, ValueError):
                    pass
            elif self.instance.position:
                self.fields['parent_position'].initial = self.instance.position.parent_position
        
        # Set queryset for parent_position - filter by company if available
        # Use initial data if available (when editing), otherwise use instance
        company = None
        position_id = None
        
        if self.initial.get('company'):
            try:
                from .models import Company
                company = Company.objects.get(pk=self.initial['company'])
            except (Company.DoesNotExist, ValueError):
                pass
        elif self.instance and self.instance.company:
            company = self.instance.company
        
        if self.initial.get('position'):
            try:
                position_id = int(self.initial['position'])
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.position:
            position_id = self.instance.position.id
        
        if company:
            # Filter department and position by company
            self.fields['department'].queryset = Department.objects.filter(
                company=company
            ).select_related('parent', 'parent_position').order_by('name')
            self.fields['position'].queryset = Position.objects.filter(
                company=company
            ).select_related('department', 'parent_position').order_by('name')
            # Get all positions from the same company, excluding the current position
            queryset = Position.objects.filter(company=company)
            if position_id:
                queryset = queryset.exclude(id=position_id)
            self.fields['parent_position'].queryset = queryset.order_by('name')
        else:
            # If no company, show all positions (will be filtered on save)
            queryset = Position.objects.all()
            if position_id:
                queryset = queryset.exclude(id=position_id)
            self.fields['parent_position'].queryset = queryset.order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        position = cleaned_data.get('position')
        parent_position = cleaned_data.get('parent_position')
        
        # Validate parent_position
        if parent_position:
            if not position:
                raise forms.ValidationError({
                    'parent_position': _('Position must be selected before setting parent position')
                })
            
            if position.company and parent_position.company_id != position.company.id:
                raise forms.ValidationError({
                    'parent_position': _('Parent position must be from the same company as the position')
                })
            
            if parent_position.id == position.id:
                raise forms.ValidationError({
                    'parent_position': _('Position cannot be its own parent')
                })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=commit)
        # Note: position.parent_position will be updated in CabinetUserAdmin.save_model
        # to ensure position is fully saved before updating parent_position
        return instance


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    form = PositionAdminForm
    list_display = (
        'name',
        'company',
        'get_parent_info',
        'color',
        'get_description',
    )
    list_filter = ('company', 'department')
    search_fields = (
        'name',
        'company__name',
        'department__name',
        'parent_position__name',
    )
    fieldsets = (
        (None, {
            'fields': ('company', 'department', 'parent_position', 'color')
        }),
        (_('Name'), {'fields': ('name',)}),
        (_('Description'), {'fields': ('description',)}),
    )

    def get_description(self, obj):
        desc = obj.get_description() or ''
        return (desc[:50] + '...') if len(desc) > 50 else desc

    get_description.short_description = _('Description')

    def get_parent_info(self, obj):
        """Display department or parent position"""
        if obj.department:
            return format_html(
                '<span class="badge bg-primary">'
                '<i class="bi bi-diagram-3 me-1"></i>{}'
                '</span>',
                obj.department.get_name()
            )
        elif obj.parent_position:
            return format_html(
                '<span class="badge bg-info text-dark">'
                '<i class="bi bi-briefcase me-1"></i>{}'
                '</span>',
                obj.parent_position.get_name()
            )
        return format_html('<span class="text-muted">-</span>')
    
    get_parent_info.short_description = _('Parent')

    class Media:
        js = ('admin/js/position_admin.js',)


@admin.register(Department)
class DepartmentAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "name"
    list_display = (
        'tree_actions',
        'indented_title',
        'company',
        'color',
        'get_description'
    )
    list_filter = ('company',)
    search_fields = (
        'name',
        'company__name'
    )
    fieldsets = (
        (None, {
            'fields': ('parent', 'parent_position', 'company', 'color')
        }),
        (_('Name'), {'fields': ('name',)}),
        (_('Description'), {'fields': ('description',)}),
    )

    def get_description(self, obj):
        desc = obj.get_description() or ''
        return (desc[:50] + '...') if len(desc) > 50 else desc

    get_description.short_description = _('Description')


class CompanyDepartmentFilter(admin.SimpleListFilter):
    """Department filter limited to selected Company, with Parent Dept/Position info"""
    title = _('Department')
    parameter_name = 'department__id__exact'

    def lookups(self, request, model_admin):
        company_id = (request.GET.get('company__id__exact') or
                     request.GET.get('company__id') or
                     request.GET.get('company'))
        departments = Department.objects.all().select_related('parent', 'parent_position', 'company')
        if company_id:
            departments = departments.filter(company_id=company_id)
        return [(d.id, self._format_dept(d)) for d in departments.order_by('name')]

    def _format_dept(self, dept):
        name = dept.get_name()
        if dept.parent:
            return f"{name} ← {dept.parent.get_name()}"
        if dept.parent_position:
            return f"{name} ({_('under')} {dept.parent_position.get_name()})"
        return name

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(department_id=self.value())
        return queryset


class CompanyPositionFilter(admin.SimpleListFilter):
    """Position filter limited to selected Company, with Dept/Parent Position info"""
    title = _('Position')
    parameter_name = 'position__id__exact'

    def lookups(self, request, model_admin):
        company_id = (request.GET.get('company__id__exact') or
                     request.GET.get('company__id') or
                     request.GET.get('company'))
        positions = Position.objects.all().select_related('department', 'parent_position', 'company')
        if company_id:
            positions = positions.filter(company_id=company_id)
        return [(p.id, self._format_pos(p)) for p in positions.order_by('name')]

    def _format_pos(self, pos):
        name = pos.get_name()
        if pos.department:
            return f"{name} ({pos.department.get_name()})"
        if pos.parent_position:
            return f"{name} ← {pos.parent_position.get_name()}"
        return name

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(position_id=self.value())
        return queryset


class CabinetUserInline(admin.StackedInline):
    model = CabinetUser
    can_delete = False
    verbose_name_plural = _('Cabinet User')
    fields = (
        'company',
        'department',
        'position',
        ('start_date', 'end_date'),
        'phone',
        'force_two_factor'
    )
    raw_id_fields = ('department', 'position')


@admin.register(CabinetUser)
class CabinetUserAdmin(admin.ModelAdmin):
    form = CabinetUserAdminForm
    list_display = (
        'user',
        'company',
        'get_department_display',
        'get_position_display',
        'get_parent',
        'start_date',
        'end_date',
        'is_currently_active',
        'is_ad_synced',
        'view_details',
        'login_as_user_link',
    )
    list_filter = (
        'company',
        'is_profile_completed',
        'is_ad_synced',
        CompanyDepartmentFilter,
        CompanyPositionFilter,
    )
    search_fields = (
        'user__username',
        'user__email',
        'company__name',
        'department__name',
        'position__name',
        'phone'
    )
    readonly_fields = ('is_currently_active', 'ad_profile_display')
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        (_('Organization'), {
            'fields': ('company', 'department', 'position', 'parent_position')
        }),
        (_('Employment'), {
            'fields': ('start_date', 'end_date', 'is_currently_active')
        }),
        (_('Contact'), {
            'fields': ('phone',)
        }),
        (_('Settings'), {
            'fields': ('is_profile_completed', 'force_two_factor', 'is_ad_synced'),
            'classes': ('collapse',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj=obj))
        if obj and obj.is_ad_synced:
            ad_section = (_('Active Directory profile'), {
                'fields': ('ad_profile_display',),
                'description': _('This user is provisioned from Active Directory. The fields below are updated on each AD login according to the company AD connection.'),
            })
            fieldsets.insert(1, ad_section)
        return fieldsets

    def ad_profile_display(self, obj):
        if not obj or not obj.is_ad_synced:
            return ''
        try:
            ad_conn = getattr(obj.company, 'ad_connection', None) if obj.company else None
        except Exception:
            ad_conn = None
        lines = [
            str(_('User is synced from Active Directory.')),
            str(_('On each login, the following are updated from AD:')),
            '• ' + str(_('User: email, first name, last name')),
            '• ' + str(_('Cabinet: phone, start date, end date')),
            '• ' + str(_('Currently active (from start/end date range)')),
        ]
        if ad_conn:
            lines.append('')
            lines.append(str(_('AD connection: %(name)s (%(server)s)') % {'name': ad_conn.name, 'server': ad_conn.server_url}))
        return format_html('<div style="max-width: 560px;">{}</div>', format_html('<br>'.join(lines)))

    ad_profile_display.short_description = _('AD profile info')

    def is_currently_active(self, obj):
        if obj.is_active_employee():
            return format_html(
                '<span style="color: green;">✓</span>'
            )
        return format_html(
            '<span style="color: red;">✗</span>'
        )

    is_currently_active.short_description = _('Currently Active')

    def get_department_display(self, obj):
        """Department with Parent Department or Parent Position info"""
        if not obj.department:
            return format_html('<span class="text-muted">-</span>')
        dept = obj.department
        name = dept.get_name()
        if dept.parent:
            return format_html(
                '<span title="{}">{} <small class="text-muted">← {}</small></span>',
                _('Parent Department: %s') % dept.parent.get_name(),
                name,
                dept.parent.get_name()
            )
        if dept.parent_position:
            return format_html(
                '<span title="{}">{} <small class="text-muted">({})</small></span>',
                _('Parent Position: %s') % dept.parent_position.get_name(),
                name,
                dept.parent_position.get_name()
            )
        return name

    get_department_display.short_description = _('Department')
    get_department_display.admin_order_field = 'department__name'

    def get_position_display(self, obj):
        """Position with Department or Parent Position info"""
        if not obj.position:
            return format_html('<span class="text-muted">-</span>')
        pos = obj.position
        name = pos.get_name()
        if pos.department:
            return format_html(
                '<span title="{}">{} <small class="text-muted">({})</small></span>',
                _('Department: %s') % pos.department.get_name(),
                name,
                pos.department.get_name()
            )
        if pos.parent_position:
            return format_html(
                '<span title="{}">{} <small class="text-muted">← {}</small></span>',
                _('Parent Position: %s') % pos.parent_position.get_name(),
                name,
                pos.parent_position.get_name()
            )
        return name

    get_position_display.short_description = _('Position')
    get_position_display.admin_order_field = 'position__name'

    def get_parent(self, obj):
        """Display parent position of the selected position"""
        if obj.position and obj.position.parent_position:
            parent = obj.position.parent_position
            return format_html(
                '<span class="badge bg-info text-dark">'
                '<i class="bi bi-briefcase me-1"></i>{}'
                '</span>',
                parent.get_name()
            )
        elif obj.position and obj.position.department:
            # Show department if no parent_position but has department
            dept = obj.position.department
            return format_html(
                '<span class="badge bg-primary">'
                '<i class="bi bi-diagram-3 me-1"></i>{}'
                '</span>',
                dept.get_name()
            )
        return format_html('<span class="text-muted">-</span>')
    
    get_parent.short_description = _('Parent')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter department, position, parent_position by company when editing"""
        obj = getattr(request, '_obj', None)
        if obj and obj.company:
            if db_field.name == 'department':
                kwargs['queryset'] = Department.objects.filter(
                    company=obj.company
                ).select_related('parent', 'parent_position').order_by('name')
            elif db_field.name == 'position':
                kwargs['queryset'] = Position.objects.filter(
                    company=obj.company
                ).select_related('department', 'parent_position').order_by('name')
            elif db_field.name == 'parent_position':
                position_id = obj.position.id if obj.position else None
                queryset = Position.objects.filter(company=obj.company)
                if position_id:
                    queryset = queryset.exclude(id=position_id)
                kwargs['queryset'] = queryset.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_form(self, request, obj=None, **kwargs):
        """Store obj in request for formfield_for_foreignkey"""
        if obj:
            request._obj = obj
        return super().get_form(request, obj, **kwargs)

    def view_details(self, obj):
        url = reverse('admin:cabinet_user_details', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, _('View Details'))

    view_details.short_description = _('Details')

    def login_as_user_link(self, obj):
        """Link to log in to the platform as this user (no password required)."""
        if not obj.user.is_active:
            return format_html('<span class="text-muted">{}</span>', _('Inactive user'))
        url = reverse('admin:app_cabinet_cabinetuser_login_as', args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" title="{}">{}</a>',
            url,
            _('Log in to the platform as this user'),
            _('Login as user'),
        )

    login_as_user_link.short_description = _('Login as user')

    @method_decorator(staff_member_required)
    def login_as_user(self, request, object_id):
        """Log in to the platform as the selected Cabinet User (no password)."""
        cabinet_user = self.get_object(request, object_id)
        if cabinet_user is None:
            self.message_user(request, _('Cabinet user not found.'), level='ERROR')
            return redirect('admin:app_cabinet_cabinetuser_changelist')
        user = cabinet_user.user
        if not user.is_active:
            self.message_user(request, _('Cannot log in as inactive user.'), level='ERROR')
            return redirect('admin:app_cabinet_cabinetuser_changelist')
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session['login_time'] = timezone.now().isoformat()
        messages.success(
            request,
            _('You are now logged in as %(username)s.') % {'username': user.get_full_name() or user.username},
        )
        return redirect('personal_cabinet')

    def get_queryset(self, request):
        """Optimize queryset to avoid N+1 queries"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'user',
            'company',
            'department',
            'department__parent',
            'department__parent_position',
            'position',
            'position__parent_position',
            'position__department',
            'position__company'
        )

    def save_model(self, request, obj, form, change):
        """Save CabinetUser and update position.parent_position"""
        super().save_model(request, obj, form, change)
        # Update position.parent_position if position exists
        if obj.position and isinstance(form, CabinetUserAdminForm):
            # Get parent_position from form's cleaned_data or form data
            if hasattr(form, 'cleaned_data') and 'parent_position' in form.cleaned_data:
                parent_position = form.cleaned_data.get('parent_position')
            elif 'parent_position' in form.data:
                # If not in cleaned_data, try to get from form data directly
                parent_position_id = form.data.get('parent_position')
                if parent_position_id:
                    try:
                        from .models import Position
                        parent_position = Position.objects.get(pk=parent_position_id)
                    except (Position.DoesNotExist, ValueError):
                        parent_position = None
                else:
                    parent_position = None
            else:
                # If parent_position not in form at all, skip update
                return
            
            # Reload position to get the latest state
            from .models import Position
            try:
                position = Position.objects.get(pk=obj.position.pk)
                # Update parent_position (can be None to clear it)
                position.parent_position = parent_position
                # Clear department if parent_position is set (mutual exclusivity)
                if parent_position:
                    position.department = None
                # Save the position
                position.save(update_fields=['parent_position', 'department'])
            except Position.DoesNotExist:
                pass  # Position was deleted, skip

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing existing object
            return self.readonly_fields + ('user',)
        return self.readonly_fields

    @method_decorator(staff_member_required)
    def cabinet_user_details(self, request, object_id):
        try:
            cabinet_user = self.get_object(request, object_id)
            if cabinet_user is None:
                raise self.model.DoesNotExist

            # Get all quiz attempts for this user if they exist
            from app_study.models import QuizAttempt
            quiz_attempts = QuizAttempt.objects.filter(
                user=cabinet_user.user
            ).select_related(
                'quiz'
            ).order_by('-started_at')

            context = {
                'title': _('User Details: %(name)s') % {
                    'name': cabinet_user.user.get_full_name() or cabinet_user.user.username
                },
                'cabinet_user': cabinet_user,
                'quiz_attempts': quiz_attempts,
                'opts': self.model._meta,
                'has_change_permission': self.has_change_permission(request, cabinet_user),
                'has_delete_permission': self.has_delete_permission(request, cabinet_user),
                'app_label': self.model._meta.app_label,
            }

            return render(
                request,
                'admin/app_cabinet/cabinet_user_details.html',
                context
            )
        except Exception as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
            return redirect('admin:app_cabinet_cabinetuser_changelist')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/user-details/',
                self.admin_site.admin_view(self.cabinet_user_details),
                name='cabinet_user_details'
            ),
            path(
                '<path:object_id>/login-as/',
                self.admin_site.admin_view(self.login_as_user),
                name='app_cabinet_cabinetuser_login_as',
            ),
        ]
        return custom_urls + urls

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/cabinet_user_admin.js',)


# Custom User Admin with password change functionality
class CustomUserAdmin(UserAdmin):
    """
    Custom User Admin that makes password change more accessible
    """
    inlines = [CabinetUserInline]
    
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'get_company',
        'get_department',
        'get_position',
        'require_two_factor',
        'password_change_link'
    )
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'groups',
        'cabinet__company',
        'cabinet__department',
        'cabinet__position',
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    # Explicitly include change_password in the fieldsets
    fieldsets = (
        (None, {'fields': ('username',)}),
        (_('Password'), {'fields': ('password',), 'classes': ('collapse',), 
            'description': format_html('<a class="changelink" href="../password/">{}</a>', _('Change password'))}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    # Custom fieldsets for adding users with password fields
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Use select_related with LEFT OUTER JOIN to handle users without cabinet records
        # This is more efficient than prefetch_related for OneToOne relationships
        return qs.select_related(
            'cabinet',
            'cabinet__company',
            'cabinet__department',
            'cabinet__position'
        )

    def _get_cabinet(self, obj):
        try:
            return obj.cabinet
        except CabinetUser.DoesNotExist:
            return None

    def get_company(self, obj):
        cabinet = self._get_cabinet(obj)
        return cabinet.company if cabinet else None

    get_company.short_description = _('Company')
    get_company.admin_order_field = 'cabinet__company__name'

    def get_department(self, obj):
        cabinet = self._get_cabinet(obj)
        if cabinet and cabinet.department:
            return cabinet.department.get_name()
        return None

    get_department.short_description = _('Department')
    get_department.admin_order_field = 'cabinet__department__name'

    def get_position(self, obj):
        cabinet = self._get_cabinet(obj)
        if cabinet and cabinet.position:
            return cabinet.position.get_name()
        return None

    get_position.short_description = _('Position')
    get_position.admin_order_field = 'cabinet__position__name'

    def require_two_factor(self, obj):
        cabinet = self._get_cabinet(obj)
        if cabinet:
            return cabinet.force_two_factor
        return False

    require_two_factor.short_description = _('Require 2FA')
    require_two_factor.boolean = True

    def get_dates(self, obj):
        cabinet = self._get_cabinet(obj)
        if cabinet:
            start = cabinet.start_date.strftime('%Y-%m-%d') if cabinet.start_date else '---'
            end = cabinet.end_date.strftime('%Y-%m-%d') if cabinet.end_date else '---'
            return f"{start} → {end}"
        return None

    get_dates.short_description = _('Employment Period')

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)

    def changelist_view(self, request, extra_context=None):
        """
        Override changelist_view to handle DoesNotExist errors gracefully
        when filters reference deleted objects
        """
        try:
            return super().changelist_view(request, extra_context)
        except Exception as e:
            # If there's a DoesNotExist error, it's likely due to a filter
            # referencing a deleted object. Clear the problematic filter parameters.
            error_str = str(e)
            if ('DoesNotExist' in str(type(e).__name__) or 
                'matching query does not exist' in error_str or
                'Control matching query does not exist' in error_str):
                
                # Get the GET parameters and remove filter-related ones
                from django.http import QueryDict
                from django.shortcuts import redirect
                from django.urls import reverse
                
                get_params = request.GET.copy()
                
                # Remove filter parameters that might be causing issues
                # These are the cabinet-related filters that could reference deleted objects
                problematic_keys = [
                    'cabinet__company__id__exact',
                    'cabinet__department__id__exact', 
                    'cabinet__position__id__exact',
                    'cabinet__company',
                    'cabinet__department',
                    'cabinet__position',
                ]
                
                # Also remove any keys containing '__' (related field filters)
                filter_keys = [key for key in get_params.keys() 
                              if any(prob in key for prob in problematic_keys) or 
                                 ('__' in key and 'cabinet' in key)]
                
                for key in filter_keys:
                    if key in get_params:
                        del get_params[key]
                
                # Redirect to the changelist without the problematic filters
                url = reverse('admin:auth_user_changelist')
                if get_params:
                    url += '?' + get_params.urlencode()
                return redirect(url)
            # Re-raise if it's a different error
            raise

    def get_urls(self):
        """
        Ensure the standard UserAdmin change password URL is preserved
        """
        urls = super().get_urls()
        return urls

    def password_change_link(self, obj):
        """
        Add a direct link to change user's password
        """
        url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return format_html('<a class="button" href="{}">{}</a>', url, _('Change Password'))
    
    password_change_link.short_description = _('Password')
    password_change_link.allow_tags = True


class CabinetPasswordCompanyLinkInline(admin.TabularInline):
    model = CabinetPasswordCompanyLink
    extra = 1


@admin.register(CabinetSettings)
class CabinetSettingsAdmin(admin.ModelAdmin):
    inlines = [CabinetPasswordCompanyLinkInline]


@admin.register(CabinetPasswordCompanyLink)
class CabinetPasswordCompanyLinkAdmin(admin.ModelAdmin):
    list_display = ('cabinet_password', 'company')
    list_filter = ('company',)


@admin.register(CabinetTaskReminderSchedule)
class CabinetTaskReminderScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'company',
        'frequency',
        'send_time',
        'is_active',
        'last_sent_at',
        'created_at',
    )
    list_filter = ('frequency', 'is_active', 'company')
    filter_horizontal = ('recipients',)
    raw_id_fields = ('created_by',)
    readonly_fields = ('last_sent_at', 'created_at', 'periodic_task')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.sync_periodic_task()


class CabinetADConnectionAdminForm(forms.ModelForm):
    """Form that uses a password widget for bind_password and keeps existing password when left blank on edit."""
    class Meta:
        model = CabinetADConnection
        fields = '__all__'
        widgets = {
            'bind_password': forms.PasswordInput(attrs={
                'autocomplete': 'new-password',
                'placeholder': '••••••••',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields.get('bind_password'):
            self.fields['bind_password'].help_text = _('Leave blank to keep the current password when editing.')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk and not self.cleaned_data.get('bind_password'):
            instance.bind_password = CabinetADConnection.objects.get(pk=instance.pk).bind_password
        if commit:
            instance.save()
        return instance


@admin.register(CabinetADConnection)
class CabinetADConnectionAdmin(admin.ModelAdmin):
    form = CabinetADConnectionAdminForm
    list_display = ('name', 'company', 'server_url', 'port', 'use_ssl', 'is_active', 'test_connection_button')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'server_url', 'company__name')
    raw_id_fields = ()
    fieldsets = (
        (None, {'fields': ('company', 'name', 'is_active', 'sync_ad_groups_to_cabinet')}),
        (_('Server'), {'fields': ('server_url', 'port', 'use_ssl')}),
        (_('Bind account'), {'fields': ('bind_dn', 'bind_password')}),
        (_('Search'), {'fields': ('base_dn', 'user_search_ou', 'user_filter')}),
        (_('Attribute mapping'), {'fields': ('attr_username', 'attr_email', 'attr_first_name', 'attr_last_name', 'attr_phone', 'attr_start_date', 'attr_end_date')}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/test-connection/',
                self.admin_site.admin_view(self.test_connection_view),
                name='app_cabinet_cabinetadconnection_test_connection',
            ),
        ]
        return custom + urls

    def test_connection_view(self, request, object_id):
        from .backends import _get_ldap_connection
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
        try:
            conn = CabinetADConnection.objects.get(pk=object_id)
        except CabinetADConnection.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': _('Connection not found.')})
        ldap_conn = _get_ldap_connection(
            conn.server_url,
            conn.port,
            conn.use_ssl,
            conn.bind_dn,
            conn.bind_password,
        )
        if ldap_conn:
            try:
                ldap_conn.unbind()
            except Exception:
                pass
            return JsonResponse({
                'status': 'success',
                'message': _('Connection to %s:%s successful.') % (conn.server_url, conn.port),
            })
        return JsonResponse({
            'status': 'error',
            'message': _('Failed to connect to %s:%s. Check server URL, port, SSL, and bind credentials.') % (conn.server_url, conn.port),
        })

    def test_connection_button(self, obj):
        if not obj.pk:
            return ""
        url = reverse('admin:app_cabinet_cabinetadconnection_test_connection', args=[obj.pk])
        return format_html(
            '<button type="button" class="cabinet-test-ad-btn" data-url="{}">{}</button>',
            url,
            _('Test Connection'),
        )
    test_connection_button.short_description = _('Test Connection')

    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/cabinet_test_ad_connection.js')


@admin.register(CabinetGroup)
class CabinetGroupAdmin(admin.ModelAdmin):
   list_display = (
       'group',
       'name',
       'company',
       'color',
       'get_description'
   )
   list_filter = ('company',)
   search_fields = (
       'group__name',
       'name',
       'description',
       'company__name'
   )

   fieldsets = (
       (None, {
           'fields': ('group', 'company', 'color')
       }),
       (_('Details'), {
           'fields': ('name', 'description')
       }),
   )

   def get_description(self, obj):
       return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else (obj.description or '')

   get_description.short_description = _('Description')


@admin.register(PlatformRole)
class PlatformRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'order', 'color', 'display_companies')
    list_filter = ('is_active', 'companies')
    search_fields = ('name', 'slug', 'description')
    filter_horizontal = ('companies', 'groups')
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'is_active', 'color', 'order')}),
        (_('Companies (from Access to Cabinet Management)'), {'fields': ('companies',)}),
        (_('Access Groups'), {'fields': ('groups',)}),
        (_('Allowed metrics/modules'), {'fields': ('allowed_metrics_modules',)}),
    )

    def display_companies(self, obj):
        return ', '.join(c.name for c in obj.companies.all()[:5]) or _('All')
    display_companies.short_description = _('Companies')


@admin.register(PlatformRoleDashboardConfig)
class PlatformRoleDashboardConfigAdmin(admin.ModelAdmin):
    list_display = ('platform_role', 'updated_at')
    search_fields = ('platform_role__name',)
    readonly_fields = ('updated_at',)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key', 'ip_address', 'user_agent', 'login_time')
    search_fields = ('user__username', 'session_key', 'ip_address', 'user_agent')


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')
    search_fields = ('user__username', 'action')


# Unregister the default User admin and register our custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(AccessOptions)
class AccessOptionsAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'has_access_users',
        'has_access_roles',
        'has_access_groups',
        'has_access_org_structure',
        'has_access_org_chart',
        'has_access_site_statistics',
        'display_companies'
    ]
    list_editable = [
        'has_access_users',
        'has_access_roles',
        'has_access_groups',
        'has_access_org_structure',
        'has_access_org_chart',
        'has_access_site_statistics'
    ]
    list_filter = [
        'has_access_users',
        'has_access_roles',
        'has_access_groups',
        'has_access_org_structure',
        'has_access_org_chart',
        'has_access_site_statistics',
        'companies'
    ]
    search_fields = ['group__name', 'companies__name', 'description']
    filter_horizontal = ['companies']
    
    # Add actions for bulk operations
    actions = ['enable_users_access', 'disable_users_access', 'enable_groups_access', 'disable_groups_access', 'enable_org_chart_access', 'disable_org_chart_access']
    
    fieldsets = (
        (_('Group'), {
            'fields': ('group',)
        }),
        (_('Users Management Permissions'), {
            'fields': (
                'has_access_users',
                'can_add_users',
                'can_edit_users',
                'can_delete_users',
                'can_export_users',
            )
        }),
        (_('Roles Management Permissions'), {
            'fields': (
                'has_access_roles',
                'can_add_roles',
                'can_edit_roles',
                'can_delete_roles',
            )
        }),
        (_('Groups Management Permissions'), {
            'fields': (
                'has_access_groups',
                'can_add_groups',
                'can_edit_groups',
                'can_delete_groups',
            )
        }),
        (_('Organization Structure Permissions'), {
            'fields': (
                'has_access_org_structure',
                'can_add_companies',
                'can_edit_companies',
                'can_delete_companies',
                'can_add_departments',
                'can_edit_departments',
                'can_delete_departments',
                'can_add_positions',
                'can_edit_positions',
                'can_delete_positions',
            )
        }),
        (_('Organization Chart Permissions'), {
            'fields': (
                'has_access_org_chart',
            )
        }),
        (_('Site Statistics Permissions'), {
            'fields': (
                'has_access_site_statistics',
                'can_export_statistics',
                'can_view_detailed_statistics',
            )
        }),
        (_('Companies and Description'), {
            'fields': (
                'companies',
                'description',
            )
        })
    )

    def display_companies(self, obj):
        return ", ".join([company.name for company in obj.companies.all()])
    display_companies.short_description = _("Companies")
    
    # Bulk actions
    def enable_users_access(self, request, queryset):
        updated = queryset.update(has_access_users=True)
        self.message_user(request, f'{updated} records updated with users access enabled.')
    enable_users_access.short_description = _("Enable users access for selected items")
    
    def disable_users_access(self, request, queryset):
        updated = queryset.update(has_access_users=False)
        self.message_user(request, f'{updated} records updated with users access disabled.')
    disable_users_access.short_description = _("Disable users access for selected items")
    
    def enable_groups_access(self, request, queryset):
        updated = queryset.update(has_access_groups=True)
        self.message_user(request, f'{updated} records updated with groups access enabled.')
    enable_groups_access.short_description = _("Enable groups access for selected items")
    
    def disable_groups_access(self, request, queryset):
        updated = queryset.update(has_access_groups=False)
        self.message_user(request, f'{updated} records updated with groups access disabled.')
    disable_groups_access.short_description = _("Disable groups access for selected items")
    
    def enable_org_chart_access(self, request, queryset):
        updated = queryset.update(has_access_org_chart=True)
        self.message_user(request, f'{updated} records updated with org chart access enabled.')
    enable_org_chart_access.short_description = _("Enable org chart access for selected items")
    
    def disable_org_chart_access(self, request, queryset):
        updated = queryset.update(has_access_org_chart=False)
        self.message_user(request, f'{updated} records updated with org chart access disabled.')
    disable_org_chart_access.short_description = _("Disable org chart access for selected items")
    
    # Override delete methods to handle the JavaScript issue
    def delete_model(self, request, obj):
        """Handle single object deletion"""
        try:
            super().delete_model(request, obj)
        except Exception as e:
            self.message_user(request, f'Error deleting {obj}: {str(e)}', level='ERROR')
    
    def delete_queryset(self, request, queryset):
        """Handle bulk deletion"""
        try:
            count = queryset.count()
            queryset.delete()
            self.message_user(request, f'{count} items deleted successfully.')
        except Exception as e:
            self.message_user(request, f'Error during bulk deletion: {str(e)}', level='ERROR')
    
    class Media:
        css = {
            'all': ('admin/css/widgets.css',)
        }
        js = ('admin/js/fix_permissions_policy.js',)  # Include our fix


class OrgStructureGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OrgStructureGuideTranslationInline(OrgStructureGuideTranslationInlineMixin, admin.StackedInline):
    model = OrgStructureGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/org_structure_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(OrgStructureGuide)
class OrgStructureGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [OrgStructureGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_cabinet/orgstructureguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['org_structure_guide_translate_url'] = reverse('org_structure_guide_translate')
        except Exception:
            extra_context['org_structure_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['org_structure_guide_translate_url'] = reverse('org_structure_guide_translate')
        except Exception:
            extra_context['org_structure_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class CabinetUsersGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CabinetUsersGuideTranslationInline(CabinetUsersGuideTranslationInlineMixin, admin.StackedInline):
    model = CabinetUsersGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/cabinet_users_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(CabinetUsersGuide)
class CabinetUsersGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [CabinetUsersGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_cabinet/cabinetusersguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['cabinet_users_guide_translate_url'] = reverse('cabinet_users_guide_translate')
        except Exception:
            extra_context['cabinet_users_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['cabinet_users_guide_translate_url'] = reverse('cabinet_users_guide_translate')
        except Exception:
            extra_context['cabinet_users_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class CabinetGroupsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CabinetGroupsGuideTranslationInline(CabinetGroupsGuideTranslationInlineMixin, admin.StackedInline):
    model = CabinetGroupsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/cabinet_groups_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(CabinetGroupsGuide)
class CabinetGroupsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [CabinetGroupsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_cabinet/cabinetgroupsguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['cabinet_groups_guide_translate_url'] = reverse('cabinet_groups_guide_translate')
        except Exception:
            extra_context['cabinet_groups_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['cabinet_groups_guide_translate_url'] = reverse('cabinet_groups_guide_translate')
        except Exception:
            extra_context['cabinet_groups_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)