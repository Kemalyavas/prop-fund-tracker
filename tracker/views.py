from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required 
from django.contrib import messages
from .models import FundingProvider, ChallengeType, UserChallenge, Trade, WithdrawalRequest
from .forms import UserChallengeForm, TradeForm, WithdrawalRequestForm
from django.db.models import Sum, Avg
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth import logout 
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils import timezone  # update_challenge_status için gerekli
from django.db import models as django_models  # trading_statistics için gerekli
from .models import Trade, UserChallenge  # ve diğer modeller
from django.contrib.auth.forms import UserCreationForm
from .forms import UserProfileForm  
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from tracker.forms import CustomUserCreationForm
from django import forms
from decimal import Decimal


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


class RegisterView(CreateView):
    form_class = CustomUserCreationForm  # UserCreationForm yerine CustomUserCreationForm kullanıyoruz
    success_url = reverse_lazy('login')
    template_name = 'registration/register.html'
    
    def form_valid(self, form):
        # Form geçerliyse kullanıcıyı kaydedin ve e-postayı ekleyin
        user = form.save()
        user.email = form.cleaned_data.get('email')
        user.save()
        return super().form_valid(form)




def check_challenge_status(challenge):
    """
    Challenge durumunu işlemlere göre otomatik kontrol edip günceller.
    """
    from django.utils import timezone
    
    # Challenge tipini ve aşama sayısını al
    challenge_type = challenge.challenge_type
    stage_count = 1
    
    # Challenge isminden aşama sayısını çıkar (örn. "1 Stage $10K")
    if challenge_type.name.startswith('1'):
        stage_count = 1
    elif challenge_type.name.startswith('2'):
        stage_count = 2
    elif challenge_type.name.startswith('3'):
        stage_count = 3
    
    # Challenge parametrelerini al
    profit_target = challenge_type.profit_target  # Yüzde olarak
    max_daily_loss = challenge_type.max_daily_loss  # Yüzde olarak
    max_total_loss = challenge_type.max_total_loss  # Yüzde olarak
    
    # Başlangıç bakiyesini ve güncel bakiyeyi al
    initial_balance = challenge_type.account_size
    current_balance = challenge.current_balance
    
    # İşlemleri al ve kar/zarar durumunu hesapla
    trades = challenge.trades.all()  # trades olarak düzeltildi (trade_set yerine)
    
    # Toplam kar/zarar yüzdesi
    profit_percentage = ((current_balance - initial_balance) / initial_balance) * 100
    
    # Günlük işlem grupları
    daily_trades = {}
    for trade in trades:
        date_key = trade.entry_date.date()
        if date_key not in daily_trades:
            daily_trades[date_key] = []
        daily_trades[date_key].append(trade)
    
    # Günlük kayıp limiti kontrolü
    for date, day_trades in daily_trades.items():
        day_balance = initial_balance
        for trade in day_trades:
            day_balance += trade.profit_loss
        
        day_loss_percentage = ((day_balance - initial_balance) / initial_balance) * 100
        if day_loss_percentage <= -max_daily_loss:
            # Günlük kayıp limitine ulaşıldı - Challenge başarısız
            challenge.status = 'FAILED'
            challenge.failure_reason = f"Günlük kayıp limiti aşıldı: {date} - {day_loss_percentage:.2f}%"
            challenge.save()
            return
    
    # Toplam kayıp limiti kontrolü
    if profit_percentage <= -max_total_loss:
        # Toplam kayıp limitine ulaşıldı - Challenge başarısız
        challenge.status = 'FAILED'
        challenge.failure_reason = f"Toplam kayıp limiti aşıldı: {profit_percentage:.2f}%"
        challenge.save()
        return
        
    elif stage_count == 2:
        # İki aşamalı challenge
        current_stage = getattr(challenge, 'current_stage', 1)
        
        if current_stage == 1 and profit_percentage >= profit_target:
            # 1. aşama tamamlandı
            challenge.current_stage = 2
            challenge.stage1_completion_date = timezone.now().date()
            challenge.save()
            # Durumu hala 'ACTIVE' kalır
            return
        
        elif current_stage == 2 and profit_percentage >= 5.0:  # 2. aşama için %5 hedef
            # 2. aşama tamamlandı - Challenge fonlandı
            challenge.status = 'FUNDED'  # COMPLETED yerine FUNDED olarak değiştirildi
            challenge.completion_date = timezone.now().date()
            challenge.funding_date = timezone.now().date()  # Fonlama tarihi eklendi
            # Varsayılan kar payı yüzdesi (%80)
            if not challenge.profit_share_percentage:
                challenge.profit_share_percentage = 80.0
            challenge.save()
            return
    
    elif stage_count == 3:
        # Üç aşamalı challenge
        current_stage = getattr(challenge, 'current_stage', 1)
        
        if current_stage == 1 and profit_percentage >= 5.0:  # Her aşama için %5
            # 1. aşama tamamlandı
            challenge.current_stage = 2
            challenge.stage1_completion_date = timezone.now().date()
            challenge.save()
            return
        
        elif current_stage == 2 and profit_percentage >= 5.0:
            # 2. aşama tamamlandı
            challenge.current_stage = 3
            challenge.stage2_completion_date = timezone.now().date()
            challenge.save()
            return
        
        elif current_stage == 3 and profit_percentage >= 5.0:
            # 3. aşama tamamlandı - Challenge fonlandı
            challenge.status = 'FUNDED'  # COMPLETED yerine FUNDED olarak değiştirildi
            challenge.completion_date = timezone.now().date()
            challenge.funding_date = timezone.now().date()  # Fonlama tarihi eklendi
            # Varsayılan kar payı yüzdesi (%80)
            if not challenge.profit_share_percentage:
                challenge.profit_share_percentage = 80.0
            challenge.save()
            return
    
    # Eğer buraya kadar geldiyse, durumu hala 'ACTIVE' olmalı
    if challenge.status != 'ACTIVE':
        challenge.status = 'ACTIVE'
        challenge.save()

