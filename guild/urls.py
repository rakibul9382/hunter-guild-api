from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Custom Signup
    path('signup/', views.signup_view, name='signup'),

    # Built-in Auth (uses your templates/guild/registration/ folders)
    path('login/', auth_views.LoginView.as_view(template_name='guild/registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboards (Placeholders for now)
    path('dashboard/', views.dashboard, name='dashboard'),
    path('verify/', views.verify_otp, name='verify_otp'),
    path('bounty/create', views.create_bounty_task, name='create_bounty_task'),
    path('bounty/success', views.task_success, name='task_success_url'),
    path('bounty/submit/<int:assignment_id>/', views.submit_task_proof, name='submit_task_proof'),
    path('bounties/', views.task_list, name='task_list'),
    path('bounties/<int:task_id>/accept/', views.accept_task, name='accept_task'),
    path('dashboard/review/<int:assignment_id>/', views.review_task, name='task_review'),
    path('notification/read/<int:note_id>/', views.mark_notification_read, name='mark_note_read'),
]
