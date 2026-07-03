from django.contrib import admin

from .models import CouncilPage, CouncilPost, ScrapeRun


@admin.register(CouncilPage)
class CouncilPageAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'province', 'is_active', 'updated_at')
    list_filter = ('province', 'is_active')
    search_fields = ('name', 'district', 'province', 'facebook_url')


@admin.register(CouncilPost)
class CouncilPostAdmin(admin.ModelAdmin):
    list_display = ('council_page', 'category', 'date_posted', 'detected_deadline', 'date_scraped')
    list_filter = ('category', 'council_page__province', 'council_page')
    search_fields = ('post_text', 'post_url', 'matched_keywords', 'council_page__name')
    readonly_fields = ('date_scraped', 'created_at', 'updated_at')


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'finished_at', 'status', 'pages_checked', 'posts_found', 'posts_created', 'posts_updated')
    list_filter = ('status',)
    search_fields = ('message',)
    readonly_fields = ('started_at', 'finished_at', 'status', 'pages_checked', 'posts_found', 'posts_created', 'posts_updated', 'message')
