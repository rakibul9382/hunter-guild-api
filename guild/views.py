from django.shortcuts import render, redirect, get_object_or_404
from .forms import HunterSignupForm, OTPVerificationForm, TaskForm, TaskSubmissionForm
from django.contrib.auth.decorators import login_required
from .models import OTPRecord, HunterProfile, TaskAssignment, Task, Notification
import random
from django.core.mail import send_mail
from django.contrib.auth import get_user_model, logout
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, When, IntegerField


def signup_view(request):
    if request.method == 'POST':
        form = HunterSignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()
            HunterProfile.objects.get_or_create(user=user)
            otp = str(random.randint(100000, 999999))
            OTPRecord.objects.create(user=user, otp_code=otp)

            send_mail(
                'Verify your guild account',
                f'Your OTP is: {otp}',
                'skrakibulislam9623@gmail.com',
                [user.email],
                fail_silently=False
            )

            request.session['verification_user_id'] = user.id
            return redirect('verify_otp')
    else:
        form = HunterSignupForm()
    return render(request, 'guild/registration/signup.html', {'form': form})


User = get_user_model()


def verify_otp(request):
    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data.get('otp_code')
            user_id = request.session.get('verification_user_id')

            if user_id:
                user = User.objects.get(id=user_id)
                otp_record = OTPRecord.objects.filter(user=user).first()

                if otp_record and otp_record.otp_code == entered_otp:
                    if otp_record.is_valid():
                        user.is_active = True
                        user.save()
                        otp_record.delete()
                        del request.session['verification_user_id']
                        return redirect('login')
                    else:
                        otp_record.delete()
                        user.delete()
                        form.add_error('otp_code', 'OTP expired! Please register again.')
                else:
                    form.add_error('otp_code', 'Invalid otp try again')
    else:
        form = OTPVerificationForm()
    return render(request, 'guild/verify_otp.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    # This is where we will eventually use Pandas for analytics!
    if request.user.is_staff:
        pending_reviews = TaskAssignment.objects.filter(status='S').select_related('task', 'hunter__user')
        return render(request, 'guild/admin_dashboard.html', {'pending_reviews': pending_reviews})
    else:
        hunter = request.user.hunter_profile
        my_history = TaskAssignment.objects.filter(hunter=hunter).select_related('task').order_by('-assigned_at')
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False)
        return render(request, 'guild/hunter_dashboard.html', {'my_history': my_history, 'hunter': hunter, 'unread_notifications': unread_notifications})


@login_required
def create_bounty_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            new_task = form.save(commit=False)
            new_task.created_by = request.user
            new_task.save()
            return redirect('task_success_url')
    else:
        form = TaskForm()
    return render(request, 'tasks/create.html', {'form': form})


def task_success(request):
    return render(request, 'tasks/success.html')


@login_required
def submit_task_proof(request, assignment_id):
    assignment = get_object_or_404(
        TaskAssignment,
        id=assignment_id,
        hunter__user=request.user,
        status='A'
    )

    if request.method == "POST":
        form = TaskSubmissionForm(request.POST, request.FILES, instance= assignment)
        form.instance.status = 'S'
        form.instance.submitted_at = timezone.now()
        if form.is_valid():
            form.save()

            return redirect('task_list')
    else:
        form = TaskSubmissionForm(instance=assignment)

    return render(request, 'tasks/submit_proof.html',
                  {'form': form, 'assignment': assignment})


