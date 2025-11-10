from django.contrib import admin
from .models import UserProfile, Playlist, Track, DownloadedPlaylist, DownloadedTrack


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'track_count', 'owner', 'created_at']
    list_filter = ['created_at', 'preview_loaded']
    search_fields = ['title', 'user__username', 'owner']


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'playlist', 'position']
    list_filter = ['playlist']
    search_fields = ['title', 'artist']


@admin.register(DownloadedPlaylist)
class DownloadedPlaylistAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'tracks_count', 'download_date']
    list_filter = ['download_date']
    search_fields = ['title', 'user__username']


@admin.register(DownloadedTrack)
class DownloadedTrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'downloaded_playlist', 'format', 'bitrate']
    list_filter = ['format', 'downloaded_playlist']
    search_fields = ['title', 'artist']
