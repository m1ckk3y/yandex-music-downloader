"""
Сервис для работы с Yandex Music API в Django
"""
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from django.conf import settings
from .models import Playlist, Track, DownloadedPlaylist, DownloadedTrack

# Add project root to path to import core module
sys.path.insert(0, str(Path(__file__).parent.parent))
from core import YandexMusicCore


class YandexMusicService(YandexMusicCore):
    """Сервис для работы с Yandex Music API в Django"""
    
    def __init__(self, token: Optional[str] = None, user_id: Optional[int] = None, session=None, preferred_format: str = "mp3"):
        super().__init__(token=token, preferred_format=preferred_format)
        self.user_id = user_id
        self.django_session = session  # Django session для обновления прогресса
    
    def update_progress(self, current, total, message=''):
        """Обновить прогресс в сессии"""
        if self.django_session is not None:
            self.django_session['loading_progress'] = {
                'status': 'loading',
                'current': current,
                'total': total,
                'message': message
            }
            self.django_session.save()
    
    # authenticate() and extract_playlist_id() inherited from YandexMusicCore
    
    def get_playlist_info(self, playlist_identifier: str) -> Optional[Dict]:
        """
        Получить информацию о плейлисте
        
        Returns:
            Dict с данными плейлиста или None
        """
        print(f"[SERVICE DEBUG] get_playlist_info called with: {playlist_identifier}")
        print(f"[SERVICE DEBUG] Client exists: {self.client is not None}")
        if not self.client:
            print("[SERVICE DEBUG] Authenticating...")
            success, msg = self.authenticate()
            print(f"[SERVICE DEBUG] Authentication result: success={success}, msg={msg}")
            if not success:
                print(f"[SERVICE DEBUG] Authentication failed: {msg}")
                # Сохраняем сообщение об ошибке для передачи на фронтенд
                self.last_error = msg
                return None
        
        try:
            # Обработка "liked" плейлиста
            if playlist_identifier.lower() in ['liked', 'favorites', 'my']:
                print("[SERVICE DEBUG] Loading 'liked' playlist...")
                print(f"[SERVICE DEBUG] Client type: {type(self.client)}")
                try:
                    liked_tracks = self.client.users_likes_tracks()
                    print(f"[SERVICE DEBUG] Liked tracks result: {liked_tracks is not None}")
                except Exception as e:
                    print(f"[SERVICE DEBUG] Error calling users_likes_tracks: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
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
                    
                    from core.yandex_music_core import chunked
                    for batch_num, batch in enumerate(chunked(ids, 100)):
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

            # Обработка UUID-плейлистов (новый формат публичных ссылок)
            if owner == '__uuid_playlist__':
                try:
                    playlist = self.resolve_uuid_playlist(playlist_id)
                    if not playlist:
                        print(f"Could not find UUID playlist {playlist_id}")
                        return None

                    # Извлекаем фактического владельца, если он есть
                    if hasattr(playlist, 'owner') and playlist.owner:
                        owner = str(playlist.owner.uid) if hasattr(playlist.owner, 'uid') else 'unknown'
                    else:
                        owner = 'unknown'
                    print(f"Found UUID playlist with owner: {owner}")
                except Exception as e:
                    print(f"Error loading UUID playlist {playlist_id}: {e}")
                    return None
            else:
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
                    from core.yandex_music_core import chunked
                    for batch in chunked(missing_ids, 100):
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
            
            # Получаем или создаем запись о скачанном плейлисте
            downloaded_playlist, created = DownloadedPlaylist.objects.get_or_create(
                user=user,
                playlist=playlist,
                defaults={
                    'title': playlist.title,
                    'tracks_count': 0
                }
            )
            
            if not created:
                # Обновляем дату последнего скачивания
                from django.utils import timezone
                downloaded_playlist.download_date = timezone.now()
                downloaded_playlist.save()
            
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
            
            # Обновляем количество треков (подсчитываем реальное количество треков)
            downloaded_playlist.tracks_count = downloaded_playlist.tracks.count()
            downloaded_playlist.save()
            
            # Финальное обновление прогресса до 100%
            if successful > 0:
                self.update_progress(total, total, f'Скачивание завершено! Успешно скачано {successful} треков')
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
