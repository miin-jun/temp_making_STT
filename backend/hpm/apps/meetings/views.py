from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Meeting
from .serializers import MeetingSerializer


@api_view(["GET"])
def meeting_list(request):
    meetings = Meeting.objects.all().order_by("-meeting_at")
    serializer = MeetingSerializer(meetings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def meeting_detail(request, meeting_id):
    meeting = Meeting.objects.get(meeting_id=meeting_id)
    serializer = MeetingSerializer(meeting)
    return Response(serializer.data)