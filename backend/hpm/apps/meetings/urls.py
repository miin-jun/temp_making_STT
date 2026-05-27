from django.urls import path
from . import views

urlpatterns = [
    path("", views.meeting_list),
    path("<int:meeting_id>/", views.meeting_detail),
]