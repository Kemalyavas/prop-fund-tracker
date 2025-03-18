from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_remove_trade_stop_loss_remove_trade_take_profit_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trade',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='trade',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]