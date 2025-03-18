from django import forms
from .models import UserChallenge, Trade, WithdrawalRequest
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.forms import widgets



class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='E-posta Adresi',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].label = 'Kullanıcı Adı'

class UserChallengeForm(forms.ModelForm):
    class Meta:
        model = UserChallenge
        fields = ['challenge_type', 'start_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {
            'username': 'Kullanıcı Adı',
            'first_name': 'Ad',
            'last_name': 'Soyad',
            'email': 'E-posta'
        }

class TradeForm(forms.ModelForm):
    class Meta:
        model = Trade
        fields = [
            'symbol', 'trade_type', 'lot_size', 
            'entry_price', 'exit_price', 
            'entry_date', 'exit_date',
            'trade_result', 'custom_result', 
            'profit_loss_percentage', 'notes'
        ]
        widgets = {
            # Diğer widget'lar aynı kalacak...
            'custom_result': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Özel sonuç açıklaması'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Trade result seçeneklerini güncelle - boş seçenek olmayacak
        self.fields['trade_result'].choices = [
            ('TP', 'TP Oldum'),
            ('SL', 'Stop Oldum'),
            ('CUSTOM', 'Özel')
        ]
        
        # İşlem tipi seçeneklerini güncelle - boş seçenek olmayacak
        self.fields['trade_type'].choices = [
            ('BUY', 'Alış'),
            ('SELL', 'Satış')
        ]
        
        # custom_result başlangıçta gerekli değil
        self.fields['custom_result'].required = False
        
        # Profit/loss açıklaması ekle
        self.fields['profit_loss_percentage'].help_text = 'Pozitif değer kar, negatif değer zarar anlamına gelir (örn: 3 veya -2.5)'
        
    def clean(self):
        cleaned_data = super().clean()
        trade_result = cleaned_data.get('trade_result')
        custom_result = cleaned_data.get('custom_result')
        
        # CUSTOM seçildiğinde özel sonuç gerekli
        if trade_result == 'CUSTOM' and not custom_result:
            self.add_error('custom_result', 'Özel sonuç seçildiğinde bu alan zorunludur.')
            
        return cleaned_data
class WithdrawalRequestForm(forms.ModelForm):
    class Meta:
        model = WithdrawalRequest
        fields = ['amount']
        