def check_auth(request):
    """AJAX için oturum durumunu kontrol eden endpoint"""
    return JsonResponse({
        'authenticated': request.user.is_authenticated
    })


@login_required
def dashboard(request):
    # Kullanıcının challenge'larını al
    active_challenges = UserChallenge.objects.filter(user=request.user, status='ACTIVE')
    completed_challenges = UserChallenge.objects.filter(user=request.user, status='COMPLETED')
    failed_challenges = UserChallenge.objects.filter(user=request.user, status='FAILED')
    funded_challenges = UserChallenge.objects.filter(user=request.user, status='FUNDED')

    # tüm challenge'ları bir araya getir
    all_challenges = list(active_challenges) + list(completed_challenges) + list(failed_challenges) + list(funded_challenges)
    
    # Kar/zarar yüzdesi hesaplama
    profit_percentage = {}
    for challenge in all_challenges:
        initial = challenge.challenge_type.account_size
        current = challenge.current_balance
        profit_percentage[challenge.id] = ((current - initial) / initial) * 100
    
    # Kar hedef yüzdesi hesaplama
    profit_target_percentage = {}
    for challenge in all_challenges:
        initial = challenge.challenge_type.account_size
        target_percentage = challenge.challenge_type.profit_target
        profit_target_percentage[challenge.id] = target_percentage
    
    # Toplam fonlanmış miktar
    total_funded_amount = funded_challenges.aggregate(
        total=Sum('challenge_type__account_size')
    )['total'] or 0
    
    # Toplam payout hesaplama
    total_payout = Decimal('0.00')
    for challenge in funded_challenges:
        total_payout += challenge.calculate_payout()
    
    # Son işlemleri al
    recent_trades = Trade.objects.filter(user=request.user).order_by('-entry_date')[:10]
    
    context = {
        'active_challenges': active_challenges,
        'completed_challenges': completed_challenges,
        'failed_challenges': failed_challenges,
        'funded_challenges': funded_challenges,
        'profit_percentage': profit_percentage,
        'profit_target_percentage': profit_target_percentage,
        'total_funded_amount': total_funded_amount,
        'total_payout': total_payout,
        'recent_trades': recent_trades,
    }
    
    return render(request, 'tracker/dashboard.html', context)
    
    # tüm challenge'ları bir araya getir
    all_challenges = list(active_challenges) + list(completed_challenges) + list(failed_challenges) + list(funded_challenges)
    
    # Kar/zarar yüzdesi hesaplama
    profit_percentage = {}
    for challenge in all_challenges:
        initial = challenge.challenge_type.account_size
        current = challenge.current_balance
        profit_percentage[challenge.id] = ((current - initial) / initial) * 100
    
    # Kar hedef yüzdesi hesaplama
    profit_target_percentage = {}
    for challenge in all_challenges:
        initial = challenge.challenge_type.account_size
        target_percentage = challenge.challenge_type.profit_target
        profit_target_percentage[challenge.id] = target_percentage
    
    # Toplam fonlanan miktarı hesapla
    total_funded_amount = sum(challenge.challenge_type.account_size for challenge in funded_challenges)
    
    # Son işlemleri al
    recent_trades = Trade.objects.filter(user=request.user).order_by('-entry_date')[:10]
    
    # Performans verilerini hazırla
    performance_data = {}  # Bu kısmı ihtiyaca göre doldur
    
    context = {
        'active_challenges': active_challenges,
        'completed_challenges': completed_challenges,
        'failed_challenges': failed_challenges,
        'funded_challenges': funded_challenges,
        'profit_percentage': profit_percentage,
        'profit_target_percentage': profit_target_percentage,
        'total_funded_amount': total_funded_amount,  # Toplam fonlanan miktar
        'recent_trades': recent_trades,
        'performance_data': performance_data,
    }
    
    return render(request, 'tracker/dashboard.html', context)

