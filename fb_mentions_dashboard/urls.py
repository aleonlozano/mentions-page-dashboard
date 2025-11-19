from django.contrib import admin
from django.urls import path
from mentions import views as mentions_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", mentions_views.dashboard, name="dashboard"),
    path("api/mentions/", mentions_views.mentions_api, name="mentions_api"),
    path("connect-instagram/", mentions_views.connect_instagram, name="connect_instagram"),
    path("instagram/callback/", mentions_views.instagram_callback, name="instagram_callback"),
    path("disconnect-instagram/", mentions_views.disconnect_instagram, name="disconnect_instagram"),
]
