# D:\Python\MyProject\SecBoard\SecBoard\app_study\models.py
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import Group
from django.utils.translation import gettext as _
from app_conf.models import Company, MailAccount
from django.urls import reverse
from tinymce.models import HTMLField
import uuid



class Quiz(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(verbose_name=_("Description"))
    shuffle_questions = models.BooleanField(
        default=False, verbose_name=_("Shuffle Questions"))
    shuffle_answers = models.BooleanField(
        default=False, verbose_name=_("Shuffle Answers"))
    passing_score = models.IntegerField(
        default=0, verbose_name=_("Passing Score"))
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_("Updated At"))
    youtube_video_id = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("YouTube Video ID"))
    pdf_material = models.FileField(
        upload_to='quiz_pdfs/', null=True, blank=True, verbose_name=_("PDF Material"))
    pdf_filename = models.CharField(
        max_length=255, blank=True, verbose_name=_("PDF Filename"))
    companies = models.ManyToManyField(
        Company, related_name='quizzes', blank=True, verbose_name=_("Companies"))
    cabinet_groups = models.ManyToManyField(
        'app_cabinet.CabinetGroup', related_name='quizzes', blank=True, verbose_name=_("Cabinet Groups"))
    cabinet_users = models.ManyToManyField(
        'app_cabinet.CabinetUser', related_name='quizzes', blank=True, verbose_name=_("Cabinet Users"))
    page = models.ForeignKey(
        'Page', on_delete=models.SET_NULL, null=True, blank=True, related_name='quizzes', verbose_name=_("Page"))

    def __str__(self):
        return self.title

    def get_pdf_url(self):
        if self.pdf_material:
            return reverse('protected_quiz_pdf', kwargs={'quiz_id': self.id})
        return None

    def save(self, *args, **kwargs):
        if self.pdf_material and not self.pdf_filename:
            self.pdf_filename = self.pdf_material.name
        super().save(*args, **kwargs)

    def has_user_access(self, user):
        """Check if a user has access to this quiz"""
        try:
            cabinet_user = user.cabinet
        except AttributeError:
            return False
        
        # First check if user's company is in quiz companies
        user_company_in_quiz = self.companies.filter(id=cabinet_user.company.id).exists()
        if not user_company_in_quiz:
            return False
        
        # Check if there are any specific groups or users defined
        has_specific_groups = self.cabinet_groups.exists()
        has_specific_users = self.cabinet_users.exists()
        
        # If no specific groups or users are defined, all users from selected companies have access
        if not has_specific_groups and not has_specific_users:
            return True
        
        # If specific groups or users are defined, check access
        # Check cabinet user direct access
        if self.cabinet_users.filter(id=cabinet_user.id).exists():
            return True
        
        # Check cabinet group access
        user_groups = user.groups.all()
        cabinet_groups = self.cabinet_groups.filter(group__in=user_groups)
        if cabinet_groups.exists():
            return True
        
        return False

    class Meta:
        verbose_name = _("Quiz")
        verbose_name_plural = _("Quizzes")


