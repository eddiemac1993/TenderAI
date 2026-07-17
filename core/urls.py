from django.urls import path

from .views import (
    AppUpdateView,
    MessageBoardView,
    MessageThreadCreateView,
    MessageThreadDetailView,
    OrganizationCreateView,
    OrganizationListView,
    SupportChatAdminListView,
    SupportChatDetailView,
    SupportChatStartView,
    SystemSettingsView,
    TeamUserCreateView,
    admin_reply_support_chat,
    ask_support_chat,
    mark_support_chat_status,
    open_project_folder,
    reply_message_thread,
    run_app_update,
)

app_name = 'core'

urlpatterns = [
    path('', SystemSettingsView.as_view(), name='settings'),
    path('open-project-folder/', open_project_folder, name='open_project_folder'),
    path('updates/', AppUpdateView.as_view(), name='app_update'),
    path('updates/run/', run_app_update, name='run_app_update'),
    path('organizations/', OrganizationListView.as_view(), name='organizations'),
    path('organizations/new/', OrganizationCreateView.as_view(), name='organization_create'),
    path('team/users/new/', TeamUserCreateView.as_view(), name='team_user_create'),
    path('messages/', MessageBoardView.as_view(), name='message_board'),
    path('messages/new/', MessageThreadCreateView.as_view(), name='message_thread_create'),
    path('messages/<int:pk>/', MessageThreadDetailView.as_view(), name='message_thread_detail'),
    path('messages/<int:pk>/reply/', reply_message_thread, name='message_thread_reply'),
    path('support/', SupportChatStartView.as_view(), name='support_chat'),
    path('support/admin/', SupportChatAdminListView.as_view(), name='support_chat_admin'),
    path('support/<int:pk>/', SupportChatDetailView.as_view(), name='support_chat_detail'),
    path('support/<int:pk>/ask/', ask_support_chat, name='ask_support_chat'),
    path('support/<int:pk>/status/<str:status>/', mark_support_chat_status, name='support_chat_status'),
    path('support/<int:pk>/admin-reply/', admin_reply_support_chat, name='support_chat_admin_reply'),
]