# views.py - Düzeltilmiş logout fonksiyonu
def custom_logout(request):
    logout(request)
    response = redirect('login')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def challenge_detail(request, challenge_id):
    challenge = get_object_or_404(UserChallenge, id=challenge_id, user=request.user)
    trades = Trade.objects.filter(challenge=challenge).order_by('-entry_date')
    
    # Challenge metrikleri
    winning_trades = trades.filter(profit_loss__gt=0).count()
    losing_trades = trades.filter(profit_loss__lt=0).count()
    total_trades = trades.count()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
     # Kazanç yüzdeleri üzerinden istatistik
    winning_trades = trades.filter(trade_result='TP')
    losing_trades = trades.filter(trade_result='SL')
    
    avg_win_percentage = winning_trades.aggregate(Avg('profit_loss_percentage'))['profit_loss_percentage__avg'] or 0
    avg_loss_percentage = losing_trades.aggregate(Avg('profit_loss_percentage'))['profit_loss_percentage__avg'] or 0
    
    context = {
        'challenge': challenge,
        'trades': trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
    }
    return render(request, 'tracker/challenge_detail.html', context)

@login_required
def add_challenge(request):
    if request.method == 'POST':
        # Form verilerini al
        stage_count = request.POST.get('stage_count')
        account_size = request.POST.get('account_size')
        start_date = request.POST.get('start_date')
        
        try:
            # Fxify sağlayıcısını bul veya oluştur
            provider, created = FundingProvider.objects.get_or_create(
                name='Fxify',
                defaults={
                    'website': 'https://fxify.com',
                }
            )
            
            # Hesap büyüklüğüne göre fiyat belirle - BU SATIRI TAŞIDIM
            price = float(account_size) * 0.05  # Örnek: Hesap büyüklüğünün %5'i kadar ücret
            
            # Aşama sayısı ve hesap büyüklüğüne göre uygun challenge tipini bul
            challenge_type = None
            
            # Aşama sayısına göre uygun parametrelerle challenge tipini bul
            if stage_count == '1':
                # 1 aşamalı: %10 kar hedefi, %3 günlük kayıp limiti, %6 toplam kayıp limiti
                challenge_type = ChallengeType.objects.filter(
                    provider=provider,
                    account_size=float(account_size),
                    profit_target=10.0,
                    max_daily_loss=3.0,
                    max_total_loss=6.0
                ).first()
            elif stage_count == '2':
                # 2 aşamalı: Bu durumda ilk aşamanın challenge tipini seçiyoruz
                challenge_type = ChallengeType.objects.filter(
                    provider=provider,
                    account_size=float(account_size),
                    profit_target=10.0,
                    max_daily_loss=4.0,
                    max_total_loss=10.0
                ).first()
            elif stage_count == '3':
                # 3 aşamalı: Her aşama için %5 kar hedefi, günlük kayıp limiti ve toplam kayıp limiti
                challenge_type = ChallengeType.objects.filter(
                    provider=provider,
                    account_size=float(account_size),
                    profit_target=5.0,
                    max_daily_loss=5.0,
                    max_total_loss=5.0
                ).first()
                
            if not challenge_type:
                # Uygun challenge tipi bulunamadıysa, yeni bir tane oluştur
                challenge_type = ChallengeType.objects.create(
                    provider=provider,
                    name=f"{stage_count} Stage ${int(float(account_size)/1000)}K",
                    account_size=float(account_size),
                    price=price,  # Şimdi price tanımlandıktan sonra kullanılıyor
                    profit_target=10.0 if stage_count == '1' or stage_count == '2' else 5.0,
                    max_daily_loss=3.0 if stage_count == '1' else (4.0 if stage_count == '2' else 5.0),
                    max_total_loss=6.0 if stage_count == '1' else (10.0 if stage_count == '2' else 5.0),
                    duration_days=999  # Varsayılan olarak 30 gün ekledim
                )
                
            # Yeni challenge oluştur
            challenge = UserChallenge(
                user=request.user,
                challenge_type=challenge_type,
                start_date=start_date,
                status='ACTIVE',
                current_balance=float(account_size),
                highest_balance=float(account_size),
                lowest_balance=float(account_size)
            )
            challenge.save()
            
            messages.success(request, 'Challenge başarıyla eklendi!')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Bir hata oluştu: {str(e)}')
            return redirect('add_challenge')
    else:
        form = UserChallengeForm()
    
    context = {
        'form': form,
        'providers': FundingProvider.objects.all(),
    }
    return render(request, 'tracker/add_challenge.html', context)