@login_required
def task_list(request):
    # 1. THE NOTICE BOARD: Grab all tasks that are 'O' (OPEN)
    # .order_by('deadline') puts the ones expiring soonest at the top!
    filter_priority = request.GET.get('priority', '').strip()
    filter_category = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', '').strip()

    open_bounties = Task.objects.filter(status='O').order_by('deadline')
    if filter_category in ['GENERAL', 'INVESTIGATION', 'ELIMINATION', 'RESCUE', 'PATROL', 'DELIVERY', 'SPECIAL']:
        open_bounties = open_bounties.filter(category=filter_category)

    if filter_priority in ['L', 'M', 'H', 'C']:
        open_bounties = open_bounties.annotate(
            priority_match=Case(
                When(priority=filter_priority, then=1),
                default=0,
                output_field=IntegerField()
            )
        ).order_by('-priority_match', 'deadline')
    valid_sort_options = {
        'reward_asc': 'reward_amount',
        'reward_desc': '-reward_amount'
    }
    if sort_by in valid_sort_options:
        if filter_priority in ['L', 'M', 'H', 'C']:
            open_bounties = open_bounties.order_by('-priority_match', valid_sort_options[sort_by])
        else:
            open_bounties = open_bounties.order_by(valid_sort_options[sort_by])

    # 2. MY ACTIVE CONTRACTS: Grab assignments for this specific hunter that are 'A' (ASSIGNED)
    my_active_assignments = TaskAssignment.objects.filter(
        hunter__user=request.user,
        status='A'
    ).select_related('task')  # MAGIC TRICK: This grabs the parent Task data in the same query so the HTML renders faster!
    context = {
        'open_bounties': open_bounties,
        'my_active_assignments': my_active_assignments,
        'selected_priority': filter_priority,
        'selected_category': filter_category,
        'selected_sort': sort_by,
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
@require_POST
def accept_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, status='O')
    hunter = request.user.hunter_profile

    try:
        new_assignment = TaskAssignment(task=task, hunter=hunter)
        print(new_assignment.task.status)
        new_assignment.save()
        print(new_assignment.task.status)
        messages.success(request, f"Bounty Accepted: {task.title}! Good luck, Hunter.")
    except ValidationError as e:
        if hasattr(e, 'message_dict'):
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"Guild Master says: {error}")
        else:
            for error in e.messages:
                messages.error(request, f"Guild Master says: {error}")
    return redirect('task_list')


@login_required
def review_task(request, assignment_id):
    # task_id = assignment_id  <-- You don't actually need this, you can just use assignment_id directly!

    if not request.user.is_staff:
        messages.error(request, "Only the Guild Master can review bounties.")
        return redirect('dashboard')

    assignment = get_object_or_404(TaskAssignment, id=assignment_id, status='S')

    if request.method == 'POST':
        admin_note = request.POST.get('admin_notes')
        decision = request.POST.get('decision')

        if decision in ['P', 'X']:
            try:
                with transaction.atomic():
                    assignment.status = decision
                    assignment.admin_notes = admin_note
                    assignment.save()

                    hunter_profile = assignment.hunter

                    if decision == 'P':
                        hunter_profile.total_completed_contract += 1
                        task_level = assignment.task.required_level
                        xp_earned = 20 * task_level
                        hunter_profile.experience_points += xp_earned

                        # FIX 1: Create the base message first!
                        notification_text = f"Your proof for '{assignment.task.title}' was APPROVED! Earned {xp_earned} XP."

                        if hunter_profile.experience_points >= 100:
                            hunter_profile.level += 1
                            hunter_profile.experience_points -= 100

                            # Add the level up text to the base message
                            notification_text += f" 🎉 LEVEL UP! You are now Level {hunter_profile.level}!"
                            messages.success(request, f"Hunter leveled up to {hunter_profile.level}!")

                        # FIX 2: Fixed spelling to 'recipient'
                        Notification.objects.create(
                            recipient=hunter_profile.user,
                            message=notification_text
                        )
                        messages.success(request, 'Bounty Approved! Stats and XP updated.')

                    elif decision == 'X':
                        # FIX 3: Changed -= to += 
                        hunter_profile.total_failed_contract += 1

                        Notification.objects.create(
                            recipient=hunter_profile.user, # Fixed spelling here too
                            message=f"Your proof for '{assignment.task.title}' was REJECTED. Guild Master Notes: {admin_note}"
                        )
                        messages.warning(request, "Bounty Rejected. Failed contract added to Hunter's record.")

                    hunter_profile.save()

            except Exception as e:
                # Pro-tip: It's helpful to print(e) here while testing so you know exactly why it failed!
                print(f"Database error: {e}") 
                messages.error(request, "A database error occurred. Canceled.")

            return redirect('dashboard')

    return render(request, 'guild/review_proof.html', {'assignment': assignment})


def mark_notification_read(request, note_id):
    note = get_object_or_404(Notification, id=note_id, recipient=request.user)
    note.is_read = True
    note.save()
    return redirect('dashboard')
