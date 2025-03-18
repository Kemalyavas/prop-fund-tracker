from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class FundingProvider(models.Model):
    """FTMO, FXify gibi fon sağlayıcı firmaları temsil eder"""
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='provider_logos/', blank=True, null=True)
    
    def __str__(self):
        return self.name

class ChallengeType(models.Model):
    """Her firmanın farklı challenge tipleri olabilir (ör: 10K, 25K, 100K vs.)"""
    provider = models.ForeignKey(FundingProvider, on_delete=models.CASCADE, related_name='challenge_types')
    name = models.CharField(max_length=100)  # Örn: "10K Challenge"
    account_size = models.DecimalField(max_digits=15, decimal_places=2)  # Örn: 10000.00
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Challenge ücreti
    max_daily_loss = models.DecimalField(max_digits=5, decimal_places=2, help_text="Yüzde olarak")  # Örn: 5.00 (%)
    max_total_loss = models.DecimalField(max_digits=5, decimal_places=2, help_text="Yüzde olarak")  # Örn: 10.00 (%)
    profit_target = models.DecimalField(max_digits=5, decimal_places=2, help_text="Yüzde olarak")  # Örn: 8.00 (%)
    duration_days = models.IntegerField(help_text="Challenge süresi (gün)")
    
    def __str__(self):
        return f"{self.provider.name} - {self.name}"