from decimal import Decimal

@login_required
def add_trade(request, challenge_id):
    challenge = get_object_or_404(UserChallenge, id=challenge_id, user=request.user)
    
    if request.method == 'POST':
        form = TradeForm(request.POST)
        if form.is_valid():
            trade = form.save(commit=False)
            trade.user = request.user
            trade.challenge = challenge
            
            # Başlangıç bakiye değerini al
            initial_balance = challenge.challenge_type.account_size
            
            # Kar/Zarar yüzdesi işlenmesi
            if trade.profit_loss_percentage is not None:
                # Yüzdeyi ondalık sayıya çevir
                percentage_decimal = Decimal(str(float(trade.profit_loss_percentage) / 100))
                
                # Kar/zarar tutarını hesapla
                trade.profit_loss = initial_balance * percentage_decimal
            
            # İşlemi kaydet
            trade.save()
            
            # Challenge bakiyesini güncelle
            challenge.current_balance += trade.profit_loss
            
            # En yüksek ve en düşük bakiyeyi güncelle
            if challenge.current_balance > challenge.highest_balance:
                challenge.highest_balance = challenge.current_balance
            if challenge.current_balance < challenge.lowest_balance:
                challenge.lowest_balance = challenge.current_balance
                
            challenge.save()
            
            # Challenge durumunu kontrol et
            check_challenge_status(challenge)
            
            # Başarı mesajını hazırla
            result_type = "Kar" if trade.profit_loss_percentage > 0 else "Zarar"
            messages.success(request, f"İşlem başarıyla eklendi! {result_type}: ${abs(trade.profit_loss):.2f} (%{abs(trade.profit_loss_percentage):.2f})")
            return redirect('challenge_detail', challenge_id=challenge.id)
    else:
        # Form ilk yüklendiğinde
        form = TradeForm(initial={
            'entry_date': timezone.now(),
            'trade_result': 'TP'  # Varsayılan olarak TP seçili
        })
    
    context = {
        'form': form,
        'challenge': challenge
    }
    return render(request, 'tracker/add_trade.html', context)