class EmailTemplate(models.Model):
    """Model for storing email templates for quiz reminders"""
    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name='email_templates', verbose_name=_("Quiz"))
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    body = models.TextField(verbose_name=_("Body"))
    is_default = models.BooleanField(default=False, verbose_name=_("Default Template"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))
    
    def __str__(self):
        return f"Email Template for {self.quiz.title}"
    
    class Meta:
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")
        unique_together = ['quiz', 'is_default']
    
    def save(self, *args, **kwargs):
        # Ensure only one default template per quiz
        if self.is_default:
            EmailTemplate.objects.filter(quiz=self.quiz, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ScheduledReminder(models.Model):
    INTERVAL_CHOICES = [
        ('once', _('Once')),
        ('week', _('Weekly')),
        ('month', _('Monthly')),
        ('quarter', _('Quarterly')),
        ('half_year', _('Half Yearly')),
    ]
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='scheduled_reminders')
    email_account = models.ForeignKey('app_conf.MailAccount', on_delete=models.CASCADE)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES)
    is_active = models.BooleanField(default=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    next_send = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Target users (can be specific users, groups, or all users with access)
    target_users = models.ManyToManyField('auth.User', blank=True, related_name='scheduled_reminders')
    target_groups = models.ManyToManyField('auth.Group', blank=True, related_name='scheduled_reminders')
    target_all_users = models.BooleanField(default=False)  # Send to all users with quiz access
    
    class Meta:
        verbose_name = _("Scheduled Reminder")
        verbose_name_plural = _("Scheduled Reminders")
        ordering = ['-created_at']

    def __str__(self):
        return f"Scheduled Reminder for {self.quiz.title} - {self.get_interval_display()}"

    def get_next_send_date(self):
        """Calculate next send date based on interval"""
        from datetime import datetime, timedelta
        from dateutil.relativedelta import relativedelta
        
        if self.interval == 'once':
            # For once interval, return the next_send date that was set when created
            return self.next_send
        
        if self.last_sent:
            base_date = self.last_sent
        else:
            base_date = datetime.now()
        
        if self.interval == 'week':
            return base_date + timedelta(weeks=1)
        elif self.interval == 'month':
            return base_date + relativedelta(months=1)
        elif self.interval == 'quarter':
            return base_date + relativedelta(months=3)
        elif self.interval == 'half_year':
            return base_date + relativedelta(months=6)
        
        return base_date + timedelta(days=7)  # Default to weekly

    def get_target_users(self):
        """Get all users who should receive this reminder"""
        from app_cabinet.models import CabinetUser
        
        users = set()
        
        # Add specific users
        users.update(self.target_users.all())
        
        # Add users from target groups
        for group in self.target_groups.all():
            users.update(group.user_set.all())
        
        # Add all users with quiz access if target_all_users is True
        if self.target_all_users:
            quiz_companies = self.quiz.companies.all()
            cabinet_users = CabinetUser.objects.filter(company__in=quiz_companies)
            
            for cabinet_user in cabinet_users:
                user = cabinet_user.user
                # Check if user has access to this quiz
                if self.quiz.has_user_access(user):
                    users.add(user)
        
        return list(users)

    def should_send_now(self):
        """Check if reminder should be sent now"""
        from django.utils import timezone
        return self.is_active and self.next_send <= timezone.now()

    def mark_sent(self):
        """Mark reminder as sent and calculate next send date"""
        from django.utils import timezone
        self.last_sent = timezone.now()
        
        if self.interval == 'once':
            # For once interval, deactivate after sending
            self.is_active = False
            self.next_send = self.last_sent  # Keep the same date
        else:
            # For recurring intervals, calculate next send date
            self.next_send = self.get_next_send_date()
        
        self.save()


class ReminderLog(models.Model):
    """Log of sent reminders for tracking"""
    scheduled_reminder = models.ForeignKey(ScheduledReminder, on_delete=models.CASCADE, related_name='logs')
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    recipients = models.ManyToManyField(User, related_name='received_scheduled_quiz_emails', blank=True, verbose_name=_("Recipients"))
    
    class Meta:
        verbose_name = _("Reminder Log")
        verbose_name_plural = _("Reminder Logs")
        ordering = ['-sent_at']

    def __str__(self):
        return f"Reminder Log for {self.scheduled_reminder} - {self.sent_at}"


class ImmediateEmailLog(models.Model):
    """Log of immediate emails sent through 'Send Now' feature"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='immediate_email_logs')
    sent_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Sent By"), related_name='sent_immediate_emails')
    sent_at = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    email_account = models.ForeignKey('app_conf.MailAccount', on_delete=models.SET_NULL, null=True, blank=True)
    recipients = models.ManyToManyField(User, related_name='received_quiz_emails', blank=True, verbose_name=_("Recipients"))
    
    class Meta:
        verbose_name = _("Immediate Email Log")
        verbose_name_plural = _("Immediate Email Logs")
        ordering = ['-sent_at']

    def __str__(self):
        return f"Immediate Email for {self.quiz.title} - {self.sent_at}"


class Question(models.Model):
    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name='questions', verbose_name=_("Quiz"))
    text = models.TextField(verbose_name=_("Text"))
    order = models.IntegerField(default=0, verbose_name=_("Order"))

    def __str__(self):
        return self.text[:50] + '...' if len(self.text) > 50 else self.text

    def total_score(self):
        return self.answers.aggregate(total=Sum('score'))['total'] or 0

    class Meta:
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")


class Answer(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name='answers', verbose_name=_("Question"))
    text = models.TextField(verbose_name=_("Text"))
    is_correct = models.BooleanField(
        default=False, verbose_name=_("Correct Answer"))
    score = models.IntegerField(default=0, verbose_name=_("Score"))

    def __str__(self):
        return self.text[:50] + '...' if len(self.text) > 50 else self.text

    class Meta:
        verbose_name = _("Answer")
        verbose_name_plural = _("Answers")


class QuizAttempt(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name=_("User"))
    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, verbose_name=_("Quiz"))
    score = models.IntegerField(default=0, verbose_name=_("Score"))
    completed = models.BooleanField(
        default=False, verbose_name=_("Completed"))
    started_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Started At"))
    completed_at = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Completed At"))
    
    # Add secure token to prevent IDOR attacks (temporarily commented until migration)
    # secure_token = models.UUIDField(
    #     default=uuid.uuid4, 
    #     editable=False, 
    #     unique=True,
    #     verbose_name=_("Secure Token"),
    #     help_text=_("Cryptographically secure token for accessing this attempt")
    # )

    def __str__(self):
        return f"{self.user.email} - {self.quiz.title}"

    class Meta:
        verbose_name = _("Quiz Attempt")
        verbose_name_plural = _("Quiz Attempts")


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(
        'QuizAttempt', on_delete=models.CASCADE, related_name='answers', verbose_name=_("Attempt"))
    question = models.ForeignKey(
        'Question', on_delete=models.CASCADE, verbose_name=_("Question"))
    answer = models.ForeignKey(
        'Answer', on_delete=models.CASCADE, verbose_name=_("Answer"))
    is_correct = models.BooleanField(
        default=False, verbose_name=_("Correct Answer"))

    def save(self, *args, **kwargs):
        self.is_correct = self.answer.is_correct
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.attempt.user.username} - {self.question.text[:20]}..."

    def get_correct_answer(self):
        return self.question.answers.filter(is_correct=True).first()

    class Meta:
        verbose_name = _("Quiz Question Answer")
        verbose_name_plural = _("Quiz Question Answers")


class AccessQuiz(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Quiz"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Quiz"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page"))
    has_access_to_results = models.BooleanField(default=False, verbose_name=_("Has access to Quiz Results"))
    companies = models.ManyToManyField(Company, blank=True, related_name='access_quiz', verbose_name=_("Companies"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Access to Quiz")
        verbose_name_plural = _("Access to Quiz")

    def __str__(self):
        return f"{self.group.name} - Access: {self.has_access}, Edit: {self.can_edit}"
    
    def delete(self, *args, **kwargs):
        """Custom delete method to handle foreign key constraints"""
        from django.db import connection
        
        try:
            # First, try to delete any related records in the app_quiz_accessquiz_companies table
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM app_quiz_accessquiz_companies 
                    WHERE accessquiz_id = %s
                """, [self.id])
            
            # Then proceed with normal deletion
            super().delete(*args, **kwargs)
        except Exception as e:
            # If the table doesn't exist or there's an error, just proceed with normal deletion
            super().delete(*args, **kwargs)


