# D:\Python\MyProject\SecBoard\SecBoard\app_study\admin.py
import csv

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.db.models import Sum, Prefetch
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.html import format_html
from app_cabinet.forms import PageAdminForm
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from .models import  Answer, Question, Quiz, QuizAnswer, \
    QuizAttempt, AccessQuiz, AccessPage, Page, PageYouTubeVideo, PageURL, PageVideoFile, PageAudioFile, PageDocumentFile, EmailTemplate, ScheduledReminder, ReminderLog, ImmediateEmailLog, \
    PageManagerGuide, PageManagerGuideTranslation, QuizManagerGuide, QuizManagerGuideTranslation
from app_conf.models import Company, Country
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django import forms
from django.shortcuts import render
from django.urls import path
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField






# MailAccountInline removed - MailAccount is now managed in app_conf/admin.py


class PageYouTubeVideoInline(admin.TabularInline):
    model = PageYouTubeVideo
    extra = 1
    fields = ('title', 'youtube_id', 'description', 'order')
    ordering = ('order',)


class PageURLInline(admin.TabularInline):
    model = PageURL
    extra = 1
    fields = ('title', 'url', 'description', 'open_in_new_tab', 'order')
    ordering = ('order',)


class PageVideoFileInline(admin.TabularInline):
    model = PageVideoFile
    extra = 1
    fields = ('title', 'video_file', 'description', 'order')
    ordering = ('order',)


class PageAudioFileInline(admin.TabularInline):
    model = PageAudioFile
    extra = 1
    fields = ('title', 'audio_file', 'description', 'order')
    ordering = ('order',)


class PageDocumentFileInline(admin.TabularInline):
    model = PageDocumentFile
    extra = 1
    fields = ('title', 'document_file', 'description', 'order')
    ordering = ('order',)


# MailServer is now registered in app_conf/admin.py


# MailAccount is now registered in app_conf/admin.py




 

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    fields = ('text', 'is_correct', 'score')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'quiz', 'order', 'total_score')
    list_filter = ('quiz',)
    search_fields = ('text', 'quiz__title')
    inlines = [AnswerInline]
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'text':
            kwargs['widget'] = TinyMCE()
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(total_score=Sum('answers__score'))
        return queryset

    def total_score(self, obj):
        return obj.total_score

    total_score.admin_order_field = 'total_score'

    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text

    short_text.short_description = _('Question')

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4


# Add QuizAdminForm with TinyMCE widget for description field
class QuizAdminForm(forms.ModelForm):
    description = forms.CharField(
        widget=TinyMCE(), 
        required=True, 
        label=_("Description")
    )
    
    cabinet_groups = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label=_("Cabinet Groups"),
        help_text=_("Select cabinet groups that should have access to this quiz")
    )
    
    cabinet_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label=_("Cabinet Users"),
        help_text=_("Select individual cabinet users that should have access to this quiz")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app_cabinet.models import CabinetGroup, CabinetUser
        
        # Set querysets with better ordering and display
        self.fields['cabinet_groups'].queryset = CabinetGroup.objects.select_related('company').order_by('name')
        self.fields['cabinet_users'].queryset = CabinetUser.objects.select_related('user', 'company').order_by('user__first_name', 'user__last_name')
    
    class Meta:
        model = Quiz
        fields = '__all__'
    
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    form = QuizAdminForm
    list_display = ('title', 'passing_score', 'total_score', 'get_access_summary', 'created_at', 'updated_at', 'page')
    list_filter = ('companies', 'cabinet_groups', 'page')
    filter_horizontal = ('companies', 'cabinet_groups', 'cabinet_users')
    inlines = [QuestionInline]
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'passing_score', 'shuffle_questions', 'shuffle_answers')
        }),
        (_('Materials'), {
            'fields': ('youtube_video_id', 'pdf_material', 'page'),
        }),
        (_('Access'), {
            'fields': ('companies', 'cabinet_groups', 'cabinet_users'),
            'description': _('Assign quiz access to companies, specific cabinet groups, or individual cabinet users. Users will have access if they match any of these criteria.')
        }),
    )

    def get_access_summary(self, obj):
        """Display a summary of access assignments"""
        summary = []
        
        companies_count = obj.companies.count()
        if companies_count > 0:
            summary.append(f"{companies_count} компанії")
        
        groups_count = obj.cabinet_groups.count()
        if groups_count > 0:
            summary.append(f"{groups_count} групи")
        
        users_count = obj.cabinet_users.count()
        if users_count > 0:
            summary.append(f"{users_count} користувачі")
        
        return ", ".join(summary) if summary else "Немає доступу"
    
    get_access_summary.short_description = _('Access Summary')

    def total_score(self, obj):
        return obj.questions.aggregate(total=Sum('answers__score'))['total'] or 0

    total_score.short_description = _('Total Score')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.prefetch_related('questions__answers')
        return queryset

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        quiz = self.get_object(request, object_id)
        if quiz:
            extra_context['total_score'] = self.total_score(quiz)
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

    class Media:
        js = (
            'admin/js/jquery.init.js',  # Ensure jQuery is properly initialized
            'admin/js/quiz_admin.js',
        )