# tracker/views.py içinde check_challenge_status fonksiyonunu güncelleyin
def check_challenge_status(challenge):
    """
    Challenge durumunu işlemlere göre otomatik kontrol edip günceller.
    """
    from django.utils import timezone
    
    # Challenge tipini ve aşama sayısını al
    challenge_type = challenge.challenge_type
    stage_count = 1
    
    # Challenge isminden aşama sayısını çıkar (örn. "1 Stage $10K")
    if challenge_type.name.startswith('1'):
        stage_count = 1
    elif challenge_type.name.startswith('2'):
        stage_count = 2
    elif challenge_type.name.startswith('3'):
        stage_count = 3
    
    # Challenge parametrelerini al
    profit_target = challenge_type.profit_target  # Yüzde olarak
    max_daily_loss = challenge_type.max_daily_loss  # Yüzde olarak
    max_total_loss = challenge_type.max_total_loss  # Yüzde olarak
    
    # Başlangıç bakiyesini ve güncel bakiyeyi al
    initial_balance = challenge_type.account_size
    current_balance = challenge.current_balance
    
    # İşlemleri al ve kar/zarar durumunu hesapla
    trades = challenge.trades.all()
    
    # Toplam kar/zarar yüzdesi
    profit_percentage = ((current_balance - initial_balance) / initial_balance) * 100
    
    # Günlük işlem grupları
    daily_trades = {}
    for trade in trades:
        date_key = trade.entry_date.date()
        if date_key not in daily_trades:
            daily_trades[date_key] = []
        daily_trades[date_key].append(trade)
    
    # Günlük kayıp limiti kontrolü
    for date, day_trades in daily_trades.items():
        day_balance = initial_balance
        for trade in day_trades:
            day_balance += trade.profit_loss
        
        day_loss_percentage = ((day_balance - initial_balance) / initial_balance) * 100
        if day_loss_percentage <= -max_daily_loss:
            # Günlük kayıp limitine ulaşıldı - Challenge başarısız
            challenge.status = 'FAILED'
            challenge.failure_reason = f"Günlük kayıp limiti aşıldı: {date} - {day_loss_percentage:.2f}%"
            challenge.save()
            return
    
    # Toplam kayıp limiti kontrolü
    if profit_percentage <= -max_total_loss:
        # Toplam kayıp limitine ulaşıldı - Challenge başarısız
        challenge.status = 'FAILED'
        challenge.failure_reason = f"Toplam kayıp limiti aşıldı: {profit_percentage:.2f}%"
        challenge.save()
        return
    
    # Kar hedefi kontrolü - Aşama sayısına göre farklı davranış
    if stage_count == 1:
        # Tek aşamalı challenge
        if profit_percentage >= profit_target:
            # Kar hedefine ulaşıldı - Challenge fonlandı
            challenge.status = 'FUNDED'
            challenge.completion_date = timezone.now().date()
            challenge.funding_date = timezone.now().date()  # Fonlama tarihi eklendi
            # Varsayılan kar payı yüzdesi (%80)
            if not challenge.profit_share_percentage:
                challenge.profit_share_percentage = 80.0
            challenge.save()
            return
    
    elif stage_count == 2:
        # İki aşamalı challenge
        current_stage = getattr(challenge, 'current_stage', 1)
        
        if current_stage == 1 and profit_percentage >= profit_target:
            # 1. aşama tamamlandı
            challenge.current_stage = 2
            challenge.stage1_completion_date = timezone.now().date()
            challenge.save()
            # Durumu hala 'ACTIVE' kalır
            return
        
        elif current_stage == 2 and profit_percentage >= 5.0:  # 2. aşama için %5 hedef
            # 2. aşama tamamlandı - Challenge fonlandı
            challenge.status = 'FUNDED'  # COMPLETED yerine FUNDED
            challenge.completion_date = timezone.now().date()
            challenge.funding_date = timezone.now().date()  # Fonlama tarihi eklendi
            # Varsayılan kar payı yüzdesi
            if not challenge.profit_share_percentage:
                challenge.profit_share_percentage = 80.0
            challenge.save()
            return
    
    elif stage_count == 3:
        # Üç aşamalı challenge
        current_stage = getattr(challenge, 'current_stage', 1)
        
        if current_stage == 1 and profit_percentage >= 5.0:  # Her aşama için %5
            # 1. aşama tamamlandı
            challenge.current_stage = 2
            challenge.stage1_completion_date = timezone.now().date()
            challenge.save()
            return
        
        elif current_stage == 2 and profit_percentage >= 5.0:
            # 2. aşama tamamlandı
            challenge.current_stage = 3
            challenge.stage2_completion_date = timezone.now().date()
            challenge.save()
            return
        
        elif current_stage == 3 and profit_percentage >= 5.0:
            # 3. aşama tamamlandı - Challenge fonlandı
            challenge.status = 'FUNDED'  # COMPLETED yerine FUNDED
            challenge.completion_date = timezone.now().date()
            challenge.funding_date = timezone.now().date()  # Fonlama tarihi eklendi
            # Varsayılan kar payı yüzdesi
            if not challenge.profit_share_percentage:
                challenge.profit_share_percentage = 80.0
            challenge.save()
            return
    
    # Eğer buraya kadar geldiyse, durumu hala 'ACTIVE' olmalı
    if challenge.status != 'ACTIVE':
        challenge.status = 'ACTIVE'
        challenge.save()

