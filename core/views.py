import os
import sys

from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import models
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import CreateView
from django.views.generic import ListView
from django.views.generic import TemplateView
from django.views.generic import UpdateView
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from .forms import MessageReplyForm, MessageThreadForm, OrganizationForm, PublicRegistrationForm, SupportChatAdminReplyForm, SupportChatQuestionForm, SupportChatStartForm, SystemSettingsForm, TeamUserCreateForm, TenderAILoginForm, UserAccessUpdateForm
from .models import MessagePost, MessageThread, Organization, SupportChatMessage, SupportChatSession, SystemSettings, UserProfile
from .support_ai import answer_support_question
from .tenancy import filter_queryset_for_user, user_can_manage_users, user_organization
from .update_service import get_update_status, run_safe_update


class SystemSettingsView(UpdateView):
    model = SystemSettings
    form_class = SystemSettingsForm
    template_name = 'core/settings.html'

    def get_object(self, queryset=None):
        return SystemSettings.load()

    def form_valid(self, form):
        messages.success(self.request, 'System settings updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class TenderAILoginView(LoginView):
    authentication_form = TenderAILoginForm
    template_name = 'registration/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = UserProfile.objects.filter(user=self.request.user).first()
        if profile and not profile.is_pro and not self.request.user.is_superuser:
            profile.active_session_key = self.request.session.session_key or ''
            profile.active_session_started_at = timezone.now()
            profile.save(update_fields=['active_session_key', 'active_session_started_at'])
        return response


def tenderai_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


class RegisterView(FormView):
    template_name = 'registration/register.html'
    form_class = PublicRegistrationForm
    success_url = reverse_lazy('dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=False)
        user.email = form.cleaned_data['email']
        user.save()
        requested_name = form.cleaned_data['organization_name'].strip()
        organization_name = requested_name
        if Organization.objects.filter(name__iexact=requested_name).exists():
            organization_name = f'{requested_name} ({user.username})'
        organization = Organization.objects.create(
            name=organization_name,
            contact_email=user.email,
            contact_phone=form.cleaned_data.get('phone', ''),
        )
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'organization': organization,
                'role': UserProfile.Role.ORG_ADMIN,
                'phone': form.cleaned_data.get('phone', ''),
                'is_pro': False,
                'full_access_until': None,
                'terms_accepted_at': timezone.now(),
            },
        )
        login(self.request, user)
        profile = user.profile
        profile.active_session_key = self.request.session.session_key or ''
        profile.active_session_started_at = timezone.now()
        profile.save(update_fields=['active_session_key', 'active_session_started_at'])
        messages.success(
            self.request,
            'Account created. You can use the dashboard and ZPPA scraping now. Admin must grant full access for companies, documents, and bid packs.',
        )
        return super().form_valid(form)


class TeamManagementRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return user_can_manage_users(self.request.user)


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class OrganizationListView(TeamManagementRequiredMixin, ListView):
    model = Organization
    template_name = 'core/organization_list.html'
    context_object_name = 'organizations'

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('members')
        if self.request.user.is_superuser:
            return queryset
        organization = user_organization(self.request.user)
        return queryset.filter(pk=organization.pk) if organization else queryset.none()


class OrganizationCreateView(TeamManagementRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'form.html'
    success_url = reverse_lazy('core:organizations')

    def test_func(self):
        return self.request.user.is_superuser


class TeamUserCreateView(TeamManagementRequiredMixin, FormView):
    template_name = 'core/team_user_form.html'
    form_class = TeamUserCreateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save(commit=False)
        user.email = form.cleaned_data.get('email', '')
        user.save()
        organization = form.cleaned_data.get('organization') or user_organization(self.request.user)
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'organization': organization,
                'role': form.cleaned_data['role'],
            },
        )
        messages.success(self.request, f'User {user.username} created.')
        return redirect('core:organizations')


def open_project_folder(request):
    if not settings.DEBUG:
        messages.warning(request, 'Opening the project folder is only available while running TenderAI locally.')
        return redirect(request.META.get('HTTP_REFERER') or 'dashboard')

    project_folder = settings.BASE_DIR
    try:
        if sys.platform.startswith('win'):
            os.startfile(project_folder)
        else:
            messages.warning(request, f'Project folder: {project_folder}')
            return redirect(request.META.get('HTTP_REFERER') or 'dashboard')
        messages.success(request, 'Project folder opened in File Explorer.')
    except OSError as exc:
        messages.error(request, f'Could not open project folder: {exc}')
    return redirect(request.META.get('HTTP_REFERER') or 'dashboard')


