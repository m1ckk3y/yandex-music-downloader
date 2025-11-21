from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Профиль пользователя с токеном Yandex Music"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    yandex_token = models.CharField(max_length=500, blank=True, help_text='OAuth токен Yandex Music')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'


class Playlist(models.Model):
    """Информация о плейлисте Yandex Music"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists')
    yandex_playlist_id = models.CharField(max_length=100)
    owner = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    track_count = models.IntegerField(default=0)
    preview_loaded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.track_count} треков)"
    
    def get_downloaded_count(self):
        """Получить количество скачанных треков для этого плейлиста"""
        downloaded_playlist = self.downloadedplaylist_set.first()
        if downloaded_playlist:
            return downloaded_playlist.tracks.count()
        return 0
    
    def get_downloaded_playlist(self):
        """Получить скачанный плейлист, если существует"""
        return self.downloadedplaylist_set.first()
    
    class Meta:
        verbose_name = 'Плейлист'
        verbose_name_plural = 'Плейлисты'
        unique_together = ['user', 'yandex_playlist_id', 'owner']


class Track(models.Model):
    """Информация о треке"""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='tracks')
    yandex_track_id = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    artist = models.CharField(max_length=500)
    duration = models.IntegerField(null=True, blank=True, help_text='Длительность в секундах')
    position = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.artist} - {self.title}"
    
    class Meta:
        verbose_name = 'Трек'
        verbose_name_plural = 'Треки'
        ordering = ['position']


class DownloadedPlaylist(models.Model):
    """Скачанный плейлист"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='downloaded_playlists')
    playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=500)
    download_date = models.DateTimeField(auto_now_add=True)
    tracks_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.title} (скачан {self.download_date.strftime('%d.%m.%Y')})"
    
    class Meta:
        verbose_name = 'Скачанный плейлист'
        verbose_name_plural = 'Скачанные плейлисты'
        ordering = ['-download_date']


class DownloadedTrack(models.Model):
    """Скачанный трек"""
    downloaded_playlist = models.ForeignKey(DownloadedPlaylist, on_delete=models.CASCADE, related_name='tracks')
    title = models.CharField(max_length=500)
    artist = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000)
    file_size = models.BigIntegerField(default=0, help_text='Размер файла в байтах')
    format = models.CharField(max_length=10, default='mp3')
    bitrate = models.IntegerField(null=True, blank=True, help_text='Битрейт в kbps')
    
    def __str__(self):
        return f"{self.artist} - {self.title}"
    
    def get_file_size_mb(self):
        """Размер файла в МБ"""
        return round(self.file_size / (1024 * 1024), 2)
    
    class Meta:
        verbose_name = 'Скачанный трек'
        verbose_name_plural = 'Скачанные треки'