class CompanyFilter(admin.SimpleListFilter):
    title = _('Company')
    parameter_name = 'company'

    def lookups(self, request, model_admin):
        companies = Company.objects.all()
        return [(company.id, company.name) for company in companies]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__cabinetuser__company__id=self.value())
        return queryset


class QuizAnswerInline(admin.TabularInline):
    model = QuizAnswer
    extra = 0
    readonly_fields = ('question', 'colored_answer', 'is_correct', 'correct_answer')
    can_delete = False
    max_num = 0

    def colored_answer(self, obj):
        color = 'green' if obj.is_correct else 'red'
        return format_html('<span style="color: {};">{}</span>', color, obj.answer.text)
    colored_answer.short_description = _('Given Answer')

    def correct_answer(self, obj):
        if not obj.is_correct:
            correct = obj.get_correct_answer()
            if correct:
                return format_html('<span style="color: green;">{}</span>', correct.text)
        return ''
    correct_answer.short_description = _('Correct Answer')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'started_at', 'completed_at', 'completed')
    list_filter = (
        'completed',
        'quiz',
        'user__cabinet__company',
    )
    search_fields = ('user__username', 'quiz__title')
    readonly_fields = ('started_at', 'completed_at')
    inlines = [QuizAnswerInline]
    actions = ['export_quiz_attempts_csv']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user__cabinet__company',
            'quiz'
        ).prefetch_related(
            Prefetch('answers', queryset=QuizAnswer.objects.select_related('question', 'answer'))
        )

    def get_company(self, obj):
        return obj.user.cabinet.company if hasattr(obj.user, 'cabinet') else None

    get_company.short_description = _('Company')
    get_company.admin_order_field = 'user__cabinet__company__name'

    def get_csv_rows(self, obj, fields):
        rows = []
        for answer in obj.answers.all():
            correct_answer = answer.get_correct_answer()
            row = {
                _('User'): force_str(obj.user.email),
                _('Company'): force_str(obj.user.cabinet.company.name if hasattr(obj.user, 'cabinet') else ''),
                _('Quiz'): force_str(obj.quiz.title),
                _('Score'): force_str(obj.score),
                _('Completed'): force_str(_('Yes') if obj.completed else _('No')),
                _('Started At'): force_str(obj.started_at),
                _('Completed At'): force_str(obj.completed_at or ''),
                _('Question'): force_str(answer.question.text),
                _('Given Answer'): force_str(answer.answer.text),
                _('User Answer'): force_str(answer.answer.text),
                _('Is Correct'): force_str(_('Yes') if answer.is_correct else _('No')),
                _('Correct Answer'): force_str(correct_answer.text if correct_answer and not answer.is_correct else ''),
            }
            rows.append({field: row.get(field, '') for field in fields})
        return rows


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'colored_answer', 'is_correct', 'correct_answer')
    list_filter = ('attempt__quiz', 'is_correct')
    search_fields = ('attempt__user__username', 'attempt__user__email', 'question__text')
    actions = ['export_quiz_answers_csv']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'attempt__user',
            'attempt__quiz',
            'question',
            'answer'
        )

    def colored_answer(self, obj):
        color = 'green' if obj.is_correct else 'red'
        return format_html('<span style="color: {};">{}</span>', color, obj.answer.text)

    colored_answer.short_description = _('Answer')

    def correct_answer(self, obj):
        if not obj.is_correct:
            correct = obj.get_correct_answer()
            if correct:
                return format_html('<span style="color: green;">{}</span>', correct.text)
        return ''

    correct_answer.short_description = _('Correct Answer')

    def export_quiz_answers_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="quiz_answers.csv"'

        fields = [_('Attempt'), _('Question'), _('Given Answer'), _('Is Correct'), _('Correct Answer')]
        writer = csv.DictWriter(response, fieldnames=fields)
        writer.writeheader()

        for obj in queryset:
            correct_answer = obj.get_correct_answer()
            writer.writerow({
                _('Attempt'): force_str(obj.attempt),
                _('Question'): force_str(obj.question.text),
                _('Given Answer'): force_str(obj.answer.text),
                _('Is Correct'): force_str(_('Yes') if obj.is_correct else _('No')),
                _('Correct Answer'): force_str(correct_answer.text if correct_answer and not obj.is_correct else '')
            })

        return response

    export_quiz_answers_csv.short_description = _("Export selected quiz answers to CSV")

    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }



@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = ('title', 'slug', 'use_html', 'has_link', 'has_youtube', 'has_multiple_youtube', 'has_multiple_urls', 'has_video', 'has_audio', 'has_documents', 'has_multiple_videos', 'has_multiple_audios', 'has_multiple_documents', 'created_at', 'updated_at')
    list_filter = ('companies', 'cabinet_groups', 'use_html')
    search_fields = ('title', 'content', 'link_url', 'youtube_id')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('companies', 'cabinet_groups', 'cabinet_users')
    inlines = [PageYouTubeVideoInline, PageURLInline, PageVideoFileInline, PageAudioFileInline, PageDocumentFileInline]
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'use_html')
        }),
        (_('Content'), {
            'fields': ('content',),
            'description': _('Enter content using the rich text editor.')
        }),
        (_('Legacy Materials'), {
            'fields': ('link_url', 'youtube_id', 'video_file', 'audio_file'),
            'description': _('Legacy fields: Use the sections below for multiple YouTube videos and URLs.'),
            'classes': ('collapse',)
        }),
        (_('Access Control'), {
            'fields': ('companies', 'cabinet_groups', 'cabinet_users'),
            'description': _('Control who can access this page. Companies are required. If Cabinet Groups or Cabinet Users are not selected, all users from selected companies will have access.')
        }),
    )

    def has_link(self, obj):
        return bool(obj.link_url)

    has_link.short_description = _('Has Link')
    has_link.boolean = True

    def has_youtube(self, obj):
        return bool(obj.youtube_id)

    has_youtube.short_description = _('Has YouTube')
    has_youtube.boolean = True

    def has_video(self, obj):
        return bool(obj.video_file)

    has_video.short_description = _('Has Video')
    has_video.boolean = True

    def has_audio(self, obj):
        return bool(obj.audio_file)

    has_audio.short_description = _('Has Audio')
    has_audio.boolean = True

    def has_multiple_youtube(self, obj):
        return obj.youtube_videos.exists()

    has_multiple_youtube.short_description = _('Multiple YouTube')
    has_multiple_youtube.boolean = True

    def has_multiple_urls(self, obj):
        return obj.page_urls.exists()

    has_multiple_urls.short_description = _('Multiple URLs')
    has_multiple_urls.boolean = True

    def has_multiple_videos(self, obj):
        return obj.video_files.exists()

    has_multiple_videos.short_description = _('Multiple Videos')
    has_multiple_videos.boolean = True

    def has_multiple_audios(self, obj):
        return obj.audio_files.exists()

    has_multiple_audios.short_description = _('Multiple Audios')
    has_multiple_audios.boolean = True
    
    def has_documents(self, obj):
        return bool(obj.document_files.count() > 0)
    
    has_documents.boolean = True
    has_documents.short_description = _('Has Documents')
    
    def has_multiple_documents(self, obj):
        return obj.document_files.exists()
    
    has_multiple_documents.short_description = _('Multiple Documents')
    has_multiple_documents.boolean = True

    class Media:
        js = ('admin/js/page_admin.js',)


