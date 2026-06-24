from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from app_conf.models import KnowledgeBaseArticle


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""
    priority = 0.8
    changefreq = 'monthly'
    protocol = 'https'
    
    def items(self):
        return [
            'app_conf:about',  # About page - high priority public page
            'app_conf:faq',    # FAQ page - high priority public page
            'app_conf:partnership',  # Partnership page - high priority public page
            'app_conf:contact',  # Contact page - high priority public page
            'privacy_policy',
            'cookie_policy',
            'terms_of_service',
        ]
    
    def location(self, item):
        try:
            return reverse(item)
        except:
            return '/'
    
    def lastmod(self, obj):
        return timezone.now()


class DocumentationSitemap(Sitemap):
    """Sitemap for documentation pages"""
    priority = 0.6
    changefreq = 'weekly'
    protocol = 'https'
    
    def items(self):
        # Add your documentation URLs here
        return [
            'docs-home',
            'user-guide',
            'api-docs',
            'security-guide',
        ]
    
    def location(self, item):
        return f'/docs/{item.replace("-", "/")}/'
    
    def lastmod(self, obj):
        return timezone.now()


class PublicContentSitemap(Sitemap):
    """Sitemap for public content that doesn't require authentication"""
    priority = 0.7
    changefreq = 'weekly'
    protocol = 'https'
    
    def items(self):
        # Add URLs for public content like blog posts, articles, etc.
        return []
    
    def location(self, item):
        return f'/content/{item}/'
    
    def lastmod(self, obj):
        return timezone.now()


class KnowledgeBaseSitemap(Sitemap):
    """Sitemap for Knowledge Base articles"""
    priority = 0.7
    changefreq = 'weekly'
    protocol = 'https'
    
    def items(self):
        return KnowledgeBaseArticle.objects.filter(is_published=True)
    
    def location(self, item):
        return f'/about/knowledge-base/{item.slug}/'
    
    def lastmod(self, obj):
        return obj.updated_at


# Main sitemap dictionary
sitemaps = {
    'static': StaticViewSitemap,
    'documentation': DocumentationSitemap,
    'content': PublicContentSitemap,
    'knowledge_base': KnowledgeBaseSitemap,
} 