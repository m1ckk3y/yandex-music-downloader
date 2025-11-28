from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('playlist-loading/', views.playlist_loading_view, name='playlist_loading'),
    path('api/playlist-load/', views.playlist_load_api, name='playlist_load_api'),
    path('api/playlist-progress/', views.playlist_progress_api, name='playlist_progress_api'),
    path('playlist/<int:playlist_id>/preview/', views.playlist_preview_view, name='playlist_preview'),
    path('playlist/<int:playlist_id>/download/', views.download_tracks_view, name='download_tracks'),
    path('download/progress/', views.download_progress_view, name='download_progress'),
    path('api/download-start/', views.download_start_api, name='download_start_api'),
    path('api/download-progress/', views.download_progress_api, name='download_progress_api'),
    path('downloaded/', views.downloaded_playlists_view, name='downloaded_playlists'),
    path('downloaded/<int:playlist_id>/', views.downloaded_playlist_detail_view, name='downloaded_playlist_detail'),
    path('downloaded/<int:playlist_id>/delete/', views.delete_downloaded_playlist_view, name='delete_downloaded_playlist'),
    path('downloaded/<int:playlist_id>/download-zip/', views.download_zip_view, name='download_zip'),
    path('downloaded/<int:playlist_id>/delete-selected/', views.delete_selected_tracks_view, name='delete_selected_tracks'),
    path('downloaded/track/<int:track_id>/delete/', views.delete_downloaded_track_view, name='delete_downloaded_track'),
    path('download-file/<int:track_id>/', views.download_file_view, name='download_file'),
]