# def create_quiz_result_group():
#     Group.objects.get_or_create(name=_('quiz_result'))
#
#
# # Call this function when Django starts
# create_quiz_result_group()


# QuizResultsSettings is now integrated into AccessQuiz as has_access_to_results field
# @admin.register(QuizResultsSettings)
# class QuizResultsSettingsAdmin(admin.ModelAdmin):
#     list_display = ('group', 'company')
#     list_filter = ('group', 'company')
#     search_fields = ('group__name', 'company__name')


@admin.register(AccessQuiz)
class AccessQuizAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'can_edit', 'has_access_to_results', 'get_companies_count')
    list_filter = ('has_access', 'can_edit', 'has_access_to_results', 'companies')
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    
    fieldsets = (
        (_('Group Settings'), {
            'fields': ('group',)
        }),
        (_('Permissions'), {
            'fields': ('has_access', 'can_edit', 'has_access_to_results'),
            'description': _('Has access to Quiz controls whether the link is shown on the index page. Has access to Quiz Results controls access to quiz results page.')
        }),
        (_('Company Access'), {
            'fields': ('companies',)
        }),
        (_('Additional Info'), {
            'fields': ('description',)
        }),
    )
    
    def get_companies_count(self, obj):
        count = obj.companies.count()
        if count == 0:
            return format_html('<span style="color: red;">0</span>')
        return count
    get_companies_count.short_description = _('Companies')
    get_companies_count.admin_order_field = 'companies__count'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('companies')


@admin.register(AccessPage)
class AccessPageAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'can_edit', 'get_companies_count')
    list_filter = ('has_access', 'can_edit', 'companies')
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    
    fieldsets = (
        (_('Basic Settings'), {
            'fields': ('group', 'description')
        }),
        (_('Access Permissions'), {
            'fields': ('has_access', 'can_edit'),
            'description': _('Has access to Page Manager controls whether the link is shown on the index page.')
        }),
        (_('Company Access'), {
            'fields': ('companies',)
        }),
    )
    
    def get_companies_count(self, obj):
        return obj.companies.count()
    
    get_companies_count.short_description = _('Companies Count')
    get_companies_count.admin_order_field = 'companies__count'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('companies')


@admin.register(PageYouTubeVideo)
class PageYouTubeVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'youtube_id', 'order', 'created_at')
    list_filter = ('page', 'created_at')
    search_fields = ('title', 'youtube_id', 'page__title')
    list_editable = ('order',)
    ordering = ('page', 'order', 'created_at')


@admin.register(PageURL)
class PageURLAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'url', 'open_in_new_tab', 'order', 'created_at')
    list_filter = ('page', 'open_in_new_tab', 'created_at')
    search_fields = ('title', 'url', 'page__title')
    list_editable = ('order', 'open_in_new_tab')
    ordering = ('page', 'order', 'created_at')


@admin.register(PageVideoFile)
class PageVideoFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'video_file', 'order', 'created_at')
    list_filter = ('page', 'created_at')
    search_fields = ('title', 'page__title')
    list_editable = ('order',)
    ordering = ('page', 'order', 'created_at')
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['video_file'].help_text = _("Max file size: 100MB. Allowed formats: MP4, WebM, OGV, AVI, MOV")
        return form


