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
    
    return render(request, 'music/register.html', {'form': form})


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
    
    return render(request, 'music/login.html')


@login_required
def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('login')


@login_required
def home_view(request):
    """Главная страница"""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    playlists = Playlist.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'profile': profile,
        'playlists': playlists,
        'has_token': bool(profile.yandex_token)
    }
    
    return render(request, 'music/home.html', context)


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
    
    return render(request, 'music/profile.html', {'form': form, 'profile': profile})


@login_required
def load_playlist_view(request):
    """Загрузка плейлиста для предпросмотра"""
    if request.method == 'POST':
        form = PlaylistLoadForm(request.POST)
        if form.is_valid():
            playlist_url = form.cleaned_data['playlist_url']
            
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                messages.error(request, 'Профиль не найден')
                return redirect('home')
            
            if not profile.yandex_token:
                messages.error(request, 'Необходимо добавить токен Yandex Music в профиле')
                return redirect('profile')
            
            # Сохраняем URL в сессии для асинхронной загрузки
            request.session['playlist_url'] = playlist_url
            request.session['loading_progress'] = {'status': 'pending', 'current': 0, 'total': 0}
            
            return redirect('playlist_loading')
    else:
        form = PlaylistLoadForm()
    
    return render(request, 'music/load_playlist.html', {'form': form})


@login_required
def playlist_loading_view(request):
    """Страница с прогресс-баром"""
    playlist_url = request.session.get('playlist_url')
    if not playlist_url:
        messages.error(request, 'Не указан URL плейлиста')
        return redirect('load_playlist')
    
    return render(request, 'music/playlist_loading.html', {'playlist_url': playlist_url})


@login_required  
def playlist_load_api(request):
    """
API для асинхронной загрузки плейлиста"""
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    playlist_url = request.session.get('playlist_url')
    if not playlist_url:
        return JsonResponse({'error': 'Не указан URL плейлиста'}, status=400)
    
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Профиль не найден'}, status=400)
    
    if not profile.yandex_token:
        return JsonResponse({'error': 'Не указан токен'}, status=400)
    
    try:
        # Создаем сервис с передачей сессии для прогресса
        service = YandexMusicService(token=profile.yandex_token, user_id=request.user.id, session=request.session)
        
        # Обновляем прогресс
        request.session['loading_progress'] = {'status': 'loading', 'current': 0, 'total': 0, 'message': 'Загрузка информации о плейлисте...'}
        request.session.save()
        
        # Загружаем плейлист
        playlist_data = service.get_playlist_info(playlist_url)
        
        if not playlist_data:
            request.session['loading_progress'] = {'status': 'error', 'message': 'Не удалось загрузить плейлист'}
            request.session.save()
            return JsonResponse({'error': 'Не удалось загрузить плейлист'}, status=400)
        
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
    
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    
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
    
    context = {
        'playlist': playlist,
        'tracks': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
        'total_tracks': tracks.count()
    }
    
    return render(request, 'music/playlist_preview.html', context)


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
    
    return render(request, 'music/download_progress.html', {})


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
        request.session['loading_progress'] = {
            'status': 'completed',
            'current': request.session['loading_progress'].get('total', 0),
            'total': request.session['loading_progress'].get('total', 0),
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
    """Просмотр скачанных плейлистов"""
    downloaded_playlists = DownloadedPlaylist.objects.filter(user=request.user).order_by('-download_date')
    
    context = {
        'downloaded_playlists': downloaded_playlists
    }
    
    return render(request, 'music/downloaded_playlists.html', context)


@login_required
def downloaded_playlist_detail_view(request, playlist_id):
    """Детали скачанного плейлиста"""
    downloaded_playlist = get_object_or_404(DownloadedPlaylist, id=playlist_id, user=request.user)
    tracks = downloaded_playlist.tracks.all()
    
    context = {
        'downloaded_playlist': downloaded_playlist,
        'tracks': tracks
    }
    
    return render(request, 'music/downloaded_playlist_detail.html', context)


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
