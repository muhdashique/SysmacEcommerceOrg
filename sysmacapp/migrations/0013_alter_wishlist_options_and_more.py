# Generated by Django 5.2.1 on 2025-07-12 05:25

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sysmacapp', '0012_product'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='wishlist',
            options={'ordering': ['-added_at'], 'verbose_name': 'Wishlist Item', 'verbose_name_plural': 'Wishlist Items'},
        ),
        migrations.AlterUniqueTogether(
            name='wishlist',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='wishlist',
            name='added_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Added Date'),
        ),
        migrations.AlterField(
            model_name='wishlist',
            name='api_product_code',
            field=models.CharField(blank=True, help_text='Product code from external API', max_length=100, null=True, verbose_name='API Product Code'),
        ),
        migrations.AlterField(
            model_name='wishlist',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wishlisted_by', to='sysmacapp.customproduct', verbose_name='Custom Product'),
        ),
        migrations.AlterField(
            model_name='wishlist',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wishlist_items', to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),
        migrations.AlterUniqueTogether(
            name='wishlist',
            unique_together={('user', 'api_product_code'), ('user', 'product')},
        ),
    ]
