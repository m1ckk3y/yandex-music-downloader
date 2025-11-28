from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from pathlib import Path
from .forms import RegistrationForm, ProfileUpdateForm, PlaylistLoadForm
from .models import UserProfile, Playlist, Track, DownloadedPlaylist, DownloadedTrack
from .services import YandexMusicService


def register_view(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешна! Добро пожаловать!')
            return redirect('home')
    else:
        form = RegistrationForm()
    
    return render(request, 'music_downloader/register.html', {'form': form})


def login_view(request):
    """Вход в систему"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    
    return render(request, 'music_downloader/login.html')


@login_required
def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def home_view(request):
    """Главная страница с формой загрузки плейлиста"""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    # Обработка формы загрузки плейлиста
    if request.method == 'POST':
        form = PlaylistLoadForm(request.POST)
        if form.is_valid():
            playlist_url = form.cleaned_data['playlist_url']
            
            if not profile.yandex_token:
                messages.error(request, 'Необходимо добавить токен Yandex Music в профиле')
                return redirect('profile')
            
            # Сохраняем URL в сессии для асинхронной загрузки
            request.session['playlist_url'] = playlist_url
            request.session['loading_progress'] = {'status': 'pending', 'current': 0, 'total': 0}
            
            return redirect('playlist_loading')
    else:
        form = PlaylistLoadForm()
    
    playlists = Playlist.objects.filter(user=request.user).order_by('-created_at')
    
    # Добавляем информацию о скачанных треках для каждого плейлиста
    playlists_with_downloads = []
    for playlist in playlists:
        playlist.downloaded_count = playlist.get_downloaded_count()
        playlist.downloaded_playlist_obj = playlist.get_downloaded_playlist()
        playlists_with_downloads.append(playlist)
    
    context = {
        'profile': profile,
        'playlists': playlists_with_downloads,
        'has_token': bool(profile.yandex_token),
        'form': form
    }
    
    return render(request, 'music_downloader/home.html', context)


@login_required
def profile_view(request):
    """Профиль пользователя"""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=profile)
    
    return render(request, 'music_downloader/profile.html', {'form': form, 'profile': profile})


@login_required
def playlist_loading_view(request):
    """Страница с прогресс-баром"""
    playlist_url = request.session.get('playlist_url')
    if not playlist_url:
        messages.error(request, 'Не указан URL плейлиста')
        return redirect('home')
    
    return render(request, 'music_downloader/playlist_loading.html', {'playlist_url': playlist_url})


@login_required  
def playlist_load_api(request):
    """
АPI для асинхронной загрузки плейлиста"""
    import json
    import traceback
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    playlist_url = request.session.get('playlist_url')
    print(f"[DEBUG] Playlist URL from session: {playlist_url}")
    if not playlist_url:
        print("[ERROR] No playlist URL in session")
        return JsonResponse({'error': 'Не указан URL плейлиста'}, status=400)
    
    try:
        profile = request.user.profile
        print(f"[DEBUG] Profile found for user {request.user.username}")
    except UserProfile.DoesNotExist:
        print(f"[ERROR] Profile not found for user {request.user.username}")
        return JsonResponse({'error': 'Профиль не найден'}, status=400)
    
    if not profile.yandex_token:
        print("[ERROR] No Yandex token in profile")
        return JsonResponse({'error': 'Не указан токен'}, status=400)
    
    print(f"[DEBUG] Token exists, length: {len(profile.yandex_token)}")
    
    try:
        # Создаем сервис с передачей сессии для прогресса
        print("[DEBUG] Creating YandexMusicService...")
        service = YandexMusicService(token=profile.yandex_token, user_id=request.user.id, session=request.session)
        
        # Обновляем прогресс
        request.session['loading_progress'] = {'status': 'loading', 'current': 0, 'total': 0, 'message': 'Загрузка информации о плейлисте...'}
        request.session.save()
        
        # Загружаем плейлист
        print(f"[DEBUG] Calling get_playlist_info with: {playlist_url}")
        playlist_data = service.get_playlist_info(playlist_url)
        print(f"[DEBUG] get_playlist_info returned: {bool(playlist_data)}")
        
        if not playlist_data:
            print("[ERROR] get_playlist_info returned None")
            # Получаем конкретное сообщение об ошибке из сервиса
            error_message = getattr(service, 'last_error', None)
            if error_message:
                if 'Invalid token' in error_message or 'Неверный токен' in error_message:
                    error_message = 'Неверный или устаревший API-ключ Yandex Music. Пожалуйста, обновите токен в профиле'
            else:
                error_message = 'Не удалось загрузить плейлист. Проверьте URL или доступ к плейлисту'
            
            request.session['loading_progress'] = {'status': 'error', 'message': error_message}
            request.session.save()
            return JsonResponse({'error': error_message}, status=400)
        
        tracks_count = len(playlist_data.get('tracks', []))
        
        # Обновляем прогресс
        request.session['loading_progress'] = {
            'status': 'saving',
            'current': tracks_count,
            'total': playlist_data['track_count'],
            'message': f'Сохранение {tracks_count} треков в базу...'
        }
        request.session.save()
        
        # Сохраняем в БД
        playlist = service.save_playlist_preview(playlist_data)
        
        if not playlist:
            request.session['loading_progress'] = {'status': 'error', 'message': 'Ошибка сохранения'}
            request.session.save()
            return JsonResponse({'error': 'Ошибка сохранения'}, status=400)
        
        saved_tracks = playlist.tracks.count()
        
        # Успешное завершение
        request.session['loading_progress'] = {
            'status': 'completed',
            'current': saved_tracks,
            'total': playlist_data['track_count'],
            'message': f'Загружено {saved_tracks} треков!',
            'playlist_id': playlist.id
        }
        request.session.save()
        
        return JsonResponse({
            'status': 'success',
            'playlist_id': playlist.id,
            'tracks_loaded': saved_tracks,
            'total_tracks': playlist_data['track_count']
        })
        
    except Exception as e:
        print(f"Error loading playlist: {e}")
        import traceback
        traceback.print_exc()
        
        request.session['loading_progress'] = {'status': 'error', 'message': str(e)}
        request.session.save()
        
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def playlist_progress_api(request):
    """
API для получения прогресса загрузки"""
    progress = request.session.get('loading_progress', {'status': 'pending'})
    return JsonResponse(progress)


@login_required
def playlist_preview_view(request, playlist_id):
    """Предпросмотр плейлиста с выбором треков"""
    from django.core.paginator import Paginator
    import json
    
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    
    # Получаем скачанный плейлист и список скачанных треков
    downloaded_playlist = playlist.get_downloaded_playlist()
    downloaded_track_ids = set()
    if downloaded_playlist:
        downloaded_track_ids = set(
            downloaded_playlist.tracks.values_list('title', 'artist')
        )
    
    # Получаем количество треков на странице
    per_page = request.GET.get('per_page', '50')
    try:
        per_page = int(per_page)
        if per_page not in [25, 50, 100]:
            per_page = 50
    except:
        per_page = 50
    
    tracks = playlist.tracks.all()
    paginator = Paginator(tracks, per_page)
    
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Помечаем скачанные треки
    for track in page_obj:
        track.is_downloaded = (track.title, track.artist) in downloaded_track_ids
    
    # Получаем все ID треков для JavaScript (кроме уже скачанных)
    all_track_ids = []
    for track in tracks:
        if (track.title, track.artist) not in downloaded_track_ids:
            all_track_ids.append(track.yandex_track_id)
    
    context = {
        'playlist': playlist,
        'tracks': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
        'total_tracks': tracks.count(),
        'downloaded_playlist': downloaded_playlist,
        'downloaded_count': len(downloaded_track_ids),
        'all_track_ids_json': json.dumps(all_track_ids)
    }
    
    return render(request, 'music_downloader/playlist_preview.html', context)


@login_required
def download_tracks_view(request, playlist_id):
    """Скачивание выбранных треков (редирект на страницу прогресса)"""
    if request.method != 'POST':
        return redirect('playlist_preview', playlist_id=playlist_id)
    
    # Сохраняем выбранные треки в сессии
    selected_tracks = request.POST.getlist('tracks')
    if not selected_tracks:
        messages.warning(request, 'Выберите хотя бы один трек для скачивания')
        return redirect('playlist_preview', playlist_id=playlist_id)
    
    request.session['download_playlist_id'] = playlist_id
    request.session['download_track_ids'] = selected_tracks
    request.session['loading_progress'] = {'status': 'pending', 'current': 0, 'total': len(selected_tracks), 'message': 'Подготовка...'}
    request.session.save()
    
    return redirect('download_progress')


@login_required
def download_progress_view(request):
    """Страница прогресса скачивания"""
    playlist_id = request.session.get('download_playlist_id')
    if not playlist_id:
        messages.error(request, 'Нет активной задачи скачивания')
        return redirect('home')
    
    return render(request, 'music_downloader/download_progress.html', {})


@login_required
def download_start_api(request):
    """API: запускает скачивание выбранных треков"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    playlist_id = request.session.get('download_playlist_id')
    track_ids = request.session.get('download_track_ids', [])
    if not playlist_id or not track_ids:
        return JsonResponse({'error': 'Нет данных для скачивания'}, status=400)
    
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Профиль не найден'}, status=400)
    
    if not profile.yandex_token:
        return JsonResponse({'error': 'Не указан токен'}, status=400)
    
    # Запускаем скачивание
    service = YandexMusicService(token=profile.yandex_token, user_id=request.user.id, session=request.session)
    success, message, downloaded_playlist = service.download_tracks(playlist_id, track_ids)
    
    if success:
        # Убеждаемся, что прогресс достигает 100%
        total_tracks = len(track_ids)
        request.session['loading_progress'] = {
            'status': 'completed',
            'current': total_tracks,
            'total': total_tracks,
            'message': message,
            'downloaded_playlist_id': downloaded_playlist.id if downloaded_playlist else None
        }
        request.session.save()
        return JsonResponse({'status': 'success', 'message': message, 'downloaded_playlist_id': downloaded_playlist.id if downloaded_playlist else None})
    else:
        request.session['loading_progress'] = {'status': 'error', 'message': message}
        request.session.save()
        return JsonResponse({'error': message}, status=500)


@login_required
def download_progress_api(request):
    """API: вернуть текущий прогресс скачивания"""
    progress = request.session.get('loading_progress', {'status': 'pending'})
    return JsonResponse(progress)




@login_required
def downloaded_playlists_view(request):
    """Страница со списком скачанных плейлистов"""
    # Получаем все скачанные плейлисты пользователя
    downloaded_playlists = DownloadedPlaylist.objects.filter(user=request.user).order_by('-download_date')
    
    context = {
        'downloaded_playlists': downloaded_playlists
    }
    
    return render(request, 'music_downloader/downloaded_playlists.html', context)


@login_required
def downloaded_playlist_detail_view(request, playlist_id):
    """Детали скачанного плейлиста с возможностью выбора"""
    downloaded_playlist = get_object_or_404(DownloadedPlaylist, id=playlist_id, user=request.user)
    
    # Если это POST запрос - обрабатываем выбор треков для zip
    if request.method == 'POST':
        selected_tracks = request.POST.getlist('tracks')
        if selected_tracks:
            # Сохраняем выбранные треки в сессии и перенаправляем на скачивание zip
            request.session['zip_track_ids'] = selected_tracks
            return redirect('download_zip', playlist_id=playlist_id)
        else:
            messages.warning(request, 'Выберите хотя бы один трек')
    
    tracks = downloaded_playlist.tracks.all()
    
    context = {
        'downloaded_playlist': downloaded_playlist,
        'tracks': tracks
    }
    
    return render(request, 'music_downloader/downloaded_playlist_detail.html', context)


@login_required
def download_file_view(request, track_id):
    """Скачивание файла трека"""
    track = get_object_or_404(DownloadedTrack, id=track_id)
    
    # Проверяем что пользователь имеет доступ к треку
    if track.downloaded_playlist.user != request.user:
        raise Http404("Файл не найден")
    
    file_path = Path(settings.MEDIA_ROOT) / track.file_path
    
    if not file_path.exists():
        raise Http404("Файл не найден")
    
    return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_path.name)


