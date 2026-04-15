from django.shortcuts import render
from django.views.generic import TemplateView

def home_view(request):
    return render(request, 'index.html')

def privacy_view(request):
    return render(request, 'policy.html', {'title': 'Privacy Policy', 'content': 'privacy'})

def terms_view(request):
    return render(request, 'policy.html', {'title': 'Terms and Conditions', 'content': 'terms'})

def refund_view(request):
    return render(request, 'policy.html', {'title': 'Refund and Cancellation Policy', 'content': 'refund'})
