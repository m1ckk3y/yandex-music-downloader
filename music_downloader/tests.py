from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserProfile, Playlist, Track, DownloadedPlaylist, DownloadedTrack
import json


class UserProfileModelTest(TestCase):
    """Tests for UserProfile model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
    
    def test_user_profile_creation(self):
        """Test that UserProfile is created with user"""
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.yandex_token, '')
    
    def test_user_profile_with_token(self):
        """Test UserProfile with Yandex token"""
        profile = UserProfile.objects.create(
            user=self.user,
            yandex_token='test_token_123'
        )
        self.assertEqual(profile.yandex_token, 'test_token_123')


class PlaylistModelTest(TestCase):
    """Tests for Playlist model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.playlist = Playlist.objects.create(
            user=self.user,
            yandex_playlist_id='12345',
            owner='testowner',
            title='Test Playlist',
            track_count=10
        )
    
    def test_playlist_creation(self):
        """Test playlist creation"""
        self.assertEqual(self.playlist.title, 'Test Playlist')
        self.assertEqual(self.playlist.track_count, 10)
        self.assertEqual(self.playlist.yandex_playlist_id, '12345')
    
    def test_playlist_str(self):
        """Test playlist string representation"""
        self.assertEqual(str(self.playlist), 'Test Playlist (10 треков)')
    
    def test_get_downloaded_count_zero(self):
        """Test get_downloaded_count returns 0 when no tracks downloaded"""
        self.assertEqual(self.playlist.get_downloaded_count(), 0)


class TrackModelTest(TestCase):
    """Tests for Track model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.playlist = Playlist.objects.create(
            user=self.user,
            yandex_playlist_id='12345',
            owner='testowner',
            title='Test Playlist',
            track_count=1
        )
        self.track = Track.objects.create(
            playlist=self.playlist,
            yandex_track_id='67890',
            title='Test Track',
            artist='Test Artist',
            duration=180,
            position=0
        )
    
    def test_track_creation(self):
        """Test track creation"""
        self.assertEqual(self.track.title, 'Test Track')
        self.assertEqual(self.track.artist, 'Test Artist')
        self.assertEqual(self.track.duration, 180)
    
    def test_track_ordering(self):
        """Test tracks are ordered by position"""
        track2 = Track.objects.create(
            playlist=self.playlist,
            yandex_track_id='67891',
            title='Test Track 2',
            artist='Test Artist',
            duration=200,
            position=1
        )
        tracks = Track.objects.filter(playlist=self.playlist)
        self.assertEqual(tracks[0], self.track)
        self.assertEqual(tracks[1], track2)


class AuthenticationViewTest(TestCase):
    """Tests for authentication views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_login_view_get(self):
        """Test login view loads correctly"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/login.html')
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_login_failure(self):
        """Test failed login with wrong password"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_register_view_get(self):
        """Test register view loads correctly"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/register.html')


class HomeViewTest(TestCase):
    """Tests for home view"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_home_view_requires_login(self):
        """Test home view redirects to login if not authenticated"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_home_view_authenticated(self):
        """Test home view loads for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/home.html')
    
    def test_home_view_creates_profile(self):
        """Test home view creates UserProfile if it doesn't exist"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('home'))
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())


class ProfileViewTest(TestCase):
    """Tests for profile view"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_profile_view_get(self):
        """Test profile view loads correctly"""
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/profile.html')
    
    def test_profile_update(self):
        """Test profile update with token"""
        response = self.client.post(reverse('profile'), {
            'yandex_token': 'new_test_token_123'
        })
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.yandex_token, 'new_test_token_123')


class PlaylistViewTest(TestCase):
    """Tests for playlist views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.playlist = Playlist.objects.create(
            user=self.user,
            yandex_playlist_id='12345',
            owner='testowner',
            title='Test Playlist',
            track_count=3
        )
        # Create 3 tracks to test pagination
        for i in range(3):
            Track.objects.create(
                playlist=self.playlist,
                yandex_track_id=f'6789{i}',
                title=f'Test Track {i+1}',
                artist='Test Artist',
                duration=180 + i*10,
                position=i
            )
    
    def test_playlist_preview_view(self):
        """Test playlist preview view loads correctly"""
        response = self.client.get(
            reverse('playlist_preview', kwargs={'playlist_id': self.playlist.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/playlist_preview.html')
        self.assertContains(response, 'Test Playlist')
    
    def test_playlist_preview_pagination(self):
        """Test playlist preview with per_page parameter"""
        # Test that per_page parameter is accepted
        response = self.client.get(
            reverse('playlist_preview', kwargs={'playlist_id': self.playlist.id}),
            {'per_page': 25}
        )
        self.assertEqual(response.status_code, 200)
        # Verify context has pagination objects
        self.assertIn('page_obj', response.context)
        self.assertIn('per_page', response.context)
        self.assertEqual(response.context['per_page'], 25)


class DownloadedPlaylistTest(TestCase):
    """Tests for downloaded playlist functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.playlist = Playlist.objects.create(
            user=self.user,
            yandex_playlist_id='12345',
            owner='testowner',
            title='Test Playlist',
            track_count=1
        )
        self.downloaded_playlist = DownloadedPlaylist.objects.create(
            user=self.user,
            playlist=self.playlist,
            title='Test Downloaded Playlist',
            tracks_count=1
        )
    
    def test_downloaded_playlists_view(self):
        """Test downloaded playlists list view"""
        response = self.client.get(reverse('downloaded_playlists'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/downloaded_playlists.html')
        self.assertContains(response, 'Test Downloaded Playlist')
    
    def test_downloaded_playlist_detail_view(self):
        """Test downloaded playlist detail view"""
        response = self.client.get(
            reverse('downloaded_playlist_detail', 
                   kwargs={'playlist_id': self.downloaded_playlist.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'music_downloader/downloaded_playlist_detail.html')
