from django.urls import path

from .views import CompleteOnboardingView, MeView

urlpatterns = [
    path('me/', MeView.as_view(), name='accounts_me'),
    path('complete-onboarding/', CompleteOnboardingView.as_view(), name='accounts_complete_onboarding'),
]
