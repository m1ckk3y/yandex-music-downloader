from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


class RegistrationForm(UserCreationForm):
    """Форма регистрации с полем для токена"""
    email = forms.EmailField(required=True, label='Email')
    yandex_token = forms.CharField(
        max_length=500,
        required=False,
        label='Токен Yandex Music',
        help_text='Получите токен по инструкции: https://yandex-music.readthedocs.io/en/main/token.html',
        widget=forms.TextInput(attrs={'placeholder': 'Необязательно, можно добавить позже'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'yandex_token']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # Создаем профиль пользователя
            UserProfile.objects.create(
                user=user,
                yandex_token=self.cleaned_data.get('yandex_token', '')
            )
        return user


class ProfileUpdateForm(forms.ModelForm):
    """Форма обновления профиля"""
    class Meta:
        model = UserProfile
        fields = ['yandex_token']
        labels = {
            'yandex_token': 'Токен Yandex Music'
        }
        widgets = {
            'yandex_token': forms.TextInput(attrs={'class': 'form-control'})
        }


class PlaylistLoadForm(forms.Form):
    """Форма для загрузки плейлиста"""
    playlist_url = forms.CharField(
        max_length=500,
        label='URL или ID плейлиста',
        widget=forms.TextInput(attrs={'placeholder': 'Введите URL плейлиста', 'class': 'form-control'})
    )
