from django.urls import path
from . import views

urlpatterns = [
    path("", views.meeting_list),
    path("<int:meeting_id>/", views.meeting_detail),
    path("<int:meeting_id>/start/", views.start_meeting),       # 회의 시작 + 녹음 시작
    path("<int:meeting_id>/end/", views.end_meeting),           # 회의 종료 + 녹음 파일 저장
    path("<int:meeting_id>/minutes/", views.generate_minutes),  # 회의록 생성 (RunPod 연동)
]