class AppUpdateView(TemplateView):
    template_name = 'core/app_update.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['update_status'] = get_update_status(force_fetch=True)
        return context


@require_POST
def run_app_update(request):
    success, output = run_safe_update()
    if success:
        messages.success(request, 'TenderAI update completed. If the page looks unchanged, restart the local server or reopen TenderAI.')
    else:
        messages.error(request, 'TenderAI update could not complete. See details below.')
    request.session['last_update_output'] = output[-6000:]
    return redirect('core:app_update')


class SupportChatStartView(FormView):
    template_name = 'core/support_chat_start.html'
    form_class = SupportChatStartForm

    def form_valid(self, form):
        session = SupportChatSession.objects.create(
            user_name=form.cleaned_data.get('user_name', ''),
            user_email=form.cleaned_data.get('user_email', ''),
            organization=user_organization(self.request.user) if self.request.user.is_authenticated else None,
        )
        create_support_exchange(session, form.cleaned_data['question'])
        self.request.session['support_chat_session_id'] = session.pk
        return redirect(session)


class SupportChatDetailView(DetailView):
    model = SupportChatSession
    template_name = 'core/support_chat_detail.html'
    context_object_name = 'chat_session'

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            session_id = self.request.session.get('support_chat_session_id')
            return super().get_queryset().filter(pk=session_id)
        return filter_queryset_for_user(super().get_queryset(), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['question_form'] = SupportChatQuestionForm()
        context['admin_reply_form'] = SupportChatAdminReplyForm(initial={'status': self.object.status})
        return context


@require_POST
def ask_support_chat(request, pk):
    queryset = filter_queryset_for_user(SupportChatSession.objects.all(), request.user) if request.user.is_authenticated else SupportChatSession.objects.filter(pk=request.session.get('support_chat_session_id'))
    session = get_object_or_404(queryset, pk=pk)
    form = SupportChatQuestionForm(request.POST)
    if form.is_valid():
        create_support_exchange(session, form.cleaned_data['question'])
        messages.success(request, 'TenderAI answered your question.')
    else:
        messages.error(request, 'Please type a question.')
    return redirect(session)


@require_POST
def mark_support_chat_status(request, pk, status):
    session = get_object_or_404(filter_queryset_for_user(SupportChatSession.objects.all(), request.user), pk=pk)
    if status in SupportChatSession.Status.values:
        session.status = status
        session.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Support chat status updated.')
    return redirect(session)


class SupportChatAdminListView(ListView):
    model = SupportChatSession
    template_name = 'core/support_chat_admin_list.html'
    context_object_name = 'chat_sessions'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('messages')
        queryset = filter_queryset_for_user(queryset, self.request.user)
        status = self.request.GET.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_options'] = SupportChatSession.Status.choices
        context['selected_status'] = self.request.GET.get('status', '').strip()
        return context


@require_POST
def admin_reply_support_chat(request, pk):
    session = get_object_or_404(filter_queryset_for_user(SupportChatSession.objects.all(), request.user), pk=pk)
    form = SupportChatAdminReplyForm(request.POST)
    if form.is_valid():
        SupportChatMessage.objects.create(
            session=session,
            sender=SupportChatMessage.Sender.ADMIN,
            message=form.cleaned_data['message'],
            confidence=100,
        )
        session.status = form.cleaned_data['status']
        session.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Admin clarification saved.')
    else:
        messages.error(request, 'Please enter a clarification.')
    return redirect(session)


def create_support_exchange(session, question):
    SupportChatMessage.objects.create(
        session=session,
        sender=SupportChatMessage.Sender.USER,
        message=question,
        confidence=100,
    )
    answer, confidence = answer_support_question(question)
    SupportChatMessage.objects.create(
        session=session,
        sender=SupportChatMessage.Sender.AI,
        message=answer,
        confidence=confidence,
    )
    if confidence < 50 and session.status == SupportChatSession.Status.OPEN:
        session.status = SupportChatSession.Status.NEEDS_ADMIN
    session.save(update_fields=['status', 'updated_at'])


def message_thread_queryset_for_user(user):
    queryset = MessageThread.objects.select_related('created_by', 'recipient', 'organization').prefetch_related('posts')
    if user.is_superuser:
        return queryset
    organization = user_organization(user)
    return queryset.filter(
        models.Q(visibility=MessageThread.Visibility.PUBLIC)
        | models.Q(created_by=user)
        | models.Q(recipient=user)
        | models.Q(organization=organization, visibility=MessageThread.Visibility.PUBLIC)
    ).distinct()


class MessageBoardView(LoginRequiredMixin, ListView):
    model = MessageThread
    template_name = 'core/message_board.html'
    context_object_name = 'threads'
    paginate_by = 20

    def get_queryset(self):
        queryset = message_thread_queryset_for_user(self.request.user)
        visibility = self.request.GET.get('visibility', '').strip()
        q = self.request.GET.get('q', '').strip()
        if visibility:
            queryset = queryset.filter(visibility=visibility)
        if q:
            queryset = queryset.filter(models.Q(subject__icontains=q) | models.Q(posts__body__icontains=q)).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['visibility_options'] = MessageThread.Visibility.choices
        context['selected_visibility'] = self.request.GET.get('visibility', '').strip()
        context['query'] = self.request.GET.get('q', '').strip()
        return context


class MessageThreadCreateView(LoginRequiredMixin, FormView):
    template_name = 'core/message_thread_form.html'
    form_class = MessageThreadForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        thread = form.save(commit=False)
        thread.created_by = self.request.user
        thread.organization = user_organization(self.request.user)
        if not self.request.user.is_superuser:
            thread.recipient = None
            thread.pinned = False
        thread.save()
        MessagePost.objects.create(
            thread=thread,
            author=self.request.user,
            body=form.cleaned_data['first_message'],
        )
        messages.success(self.request, 'Message posted.')
        return redirect(thread)


class MessageThreadDetailView(LoginRequiredMixin, DetailView):
    model = MessageThread
    template_name = 'core/message_thread_detail.html'
    context_object_name = 'thread'

    def get_queryset(self):
        return message_thread_queryset_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['reply_form'] = MessageReplyForm()
        return context


@require_POST
def reply_message_thread(request, pk):
    thread = get_object_or_404(message_thread_queryset_for_user(request.user), pk=pk)
    if thread.closed:
        messages.warning(request, 'This message thread is closed.')
        return redirect(thread)
    form = MessageReplyForm(request.POST)
    if form.is_valid():
        MessagePost.objects.create(thread=thread, author=request.user, body=form.cleaned_data['body'])
        thread.save(update_fields=['updated_at'])
        messages.success(request, 'Reply posted.')
    else:
        messages.error(request, 'Please type a reply.')
    return redirect(thread)


class SuperuserDashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = 'core/superuser_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for user in User.objects.filter(profile__isnull=True):
            UserProfile.objects.get_or_create(user=user)

        profiles = list(
            UserProfile.objects.select_related('user', 'organization')
            .annotate(
                message_posts_count=models.Count('user__message_posts', distinct=True),
                message_threads_count=models.Count('user__message_threads', distinct=True),
            )
            .order_by('-user__last_login', 'user__username')
        )
        for profile in profiles:
            profile.access_form = UserAccessUpdateForm(instance=profile)
        context['profiles'] = profiles
        context['total_users'] = len(profiles)
        context['active_users'] = sum(1 for profile in profiles if profile.user.is_active)
        context['pro_users'] = sum(1 for profile in profiles if profile.is_pro)
        context['limited_users'] = sum(1 for profile in profiles if not profile.has_full_access and not profile.user.is_superuser)
        context['recent_messages'] = MessageThread.objects.select_related('created_by', 'recipient').order_by('-updated_at')[:8]
        context['open_support_chats'] = SupportChatSession.objects.exclude(status=SupportChatSession.Status.CLOSED).count()
        return context


@require_POST
def update_user_access(request, pk):
    if not request.user.is_superuser:
        messages.error(request, 'Only the superuser can update access settings.')
        return redirect('dashboard')
    profile = get_object_or_404(UserProfile.objects.select_related('user'), pk=pk)
    form = UserAccessUpdateForm(request.POST, instance=profile)
    if form.is_valid():
        updated_profile = form.save(commit=False)
        if updated_profile.access_days and not updated_profile.access_granted_at:
            updated_profile.access_granted_at = timezone.now()
        if not updated_profile.access_days:
            updated_profile.access_granted_at = None
        updated_profile.save()
        messages.success(request, f'Access updated for {profile.user.username}.')
    else:
        messages.error(request, f'Could not update {profile.user.username}. Check the values and try again.')
    return redirect('core:superuser_dashboard')
