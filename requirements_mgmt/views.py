from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import RequirementRequest


@login_required
def requirement_list(request):
    role = request.user.role
    if role == 'HEAD_CLERK':
        requests = RequirementRequest.objects.filter(raised_by=request.user)
    else:
        requests = RequirementRequest.objects.all()
    return render(request, 'requirements_mgmt/requirement_list.html', {
        'requests': requests,
        'role': role,
        'active_nav': 'requirements',
    })