# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.shortcuts import render
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'user_type', 'is_staff', 'date_joined')
    list_filter = ('user_type', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'profile_picture')}),
        ('Permissions', {
            'fields': ('user_type', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'user_type', 'is_staff', 'is_superuser'),
        }),
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    # Add custom URL for user detail view
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/details/', self.admin_site.admin_view(self.user_detail_view), 
            name='user-details'),
        ]
        return custom_urls + urls
    
    def user_detail_view(self, request, user_id):
        user = CustomUser.objects.get(id=user_id)
        context = {
            'user': user,
            'opts': self.model._meta,
            'title': f'User Details - {user.email}',
        }
        return render(request, 'admin/user_detail.html', context)

admin.site.register(CustomUser, CustomUserAdmin)