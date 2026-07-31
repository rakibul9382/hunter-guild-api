from django.urls import path
from . import api_views
urlpatterns = [
    # When a client hits this, it kicks off the data flow
    path('tasks/', api_views.task_list, name='api-task-list'),
    path('signup/', api_views.api_signup, name='signup'),
    path('verify-otp/', api_views.otp_view, name='api-verify-otp'),
    path('resend-otp/', api_views.api_resend_otp, name='api-resend-otp'),
    path('login/', api_views.login_view, name='login'),
    path('admin-signup/', api_views.api_admin_signup, name='api-admin-signup'),
    path('dashboard/', api_views.api_dashboard, name='dashboard'),
    path('create-task/', api_views.api_create_task, name='task-creation'),
    path('task-submission/<int:assignment_id>/', api_views.api_submition_proof, name='task-submit'),
    path('accept-task/<int:task_id>/', api_views.api_accept_task, name='task-accept'),
    path('review-task/<int:assignment_id>/', api_views.api_review_task, name='review-task'),
    path('profile/me/', api_views.profile_api_view, name='profile-details'),
    path('leaderboard/', api_views.leaderboard_view, name='leaderboard-details'),
    path('notifications/', api_views.api_notification, name='notifications'),
    path('contract-history/', api_views.api_contract_history, name='contract-history'),
    path('profile/request-edit/', api_views.request_profile_edit_otp, name='request-edit-otp'),
    path('profile/profile-edit/', api_views.edit_profile_api, name='profile-edit'),
    path('admin/pending_review/', api_views.admin_pending_queue, name='admin_pending_queue'),
    path('test-email-task/', api_views.trigger_email_task, name='test_email_task'),
    path('task-status/<str:task_id>/', api_views.get_task_status, name='get_task_status'),

]
