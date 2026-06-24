from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps


class Command(BaseCommand):
    help = 'Move Page data from app_conf to app_study'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write("Starting Page data migration...")
            
            try:
                # Get models from both apps
                from app_conf.models import Page as OldPage, PageYouTubeVideo as OldPageYouTubeVideo, \
                    PageURL as OldPageURL, PageVideoFile as OldPageVideoFile, PageAudioFile as OldPageAudioFile
                from app_study.models import Page as NewPage, PageYouTubeVideo as NewPageYouTubeVideo, \
                    PageURL as NewPageURL, PageVideoFile as NewPageVideoFile, PageAudioFile as NewPageAudioFile
                
                self.stdout.write("Models imported successfully")
                
            except ImportError as e:
                self.stdout.write(self.style.ERROR(f"Error importing models: {e}"))
                return
            
            # Copy Page data
            page_count = 0
            page_mapping = {}
            
            for old_page in OldPage.objects.all():
                try:
                    new_page, created = NewPage.objects.get_or_create(
                        slug=old_page.slug,
                        defaults={
                            'title': old_page.title,
                            'content': old_page.content,
                            'html_content': old_page.html_content,
                            'use_html': old_page.use_html,
                            'link_url': old_page.link_url,
                            'youtube_id': old_page.youtube_id,
                            'video_file': old_page.video_file,
                            'audio_file': old_page.audio_file,
                            'created_at': old_page.created_at,
                            'updated_at': old_page.updated_at,
                        }
                    )
                    
                    if created:
                        # Copy ManyToMany relationships
                        new_page.companies.set(old_page.companies.all())
                        new_page.cabinet_groups.set(old_page.cabinet_groups.all())
                        new_page.cabinet_users.set(old_page.cabinet_users.all())
                        page_count += 1
                        self.stdout.write(f"Created page: {new_page.title}")
                    
                    page_mapping[old_page.id] = new_page
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error creating page {old_page.title}: {e}"))
            
            # Copy PageYouTubeVideo data
            video_count = 0
            for old_video in OldPageYouTubeVideo.objects.all():
                if old_video.page_id in page_mapping:
                    try:
                        new_video, created = NewPageYouTubeVideo.objects.get_or_create(
                            page=page_mapping[old_video.page_id],
                            youtube_id=old_video.youtube_id,
                            defaults={
                                'title': old_video.title,
                                'description': old_video.description,
                                'order': old_video.order,
                                'created_at': old_video.created_at,
                            }
                        )
                        if created:
                            video_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating YouTube video {old_video.title}: {e}"))
            
            # Copy PageURL data
            url_count = 0
            for old_url in OldPageURL.objects.all():
                if old_url.page_id in page_mapping:
                    try:
                        new_url, created = NewPageURL.objects.get_or_create(
                            page=page_mapping[old_url.page_id],
                            url=old_url.url,
                            defaults={
                                'title': old_url.title,
                                'description': old_url.description,
                                'open_in_new_tab': old_url.open_in_new_tab,
                                'order': old_url.order,
                                'created_at': old_url.created_at,
                            }
                        )
                        if created:
                            url_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating URL {old_url.title}: {e}"))
            
            # Copy PageVideoFile data
            video_file_count = 0
            for old_video_file in OldPageVideoFile.objects.all():
                if old_video_file.page_id in page_mapping:
                    try:
                        new_video_file, created = NewPageVideoFile.objects.get_or_create(
                            page=page_mapping[old_video_file.page_id],
                            video_file=old_video_file.video_file,
                            defaults={
                                'title': old_video_file.title,
                                'description': old_video_file.description,
                                'order': old_video_file.order,
                                'created_at': old_video_file.created_at,
                            }
                        )
                        if created:
                            video_file_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating video file {old_video_file.title}: {e}"))
            
            # Copy PageAudioFile data
            audio_file_count = 0
            for old_audio_file in OldPageAudioFile.objects.all():
                if old_audio_file.page_id in page_mapping:
                    try:
                        new_audio_file, created = NewPageAudioFile.objects.get_or_create(
                            page=page_mapping[old_audio_file.page_id],
                            audio_file=old_audio_file.audio_file,
                            defaults={
                                'title': old_audio_file.title,
                                'description': old_audio_file.description,
                                'order': old_audio_file.order,
                                'created_at': old_audio_file.created_at,
                            }
                        )
                        if created:
                            audio_file_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating audio file {old_audio_file.title}: {e}"))
            
            # Update Quiz references
            from app_study.models import Quiz
            quiz_update_count = 0
            for quiz in Quiz.objects.filter(page__isnull=False):
                old_page_id = quiz.page_id
                if old_page_id in page_mapping:
                    quiz.page = page_mapping[old_page_id]
                    quiz.save()
                    quiz_update_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully migrated:\n"
                    f"- {page_count} pages\n"
                    f"- {video_count} YouTube videos\n"
                    f"- {url_count} URLs\n"
                    f"- {video_file_count} video files\n"
                    f"- {audio_file_count} audio files\n"
                    f"- Updated {quiz_update_count} quiz references"
                )
            ) 