class QuizResultsSettings(models.Model):
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name='quiz_results_settings', verbose_name=_("Group"))
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='quiz_results_settings', verbose_name=_("Company"))

    class Meta:
        verbose_name = _("Quiz Results Settings")
        verbose_name_plural = _("Quiz Results Settings")
        unique_together = ('group', 'company')

    def __str__(self):
        return f"{self.group.name} - {self.company.name}"


class AccessPage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Page Manager"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Pages"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page"))
    companies = models.ManyToManyField(Company, blank=True, related_name='access_page', verbose_name=_("Companies"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Access to Page Manager")
        verbose_name_plural = _("Access to Page Manager")

    def __str__(self):
        return f"{self.group.name} - Access: {self.has_access}, Edit: {self.can_edit}"
    
    def delete(self, *args, **kwargs):
        """Custom delete method to handle foreign key constraints"""
        from django.db import connection
        
        try:
            # First, try to delete any related records in the app_quiz_accesspage_companies table
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM app_quiz_accesspage_companies 
                    WHERE accesspage_id = %s
                """, [self.id])
            
            # Then proceed with normal deletion
            super().delete(*args, **kwargs)
        except Exception as e:
            # If the table doesn't exist or there's an error, just proceed with normal deletion
            super().delete(*args, **kwargs)


class Page(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    slug = models.SlugField(unique=True, verbose_name=_("Slug"))
    content = HTMLField(blank=True, null=True, verbose_name='Content (Rich Text)')
    html_content = models.TextField(
        blank=True, null=True, verbose_name=_("Content (HTML)"))
    use_html = models.BooleanField(
        default=False, verbose_name=_("Use HTML"))
    link_url = models.URLField(
        blank=True, null=True, verbose_name=_("External Link"))
    youtube_id = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("YouTube Video ID"))
    
    # Media files
    video_file = models.FileField(
        upload_to='pages/videos/', 
        blank=True, 
        null=True, 
        verbose_name=_("Video File"),
        help_text=_("Upload video file (MP4, WebM, OGV)")
    )
    audio_file = models.FileField(
        upload_to='pages/audio/', 
        blank=True, 
        null=True, 
        verbose_name=_("Audio File"),
        help_text=_("Upload audio file (MP3, WAV, OGG)")
    )
    
    companies = models.ManyToManyField(
        Company, related_name='accessible_pages', blank=True, verbose_name=_("Companies"))
    cabinet_groups = models.ManyToManyField(
        'app_cabinet.CabinetGroup', related_name='pages', blank=True, verbose_name=_("Cabinet Groups"))
    cabinet_users = models.ManyToManyField(
        'app_cabinet.CabinetUser', related_name='pages', blank=True, verbose_name=_("Cabinet Users"))
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created"))
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_("Updated"))
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"))

    def __str__(self):
        return self.title

    def has_user_access(self, user):
        """Check if a user has access to this page"""
        try:
            cabinet_user = user.cabinet
        except AttributeError:
            return False
        
        # First check if user's company is in page companies
        user_company_in_page = self.companies.filter(id=cabinet_user.company.id).exists()
        if not user_company_in_page:
            return False
        
        # Check if there are any specific groups or users defined
        has_specific_groups = self.cabinet_groups.exists()
        has_specific_users = self.cabinet_users.exists()
        
        # If no specific groups or users are defined, all users from selected companies have access
        if not has_specific_groups and not has_specific_users:
            return True
        
        # If specific groups or users are defined, check access
        # Check cabinet user direct access
        if self.cabinet_users.filter(id=cabinet_user.id).exists():
            return True
        
        # Check cabinet group access
        user_groups = user.groups.all()
        cabinet_groups = self.cabinet_groups.filter(group__in=user_groups)
        if cabinet_groups.exists():
            return True
        
        return False

    class Meta:
        ordering = ['title']
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    def get_content(self):
        return self.html_content if self.use_html else self.content


class PageYouTubeVideo(models.Model):
    """Model for storing multiple YouTube videos for a page"""
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='youtube_videos',
        verbose_name=_("Page")
    )
    title = models.CharField(
        max_length=200, 
        verbose_name=_("Video Title"),
        help_text=_("Title for this YouTube video")
    )
    youtube_id = models.CharField(
        max_length=20, 
        verbose_name=_("YouTube Video ID"),
        help_text=_("YouTube video ID (e.g., dQw4w9WgXcQ)")
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description"),
        help_text=_("Optional description for this video")
    )
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name=_("Order"),
        help_text=_("Order of display (lower numbers first)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = _("Page YouTube Video")
        verbose_name_plural = _("Page YouTube Videos")

    def __str__(self):
        return f"{self.page.title} - {self.title}"

    @property
    def embed_url(self):
        return f"https://www.youtube.com/embed/{self.youtube_id}"

    @property
    def watch_url(self):
        return f"https://www.youtube.com/watch?v={self.youtube_id}"


class PageURL(models.Model):
    """Model for storing multiple URLs for a page"""
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='page_urls',
        verbose_name=_("Page")
    )
    title = models.CharField(
        max_length=200, 
        verbose_name=_("Link Title"),
        help_text=_("Display title for this link")
    )
    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("Full URL including http:// or https://")
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description"),
        help_text=_("Optional description for this link")
    )
    open_in_new_tab = models.BooleanField(
        default=True, 
        verbose_name=_("Open in New Tab"),
        help_text=_("Whether to open this link in a new tab")
    )
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name=_("Order"),
        help_text=_("Order of display (lower numbers first)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = _("Page URL")
        verbose_name_plural = _("Page URLs")

    def __str__(self):
        return f"{self.page.title} - {self.title}"


class PageVideoFile(models.Model):
    """Model for storing multiple video files for a page"""
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='video_files',
        verbose_name=_("Page")
    )
    title = models.CharField(
        max_length=200, 
        verbose_name=_("Video Title"),
        help_text=_("Title for this video file")
    )
    video_file = models.FileField(
        upload_to='pages/videos/', 
        verbose_name=_("Video File"),
        help_text=_("Upload video file (MP4, WebM, OGV, AVI, MOV)")
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description"),
        help_text=_("Optional description for this video")
    )
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name=_("Order"),
        help_text=_("Order of display (lower numbers first)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = _("Page Video File")
        verbose_name_plural = _("Page Video Files")

    def __str__(self):
        return f"{self.page.title} - {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.video_file:
            # Check file size (max 100MB)
            if self.video_file.size > 100 * 1024 * 1024:
                raise ValidationError(_('Video file size cannot exceed 100MB.'))
            
            # Check file extension
            allowed_extensions = ['.mp4', '.webm', '.ogv', '.avi', '.mov']
            file_extension = self.video_file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(_('Only MP4, WebM, OGV, AVI, and MOV video files are allowed.'))


class PageAudioFile(models.Model):
    """Model for storing multiple audio files for a page"""
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='audio_files',
        verbose_name=_("Page")
    )
    title = models.CharField(
        max_length=200, 
        verbose_name=_("Audio Title"),
        help_text=_("Title for this audio file")
    )
    audio_file = models.FileField(
        upload_to='pages/audio/', 
        verbose_name=_("Audio File"),
        help_text=_("Upload audio file (MP3, WAV, OGG, M4A, AAC)")
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description"),
        help_text=_("Optional description for this audio")
    )
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name=_("Order"),
        help_text=_("Order of display (lower numbers first)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = _("Page Audio File")
        verbose_name_plural = _("Page Audio Files")

    def __str__(self):
        return f"{self.page.title} - {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.audio_file:
            # Check file size (max 50MB)
            if self.audio_file.size > 50 * 1024 * 1024:
                raise ValidationError(_('Audio file size cannot exceed 50MB.'))
            
            # Check file extension
            allowed_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.aac']
            file_extension = self.audio_file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(_('Only MP3, WAV, OGG, M4A, and AAC audio files are allowed.'))


class PageDocumentFile(models.Model):
    """Model for storing multiple document files for a page"""
    page = models.ForeignKey(
        Page, 
        on_delete=models.CASCADE, 
        related_name='document_files',
        verbose_name=_("Page")
    )
    title = models.CharField(
        max_length=200, 
        verbose_name=_("Document Title"),
        help_text=_("Title for this document file")
    )
    document_file = models.FileField(
        upload_to='pages/documents/', 
        verbose_name=_("Document File"),
        help_text=_("Upload document file (PDF, DOCX, XLSX, PPTX, TXT, RTF)")
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description"),
        help_text=_("Optional description for this document")
    )
    file_type = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_("File Type"),
        help_text=_("Automatically detected file type")
    )
    file_size = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("File Size"),
        help_text=_("File size in bytes")
    )
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name=_("Order"),
        help_text=_("Order of display (lower numbers first)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = _("Page Document File")
        verbose_name_plural = _("Page Document Files")

    def __str__(self):
        return f"{self.page.title} - {self.title}"
    
    def get_file_icon(self):
        """Return Bootstrap icon class based on file type"""
        file_icons = {
            'pdf': 'bi-file-pdf',
            'docx': 'bi-file-word',
            'doc': 'bi-file-word',
            'xlsx': 'bi-file-excel',
            'xls': 'bi-file-excel',
            'pptx': 'bi-file-ppt',
            'ppt': 'bi-file-ppt',
            'txt': 'bi-file-text',
            'rtf': 'bi-file-text',
        }
        return file_icons.get(self.file_type.lower(), 'bi-file-earmark')
    
    def get_file_size_display(self):
        """Return human readable file size"""
        if not self.file_size:
            return ""
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def clean(self):
        from django.core.exceptions import ValidationError
        import os
        
        if self.document_file:
            # Check file size (max 100MB)
            if self.document_file.size > 100 * 1024 * 1024:
                raise ValidationError(_('Document file size cannot exceed 100MB.'))
            
            # Check file extension
            allowed_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.rtf']
            file_extension = os.path.splitext(self.document_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                raise ValidationError(_('Only PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, TXT, and RTF document files are allowed.'))
            
            # Set file type and size
            self.file_type = file_extension[1:]  # Remove the dot
            self.file_size = self.document_file.size


class PageManagerGuide(models.Model):
    """Base Guide for Page Manager. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Page Manager Guide")
        verbose_name_plural = _("Page Manager Guides")

    def __str__(self):
        return _("Page Manager Guide")


class PageManagerGuideTranslation(models.Model):
    """Per-country (language) translations of the Page Manager Guide."""
    guide = models.ForeignKey(
        PageManagerGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="page_manager_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Page Manager Guide Translation")
        verbose_name_plural = _("Page Manager Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class QuizManagerGuide(models.Model):
    """Base Guide for Quiz Manager. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Quiz Manager Guide")
        verbose_name_plural = _("Quiz Manager Guides")

    def __str__(self):
        return _("Quiz Manager Guide")


class QuizManagerGuideTranslation(models.Model):
    """Per-country (language) translations of the Quiz Manager Guide."""
    guide = models.ForeignKey(
        QuizManagerGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="quiz_manager_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Quiz Manager Guide Translation")
        verbose_name_plural = _("Quiz Manager Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"