@admin.register(PageAudioFile)
class PageAudioFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'audio_file', 'order', 'created_at')
    list_filter = ('page', 'created_at')
    search_fields = ('title', 'page__title')
    list_editable = ('order',)
    ordering = ('page', 'order', 'created_at')
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['audio_file'].help_text = _("Max file size: 50MB. Allowed formats: MP3, WAV, OGG, M4A, AAC")
        return form


@admin.register(PageDocumentFile)
class PageDocumentFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'document_file', 'file_type', 'get_file_size_display', 'order', 'created_at')
    list_filter = ('page', 'file_type', 'created_at')
    search_fields = ('title', 'page__title', 'file_type')
    list_editable = ('order',)
    ordering = ('page', 'order', 'created_at')
    readonly_fields = ('file_type', 'file_size')
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['document_file'].help_text = _("Max file size: 100MB. Allowed formats: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, TXT, RTF")
        return form


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['quiz', 'subject', 'is_default', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['quiz__title', 'subject']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ScheduledReminder)
class ScheduledReminderAdmin(admin.ModelAdmin):
    list_display = ['quiz', 'interval', 'is_active', 'next_send', 'last_sent', 'created_at']
    list_filter = ['interval', 'is_active', 'created_at']
    search_fields = ['quiz__title', 'subject_template']
    readonly_fields = ['created_at', 'updated_at', 'last_sent']
    filter_horizontal = ['target_users', 'target_groups']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('quiz', 'email_account', 'interval', 'is_active')
        }),
        ('Email Template', {
            'fields': ('subject_template', 'body_template')
        }),
        ('Target Users', {
            'fields': ('target_users', 'target_groups', 'target_all_users'),
            'description': 'Select specific users/groups or check "Target All Users" to send to all users with quiz access'
        }),
        ('Schedule', {
            'fields': ('next_send', 'last_sent'),
            'description': 'Next send date will be calculated automatically based on interval'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ['scheduled_reminder', 'sent_at', 'sent_count', 'failed_count']
    list_filter = ['sent_at']
    search_fields = ['scheduled_reminder__quiz__title']
    readonly_fields = ['scheduled_reminder', 'sent_at', 'sent_count', 'failed_count', 'error_message']
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'scheduled_reminder__quiz'
        )


@admin.register(ImmediateEmailLog)
class ImmediateEmailLogAdmin(admin.ModelAdmin):
    list_display = ['quiz', 'sent_by', 'sent_at', 'sent_count', 'failed_count', 'email_account']
    list_filter = ['sent_at', 'email_account']
    search_fields = ['quiz__title', 'sent_by__username', 'sent_by__first_name', 'sent_by__last_name', 'subject']
    readonly_fields = ['quiz', 'sent_by', 'sent_at', 'sent_count', 'failed_count', 'error_message', 'email_account', 'subject']
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'quiz', 'sent_by', 'email_account'
        )


class PageManagerGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PageManagerGuideTranslationInline(PageManagerGuideTranslationInlineMixin, admin.StackedInline):
    model = PageManagerGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/page_manager_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(PageManagerGuide)
class PageManagerGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [PageManagerGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_study/pagemanagerguide/change_form.html'

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
            extra_context['page_manager_guide_translate_url'] = reverse('page_manager_guide_translate')
        except Exception:
            extra_context['page_manager_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['page_manager_guide_translate_url'] = reverse('page_manager_guide_translate')
        except Exception:
            extra_context['page_manager_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class QuizManagerGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class QuizManagerGuideTranslationInline(QuizManagerGuideTranslationInlineMixin, admin.StackedInline):
    model = QuizManagerGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/quiz_manager_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(QuizManagerGuide)
class QuizManagerGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [QuizManagerGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_study/quizmanagerguide/change_form.html'

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
            extra_context['quiz_manager_guide_translate_url'] = reverse('quiz_manager_guide_translate')
        except Exception:
            extra_context['quiz_manager_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['quiz_manager_guide_translate_url'] = reverse('quiz_manager_guide_translate')
        except Exception:
            extra_context['quiz_manager_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)