class UserChallenge(models.Model):
    """Kullanıcının başladığı fonları/challenge'ları temsil eder"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenges')
    challenge_type = models.ForeignKey(ChallengeType, on_delete=models.CASCADE)
    start_date = models.DateField(default=timezone.now)
    current_stage = models.IntegerField(default=1, help_text="Çok aşamalı challenge'larda mevcut aşama")
    stage1_completion_date = models.DateField(null=True, blank=True)
    stage2_completion_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True, help_text="Challenge'ın tamamlandığı tarih")
    failure_reason = models.CharField(max_length=255, null=True, blank=True, help_text="Challenge başarısız olma sebebi")
    
    def __str__(self):
        return f"{self.user.username} - {self.challenge_type.provider.name} {self.challenge_type.name}"
    
    def days_remaining(self):
        if self.status != 'ACTIVE':
            return 0
        elapsed = (timezone.now().date() - self.start_date).days
        return max(0, self.challenge_type.duration_days - elapsed)
    
    def profit_percentage(self):
        initial = self.challenge_type.account_size
        current = self.current_balance
        if initial == 0:
            return 0
        return ((current - initial) / initial) * 100
    
    # Bu property'i ekleyin (profit_percentage metodundan sonra):
    @property
    def target_balance(self):
        """Hedef bakiyeyi hesaplar"""
        initial = self.challenge_type.account_size
        profit_target_percent = self.challenge_type.profit_target
        # Örneğin %10 kar hedefi için: 25000 + (25000 * 10/100) = 27500
        return initial * (1 + (profit_target_percent / 100))
    
    # Opsiyonel: Kar hedefine ulaşma yüzdesini hesaplayan bir property
    @property
    def profit_percentage_of_target(self):
        """Kar hedefine ulaşma yüzdesini hesaplar"""
        initial = self.challenge_type.account_size
        current = self.current_balance
        target = self.target_balance
        
        if target == initial:  # Hedef kar 0 ise
            return 100.0
            
        current_profit = current - initial
        target_profit = target - initial
        
        if target_profit <= 0:
            return 0.0
            
        percentage = (current_profit / target_profit) * 100
        # En fazla %100 olabilir (hedefi aşsa bile)
        return min(100.0, max(0.0, percentage))
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Devam Ediyor'),
        ('COMPLETED', 'Başarıyla Tamamlandı'),
        ('FAILED', 'Başarısız'),
        ('FUNDED', 'Fonlandı'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Challenge'ın mevcut durumunu takip etmek için
    current_balance = models.DecimalField(max_digits=15, decimal_places=2)
    highest_balance = models.DecimalField(max_digits=15, decimal_places=2)
    lowest_balance = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Funded olduğunda kullanılacak
    funding_date = models.DateField(null=True, blank=True)
    profit_share_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.challenge_type.provider.name} {self.challenge_type.name}"
    
    def days_remaining(self):
        if self.status != 'ACTIVE':
            return 0
        elapsed = (timezone.now().date() - self.start_date).days
        return max(0, self.challenge_type.duration_days - elapsed)
    
    def profit_percentage(self):
        initial = self.challenge_type.account_size
        current = self.current_balance
        if initial == 0:
            return 0
        return ((current - initial) / initial) * 100
    
    def calculate_payout(self):
        """
        Fonlanmış challenge için payout miktarını hesaplar.
        Payout = Kar * Kar Payı Yüzdesi / 100
        """
        if self.status != 'FUNDED':
            return Decimal('0.00')
            
        # Başlangıç bakiyesi
        initial_balance = self.challenge_type.account_size
        
        # Şu anki kar miktarı - FONLANDIKTAN SONRA!
        current_profit = self.current_balance - initial_balance
        
        # Kar payı yüzdesi (varsayılan %80)
        profit_share_percentage = self.profit_share_percentage or Decimal('80.0')
        
        # Payout hesaplama
        payout = current_profit * (profit_share_percentage / Decimal('100.0'))
        
        return payout if payout > 0 else Decimal('0.00')

class Trade(models.Model):
    TRADE_RESULT_CHOICES = [
        ('TP', 'TP Oldum'),
        ('SL', 'Stop Oldum'),
        ('CUSTOM', 'Özel')
    ]
    
    # Önce model alanlarını tanımlayalım, sonra metodları
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades')
    challenge = models.ForeignKey(UserChallenge, on_delete=models.CASCADE, related_name='trades')
    
    symbol = models.CharField(max_length=20, verbose_name="Sembol")  
    
    TRADE_TYPES = [
        ('BUY', 'Alış'),
        ('SELL', 'Satış'),
    ]
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES, verbose_name="İşlem Tipi")
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Lot Büyüklüğü")
    
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, verbose_name="Giriş Fiyatı")
    exit_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True, verbose_name="Çıkış Fiyatı")
    
    entry_date = models.DateTimeField(verbose_name="Giriş Tarihi")
    exit_date = models.DateTimeField(null=True, blank=True, verbose_name="Çıkış Tarihi")
    
    trade_result = models.CharField(max_length=10, choices=TRADE_RESULT_CHOICES, verbose_name="İşlem Sonucu")
    custom_result = models.CharField(max_length=100, blank=True, null=True, verbose_name="Özel Sonuç")
    
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Kar/Zarar ($)")
    profit_loss_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Kar/Zarar Yüzdesi (%)")
    
    notes = models.TextField(blank=True, null=True, verbose_name="Notlar")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Şimdi metodları tanımlayalım
    def get_formatted_profit_loss_percentage(self):
        """Kar/zarar yüzdesini formatlı şekilde döndürür"""
        if self.profit_loss_percentage is None:
            return "0.00"
        return f"{float(self.profit_loss_percentage):.2f}"
        
    def get_formatted_profit_loss(self):
        """Kar/zarar tutarını formatlı şekilde döndürür"""
        if self.profit_loss is None:
            return "$0.00"
        
        symbol = "+" if self.profit_loss >= 0 else "-"
        return f"{symbol}${abs(self.profit_loss):.2f}"

class WithdrawalRequest(models.Model):
    """Funded hesaptan para çekme taleplerine ait bilgiler"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    challenge = models.ForeignKey(UserChallenge, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    request_date = models.DateField(default=timezone.now)
    
    STATUS_CHOICES = [
        ('PENDING', 'Beklemede'),
        ('APPROVED', 'Onaylandı'),
        ('PAID', 'Ödendi'),
        ('REJECTED', 'Reddedildi'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} TL - {self.status}"
    
    
    