"""
Сервис для работы с Yandex Music API в Django
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from yandex_music import Client
from yandex_music.exceptions import YandexMusicError, NetworkError, UnauthorizedError
from django.conf import settings
from .models import Playlist, Track, DownloadedPlaylist, DownloadedTrack


def _chunked(iterable, size):
    """Разбить последовательность на чанки фиксированного размера"""
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]


class YandexMusicService:
    """Сервис для работы с Yandex Music API"""
    
    def __init__(self, token: Optional[str] = None, user_id: Optional[int] = None, session=None):
        self.token = token
        self.user_id = user_id
        self.client = None
        self.session = session  # Django session для обновления прогресса
    
    def update_progress(self, current, total, message=''):
        """Обновить прогресс в сессии"""
        if self.session is not None:
            self.session['loading_progress'] = {
                'status': 'loading',
                'current': current,
                'total': total,
                'message': message
            }
            self.session.save()
    
    def authenticate(self) -> Tuple[bool, str]:
        """
        Аутентификация в Yandex Music
        
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            if not self.token:
                return False, "Токен не предоставлен"
            
            self.client = Client(self.token).init()
            account_info = self.client.account_status()
            
            if account_info:
                return True, f"Успешная авторизация как {account_info.account.display_name}"
            else:
                return False, "Не удалось получить информацию об аккаунте"
        
        except UnauthorizedError:
            return False, "Неверный токен"
        except NetworkError:
            return False, "Ошибка сети"
        except Exception as e:
            return False, f"Ошибка аутентификации: {str(e)}"
    
    def extract_playlist_id(self, url_or_id: str) -> Optional[Tuple[str, str]]:
        """
        Извлечь ID плейлиста из URL
        
        Returns:
            Tuple[owner, playlist_id] или None
        """
        import re
        url_pattern = r'https?://music\.yandex\.[a-z]+/users/([^/]+)/playlists/(\d+)'
        match = re.search(url_pattern, url_or_id)
        
        if match:
            return match.group(1), match.group(2)
        
        if ':' in url_or_id:
            parts = url_or_id.split(':')
            if len(parts) == 2:
                return parts[0], parts[1]
        
        return None
    
    def get_playlist_info(self, playlist_identifier: str) -> Optional[Dict]:
        """
        Получить информацию о плейлисте
        
        Returns:
            Dict с данными плейлиста или None
        """
        if not self.client:
            success, _ = self.authenticate()
            if not success:
                return None
        
        try:
            # Обработка "liked" плейлиста
            if playlist_identifier.lower() in ['liked', 'favorites', 'my']:
                print("Loading 'liked' playlist...")
                liked_tracks = self.client.users_likes_tracks()
                if liked_tracks and hasattr(liked_tracks, 'tracks_ids'):
                    tracks_data = []
                    # tracks_ids содержит объекты TrackId, у которых есть атрибут id
                    ids = []
                    for ti in liked_tracks.tracks_ids:
                        track_id = getattr(ti, 'id', None) or str(ti)
                        if track_id:
                            ids.append(track_id)
                    total_tracks = len(ids)
                    print(f"Found {total_tracks} liked tracks, loading in batches...")
                    
                    processed = 0
                    self.update_progress(0, total_tracks, 'Загрузка треков...')
                    
                    for batch_num, batch in enumerate(_chunked(ids, 100)):
                        try:
                            # Загружаем батч
                            batch_tracks = self.client.tracks(batch)
                            
                            # Обрабатываем каждый трек
                            for i, t in enumerate(batch_tracks):
                                if not t:
                                    continue
                                try:
                                    # Безопасное извлечение исполнителей
                                    artists = getattr(t, 'artists', [])
                                    if artists:
                                        try:
                                            artist = ', '.join([getattr(a, 'name', 'Unknown') for a in artists])
                                        except:
                                            artist = 'Unknown'
                                    else:
                                        artist = 'Unknown'
                                    
                                    duration_sec = (getattr(t, 'duration_ms', 0) or 0) // 1000
                                    track_id = str(getattr(t, 'id', '')) or str(getattr(t, 'track_id', ''))
                                    
                                    if not track_id:
                                        print(f"Skipping track without ID at batch {batch_num}, position {i}")
                                        continue
                                    
                                    tracks_data.append({
                                        'id': track_id,
                                        'title': getattr(t, 'title', 'Без названия') or 'Без названия',
                                        'artist': artist,
                                        'duration': duration_sec,
                                        'position': processed
                                    })
                                    processed += 1
                                except Exception as e:
                                    print(f"Error processing track in batch {batch_num}, pos {i}: {e}")
                                    continue
                            
                            print(f"Loaded {min(processed, total_tracks)}/{total_tracks} tracks...")
                            self.update_progress(processed, total_tracks, f'Загружено {processed} из {total_tracks} треков')
                            
                        except Exception as e:
                            # Если батч полностью не загрузился, пробуем по одному
                            print(f"Error fetching batch {batch_num}: {e}. Trying individual tracks...")
                            for track_id in batch:
                                try:
                                    track_list = self.client.tracks([track_id])
                                    if track_list and len(track_list) > 0:
                                        t = track_list[0]
                                        if not t:
                                            continue
                                        
                                        artists = getattr(t, 'artists', [])
                                        if artists:
                                            try:
                                                artist = ', '.join([getattr(a, 'name', 'Unknown') for a in artists])
                                            except:
                                                artist = 'Unknown'
                                        else:
                                            artist = 'Unknown'
                                        
                                        duration_sec = (getattr(t, 'duration_ms', 0) or 0) // 1000
                                        
                                        tracks_data.append({
                                            'id': str(track_id),
                                            'title': getattr(t, 'title', 'Без названия') or 'Без названия',
                                            'artist': artist,
                                            'duration': duration_sec,
                                            'position': processed
                                        })
                                        processed += 1
                                except Exception as track_error:
                                    print(f"Failed to load individual track: {track_error}")
                                    continue
                            
                            print(f"After individual retry: {processed}/{total_tracks} tracks loaded")
                            self.update_progress(processed, total_tracks, f'Загружено {processed} из {total_tracks} треков')
                    
                    print(f"Successfully loaded {len(tracks_data)} tracks")
                    return {
                        'owner': 'me',
                        'playlist_id': 'liked',
                        'title': 'Мне нравится',
                        'track_count': total_tracks,
                        'tracks': tracks_data
                    }
            
            # Обычный плейлист
            playlist_info = self.extract_playlist_id(playlist_identifier)
            if not playlist_info:
                return None
            
            owner, playlist_id = playlist_info
            playlist = self.client.users_playlists(playlist_id, owner)
            
            if not playlist:
                return None
            
            tracks_data = []
            if hasattr(playlist, 'tracks') and playlist.tracks:
                total_tracks = len(playlist.tracks)
                print(f"Loading {total_tracks} tracks from playlist...")
                
                # Сначала берем те, где уже есть объект track
                missing_ids = []
                for i, track_short in enumerate(playlist.tracks):
                    try:
                        t = getattr(track_short, 'track', None)
                        if t:
                            artist = ', '.join([a.name for a in getattr(t, 'artists', [])]) if getattr(t, 'artists', None) else 'Unknown'
                            duration_sec = (getattr(t, 'duration_ms', 0) or 0) // 1000
                            tracks_data.append({
                                'id': str(getattr(t, 'id', '')),
                                'title': getattr(t, 'title', 'Без названия') or 'Без названия',
                                'artist': artist,
                                'duration': duration_sec,
                                'position': i
                            })
                        else:
                            # Собираем id для последующей пакетной загрузки
                            tid = getattr(track_short, 'track_id', None) or getattr(track_short, 'id', None)
                            if tid:
                                missing_ids.append((i, tid))
                    except Exception as e:
                        print(f"Error processing short track {i}: {e}")
                        continue
                
                # Догружаем отсутствующие треки батчами
                if missing_ids:
                    print(f"Fetching details for {len(missing_ids)} tracks in batches...")
                    for batch in _chunked(missing_ids, 100):
                        idxs = [b[0] for b in batch]
                        ids = [b[1] for b in batch]
                        try:
                            batch_tracks = self.client.tracks(ids)
                        except Exception as e:
                            print(f"Error fetching playlist batch: {e}")
                            batch_tracks = []
                        for j, t in enumerate(batch_tracks):
                            pos = idxs[j] if j < len(idxs) else 0
                            if not t:
                                continue
                            try:
                                artist = ', '.join([a.name for a in getattr(t, 'artists', [])]) if getattr(t, 'artists', None) else 'Unknown'
                                duration_sec = (getattr(t, 'duration_ms', 0) or 0) // 1000
                                tracks_data.append({
                                    'id': str(getattr(t, 'id', '')),
                                    'title': getattr(t, 'title', 'Без названия') or 'Без названия',
                                    'artist': artist,
                                    'duration': duration_sec,
                                    'position': pos
                                })
                            except Exception as e:
                                print(f"Error processing fetched track at pos {pos}: {e}")
                                continue
                
                # Сортируем по позиции
                tracks_data.sort(key=lambda x: x['position'])
                print(f"Successfully loaded {len(tracks_data)} tracks")
            
            return {
                'owner': owner,
                'playlist_id': playlist_id,
                'title': playlist.title,
                'track_count': len(playlist.tracks) if playlist.tracks else 0,
                'tracks': tracks_data
            }
        
        except Exception as e:
            print(f"Error getting playlist info: {e}")
            return None
    
    def save_playlist_preview(self, playlist_data: Dict) -> Optional[Playlist]:
        """Сохранить предпросмотр плейлиста в БД"""
        if not self.user_id:
            return None
        
        from django.contrib.auth.models import User
        user = User.objects.get(id=self.user_id)
        
        # Создаем или обновляем плейлист
        playlist, created = Playlist.objects.get_or_create(
            user=user,
            yandex_playlist_id=playlist_data['playlist_id'],
            owner=playlist_data['owner'],
            defaults={
                'title': playlist_data['title'],
                'track_count': playlist_data['track_count'],
                'preview_loaded': True
            }
        )
        
        if not created:
            playlist.title = playlist_data['title']
            playlist.track_count = playlist_data['track_count']
            playlist.preview_loaded = True
            playlist.save()
        
        # Удаляем старые треки и добавляем новые
        playlist.tracks.all().delete()
        
        print(f"Saving {len(playlist_data['tracks'])} tracks to database...")
        for track_data in playlist_data['tracks']:
            try:
                Track.objects.create(
                    playlist=playlist,
                    yandex_track_id=track_data['id'],
                    title=track_data['title'],
                    artist=track_data['artist'],
                    duration=track_data.get('duration'),
                    position=track_data['position']
                )
            except Exception as e:
                print(f"Error saving track {track_data['title']}: {e}")
        
        saved_count = playlist.tracks.count()
        print(f"Successfully saved {saved_count} tracks to database")
        
        return playlist
    
    def download_tracks(self, playlist_id: int, track_ids: List[str]) -> Tuple[bool, str, Optional[DownloadedPlaylist]]:
        """
        Скачать выбранные треки
        
        Args:
            playlist_id: ID плейлиста в БД
            track_ids: Список ID треков для скачивания
        
        Returns:
            Tuple[bool, str, DownloadedPlaylist]: (успех, сообщение, скачанный плейлист)
        """
        if not self.client:
            success, msg = self.authenticate()
            if not success:
                return False, msg, None
        
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=self.user_id)
            playlist = Playlist.objects.get(id=playlist_id, user=user)
            
            # Создаем директорию для скачивания
            media_root = Path(settings.MEDIA_ROOT)
            user_dir = media_root / f"user_{self.user_id}"
            playlist_dir = user_dir / f"playlist_{playlist.id}_{playlist.yandex_playlist_id}"
            playlist_dir.mkdir(parents=True, exist_ok=True)
            
            # Создаем запись о скачанном плейлисте
            downloaded_playlist = DownloadedPlaylist.objects.create(
                user=user,
                playlist=playlist,
                title=playlist.title,
                tracks_count=0
            )
            
            successful = 0
            failed = 0
            
            # Получаем треки для скачивания
            tracks_to_download = Track.objects.filter(
                playlist=playlist,
                yandex_track_id__in=track_ids
            )
            
            total = tracks_to_download.count()
            self.update_progress(0, total, 'Начало скачивания...')
            
            for idx, track in enumerate(tracks_to_download, 1):
                try:
                    self.update_progress(idx-1, total, f'Скачивание трека {idx} из {total}: {track.artist} - {track.title}')
                    
                    # Получаем информацию о треке
                    yandex_track = self.client.tracks([track.yandex_track_id])[0]
                    
                    # Получаем ссылку на скачивание
                    download_infos = self.client.tracks_download_info(track.yandex_track_id)
                    if not download_infos:
                        failed += 1
                        continue
                    
                    # Выбираем лучшее качество
                    best_info = max(download_infos, key=lambda x: x.bitrate_in_kbps or 0)
                    download_url = best_info.get_direct_link()
                    
                    if not download_url:
                        failed += 1
                        continue
                    
                    # Формируем имя файла
                    safe_filename = self._sanitize_filename(f"{track.artist} - {track.title}")
                    file_extension = best_info.codec if best_info.codec in ['mp3', 'flac', 'aac'] else 'mp3'
                    filename = f"{safe_filename}.{file_extension}"
                    filepath = playlist_dir / filename
                    
                    # Скачиваем файл
                    import requests
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Получаем размер файла
                    file_size = filepath.stat().st_size
                    
                    # Сохраняем информацию о скачанном треке
                    relative_path = str(filepath.relative_to(media_root))
                    DownloadedTrack.objects.create(
                        downloaded_playlist=downloaded_playlist,
                        title=track.title,
                        artist=track.artist,
                        file_path=relative_path,
                        file_size=file_size,
                        format=file_extension,
                        bitrate=best_info.bitrate_in_kbps
                    )
                    
                    successful += 1
                    self.update_progress(idx, total, f'Скачано {successful} из {total} треков')
                
                except Exception as e:
                    print(f"Error downloading track {track.title}: {e}")
                    failed += 1
                    self.update_progress(idx, total, f'Ошибка при скачивании: {track.title}')
                    continue
            
            # Обновляем количество треков
            downloaded_playlist.tracks_count = successful
            downloaded_playlist.save()
            
            if successful > 0:
                return True, f"Успешно скачано {successful} треков (ошибок: {failed})", downloaded_playlist
            else:
                return False, f"Не удалось скачать треки (ошибок: {failed})", None
        
        except Exception as e:
            return False, f"Ошибка при скачивании: {str(e)}", None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Очистить имя файла от недопустимых символов"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:200]