def transliterate_russian(text):
    """Транслитерация русского текста в латиницу"""
    translit_map = {
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
        'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
        'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts',
        'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = []
    for char in text:
        if char in translit_map:
            result.append(translit_map[char])
        else:
            result.append(char)
    return ''.join(result)


@login_required
def download_zip_view(request, playlist_id):
    """Скачивание выбранных треков в zip архиве"""
    import zipfile
    import tempfile
    import os
    from django.http import HttpResponse
    
    downloaded_playlist = get_object_or_404(DownloadedPlaylist, id=playlist_id, user=request.user)
    
    # Получаем выбранные ID треков из сессии
    track_ids = request.session.get('zip_track_ids', [])
    if not track_ids:
        messages.error(request, 'Не выбраны треки для скачивания')
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)
    
    # Преобразуем ID в целые числа
    track_ids = [int(tid) for tid in track_ids]
    
    # Получаем выбранные треки
    tracks = downloaded_playlist.tracks.filter(id__in=track_ids)
    
    if not tracks.exists():
        messages.error(request, 'Не найдены выбранные треки')
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)
    
    # Создаем временный zip файл
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    
    try:
        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            media_root = Path(settings.MEDIA_ROOT)
            
            for track in tracks:
                file_path = media_root / track.file_path
                if file_path.exists():
                    # Добавляем файл в архив с именем файла
                    zipf.write(file_path, arcname=file_path.name)
        
        # Открываем файл для чтения
        with open(temp_file.name, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            # Транслитерируем название плейлиста
            transliterated_title = transliterate_russian(downloaded_playlist.title)
            # Санитаризируем имя файла
            safe_title = "".join(c for c in transliterated_title if c.isalnum() or c in (' ', '-', '_')).strip()
            # Заменяем пробелы на нижние подчеркивания
            safe_title = safe_title.replace(' ', '_')
            # Добавляем дату скачивания к имени файла
            download_date_str = downloaded_playlist.download_date.strftime('%Y-%m-%d_%H-%M')
            zip_filename = f"{safe_title}_{download_date_str}.zip"
            
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            
            # Очищаем сессию
            if 'zip_track_ids' in request.session:
                del request.session['zip_track_ids']
            
            return response
    finally:
        # Удаляем временный файл
        try:
            os.unlink(temp_file.name)
        except:
            pass


@login_required
def delete_selected_tracks_view(request, playlist_id):
    """Групповое удаление выбранных треков из скачанного плейлиста"""
    downloaded_playlist = get_object_or_404(DownloadedPlaylist, id=playlist_id, user=request.user)

    if request.method != 'POST':
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)

    track_ids = request.POST.getlist('tracks')
    if not track_ids:
        messages.warning(request, 'Выберите хотя бы один трек для удаления')
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)

    try:
        track_ids_int = [int(tid) for tid in track_ids]
    except ValueError:
        messages.error(request, 'Некорректные идентификаторы треков')
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)

    media_root = Path(settings.MEDIA_ROOT)
    tracks = downloaded_playlist.tracks.filter(id__in=track_ids_int)

    deleted_count = 0
    for track in tracks:
        file_path = media_root / track.file_path
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
        track.delete()
        deleted_count += 1

    # Обновляем счетчик треков в плейлисте
    downloaded_playlist.tracks_count = downloaded_playlist.tracks.count()
    downloaded_playlist.save()

    if deleted_count:
        messages.success(request, f'Удалено {deleted_count} трек(ов)')
    else:
        messages.warning(request, 'Не удалось удалить выбранные треки')

    return redirect('downloaded_playlist_detail', playlist_id=playlist_id)