@login_required
def request_withdrawal(request, challenge_id):
    challenge = get_object_or_404(UserChallenge, id=challenge_id, user=request.user, status='FUNDED')
    
    if request.method == 'POST':
        form = WithdrawalRequestForm(request.POST)
        if form.is_valid():
            withdrawal = form.save(commit=False)
            withdrawal.user = request.user
            withdrawal.challenge = challenge
            withdrawal.save()
            messages.success(request, 'Para çekme talebi başarıyla oluşturuldu!')
            return redirect('challenge_detail', challenge_id=challenge.id)
    else:
        form = WithdrawalRequestForm()
    
    context = {
        'form': form,
        'challenge': challenge,
    }
    return render(request, 'tracker/request_withdrawal.html', context)

@login_required
def trading_statistics(request):
    import json
    from datetime import timedelta
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncDate
    
    # Kullanıcının tüm tradelerini al
    trades = Trade.objects.filter(user=request.user)
    
    # Fonlanmış challenge'ları tanımla - İLK OLARAK TANIMLANMALI
    funded_challenges = UserChallenge.objects.filter(user=request.user, status='FUNDED')
    
    # Payout hesaplama
    total_payout = Decimal('0.00')
    for challenge in funded_challenges:
        total_payout += challenge.calculate_payout()
    
    # İstatistik hesapları
    total_trades = trades.count()
    winning_trades = trades.filter(profit_loss__gt=0).count()
    losing_trades = trades.filter(profit_loss__lt=0).count()
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = trades.filter(profit_loss__gt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    total_loss = trades.filter(profit_loss__lt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 and total_loss is not None else 0
    
    funded_trades = Trade.objects.filter(challenge__in=funded_challenges)
    funded_total_profit = funded_trades.filter(profit_loss__gt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    
    # En yaygın işlem yapılan semboller
    symbols = trades.values('symbol').annotate(count=Count('id')).order_by('-count')[:5]
    
    # İşlem geçmişi için tarih bazlı veriler
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_trades = trades.filter(
        entry_date__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('entry_date')
    ).values('date').annotate(
        daily_pl=Sum('profit_loss')
    ).order_by('date')
    
    # Grafik için tarih ve P/L dizilerini hazırla
    trade_dates = []
    daily_pl = []
    
    for day in daily_trades:
        trade_dates.append(day['date'].strftime('%d/%m/%Y'))
        daily_pl.append(float(day['daily_pl'] or 0.0))
    
    context = {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'total_loss': total_loss,
        'profit_factor': profit_factor,
        'funded_total_profit': funded_total_profit,
        'symbols': symbols,
        'trade_dates': json.dumps(trade_dates),
        'daily_pl': json.dumps(daily_pl),
        'total_payout': total_payout,  # Total payout'u context'e ekle
    }
    return render(request, 'tracker/trading_statistics.html', context)
    
    # Kullanıcının tüm tradelerini al
    trades = Trade.objects.filter(user=request.user)
    
    # İstatistik hesapları
    total_trades = trades.count()
    winning_trades = trades.filter(profit_loss__gt=0).count()
    losing_trades = trades.filter(profit_loss__lt=0).count()
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = trades.filter(profit_loss__gt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    total_loss = trades.filter(profit_loss__lt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    
    profit_factor = abs(total_profit / total_loss) if total_loss != 0 and total_loss is not None else 0
    
    # Sadece fonlanmış hesaplardan yapılan işlemlerden toplam kar
    funded_challenges = UserChallenge.objects.filter(user=request.user, status='FUNDED')
    funded_trades = Trade.objects.filter(challenge__in=funded_challenges)
    funded_total_profit = funded_trades.filter(profit_loss__gt=0).aggregate(Sum('profit_loss'))['profit_loss__sum'] or 0
    
    # En yaygın işlem yapılan semboller
    symbols = trades.values('symbol').annotate(count=Count('id')).order_by('-count')[:5]
    
    # İşlem geçmişi için tarih bazlı veriler
    # Son 30 günlük işlemleri gruplayarak alıyoruz
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_trades = trades.filter(
        entry_date__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('entry_date')
    ).values('date').annotate(
        daily_pl=Sum('profit_loss')
    ).order_by('date')
    
    # Grafik için tarih ve P/L dizilerini hazırla
    trade_dates = []
    daily_pl = []
    
    for day in daily_trades:
        trade_dates.append(day['date'].strftime('%d/%m/%Y'))
        # None değerleri 0.0 olarak işle
        daily_pl.append(float(day['daily_pl'] or 0.0))
    
    context = {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'total_loss': total_loss,
        'profit_factor': profit_factor,
        'funded_total_profit': funded_total_profit,
        'symbols': symbols,
        'trade_dates': json.dumps(trade_dates),
        'daily_pl': json.dumps(daily_pl),
    }
    return render(request, 'tracker/trading_statistics.html', context)

@login_required
def delete_challenge(request, challenge_id):
    challenge = get_object_or_404(UserChallenge, id=challenge_id, user=request.user)
    
    if request.method == 'POST':
        # Challenge'a bağlı işlemleri de sil
        Trade.objects.filter(challenge=challenge).delete()
        # Challenge'ı sil
        challenge.delete()
        messages.success(request, 'Challenge başarıyla silindi!')
        return redirect('dashboard')
    
    context = {
        'challenge': challenge
    }
    return render(request, 'tracker/delete_challenge_confirm.html', context)

@login_required
def trades_list(request):
    # Tüm challengeları al
    challenges = UserChallenge.objects.filter(user=request.user)
    
    # URL parametresinden challenge_id alın (filtre için)
    selected_challenge_id = request.GET.get('challenge_id')
    
    # Trade filtrelerini uygula
    if selected_challenge_id:
        trades = Trade.objects.filter(
            user=request.user,
            challenge_id=selected_challenge_id
        ).order_by('-entry_date')
    else:
        trades = Trade.objects.filter(
            user=request.user
        ).order_by('-entry_date')
    
    # Kar/zarar yüzdeleri hesaplama
    profit_percentage_by_challenge = {}
    for challenge in challenges:
        initial_balance = challenge.challenge_type.account_size
        current_balance = challenge.current_balance
        profit_percentage = ((current_balance - initial_balance) / initial_balance) * 100
        profit_percentage_by_challenge[challenge.id] = round(profit_percentage, 2)
    
    context = {
        'trades': trades,
        'challenges': challenges,
        'selected_challenge_id': int(selected_challenge_id) if selected_challenge_id else None,
        'profit_percentage_by_challenge': profit_percentage_by_challenge,
    }
    return render(request, 'tracker/trades_list.html', context)
    

@login_required
def update_trade(request, trade_id):
    trade = get_object_or_404(Trade, id=trade_id, user=request.user)
    challenge = trade.challenge
    
    # İşlemin eski kar/zarar değerini sakla
    old_profit_loss = trade.profit_loss
    
    if request.method == 'POST':
        form = TradeForm(request.POST, instance=trade)
        if form.is_valid():
            # İşlemi güncelle ama henüz kaydetme
            updated_trade = form.save(commit=False)
            
            # Başlangıç bakiye değerini al
            initial_balance = challenge.challenge_type.account_size
            
            # Kar/Zarar yüzdesi işlenmesi
            if updated_trade.profit_loss_percentage is not None:
                # Yüzdeyi ondalık sayıya çevir
                percentage_decimal = Decimal(str(float(updated_trade.profit_loss_percentage) / 100))
                
                # Kar/zarar tutarını hesapla
                updated_trade.profit_loss = initial_balance * percentage_decimal
            
            # İşlemi kaydet
            updated_trade.save()
            
            # Challenge bakiyesini güncelle
            # Önce eski kar/zarar değerini çıkar, sonra yeni değeri ekle
            challenge.current_balance = challenge.current_balance - old_profit_loss + updated_trade.profit_loss
            
            # En yüksek ve en düşük bakiyeyi güncelle
            if challenge.current_balance > challenge.highest_balance:
                challenge.highest_balance = challenge.current_balance
            if challenge.current_balance < challenge.lowest_balance:
                challenge.lowest_balance = challenge.current_balance
                
            challenge.save()
            
            messages.success(request, 'İşlem başarıyla güncellendi!')
            return redirect('challenge_detail', challenge_id=challenge.id)
    else:
        form = TradeForm(instance=trade)
    
    context = {
        'form': form,
        'trade': trade,
        'challenge': challenge,
        'is_update': True
    }
    
    return render(request, 'tracker/add_trade.html', context)

@login_required
def user_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil bilgileriniz başarıyla güncellendi!')
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Kullanıcının challengelarını ve işlemlerini say
    challenges_count = UserChallenge.objects.filter(user=request.user).count()
    trades_count = Trade.objects.filter(user=request.user).count()
    
    context = {
        'form': form,
        'challenges_count': challenges_count,
        'trades_count': trades_count
    }
    return render(request, 'tracker/user_profile.html', context)

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Önemli: Kullanıcının oturumu korunur
            messages.success(request, 'Şifreniz başarıyla değiştirildi!')
            return redirect('user_profile')
        else:
            messages.error(request, 'Lütfen aşağıdaki hataları düzeltin.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'tracker/change_password.html', {
        'form': form
    })