@login_required
def delete_downloaded_track_view(request, track_id):
    """Удаление отдельного трека"""
    track = get_object_or_404(DownloadedTrack, id=track_id)
    
    # Проверяем что пользователь имеет доступ к треку
    if track.downloaded_playlist.user != request.user:
        raise Http404("Трек не найден")
    
    if request.method == 'POST':
        playlist_id = track.downloaded_playlist.id
        track_title = track.title
        
        # Удаляем файл трека
        media_root = Path(settings.MEDIA_ROOT)
        file_path = media_root / track.file_path
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
                messages.error(request, f'Ошибка удаления файла: {e}')
                return redirect('downloaded_playlist_detail', playlist_id=playlist_id)
        
        # Удаляем запись из базы данных
        track.delete()
        
        # Обновляем счетчик треков в плейлисте
        track.downloaded_playlist.tracks_count = track.downloaded_playlist.tracks.count()
        track.downloaded_playlist.save()
        
        messages.success(request, f'Трек "{track_title}" успешно удален')
        return redirect('downloaded_playlist_detail', playlist_id=playlist_id)
    
    # Для GET запроса возвращаем на страницу плейлиста
    return redirect('downloaded_playlist_detail', playlist_id=track.downloaded_playlist.id)


@login_required
def delete_downloaded_playlist_view(request, playlist_id):
    """Удаление скачанного плейлиста"""
    downloaded_playlist = get_object_or_404(DownloadedPlaylist, id=playlist_id, user=request.user)
    
    if request.method == 'POST':
        # Удаляем файлы треков
        import shutil
        media_root = Path(settings.MEDIA_ROOT)
        
        for track in downloaded_playlist.tracks.all():
            file_path = media_root / track.file_path
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        
        # Пытаемся удалить директорию плейлиста (если пустая)
        if downloaded_playlist.playlist:
            playlist_dir = media_root / f"user_{request.user.id}" / f"playlist_{downloaded_playlist.playlist.id}_{downloaded_playlist.playlist.yandex_playlist_id}"
            if playlist_dir.exists():
                try:
                    # Удаляем директорию только если она пустая или содержит только удаленные файлы
                    if not any(playlist_dir.iterdir()):
                        playlist_dir.rmdir()
                except Exception as e:
                    print(f"Error removing directory {playlist_dir}: {e}")
        
        # Удаляем запись из базы данных
        playlist_title = downloaded_playlist.title
        downloaded_playlist.delete()
        
        messages.success(request, f'Плейлист "{playlist_title}" успешно удален')
        return redirect('downloaded_playlists')
    
    # Для GET запроса возвращаем на страницу плейлиста
    return redirect('downloaded_playlist_detail', playlist_id=playlist_id)
