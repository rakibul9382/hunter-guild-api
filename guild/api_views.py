from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.db.models import Case, When, IntegerField
from django.core.mail import send_mail
import random
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.utils import timezone
from django.db import IntegrityError, DatabaseError
import logging
from django.db import transaction
from .serializers import (
    TaskSerializer,
    TaskAssignmentSerializer,
    HunterSignupSerializer,
    OtpSerializer,
    AdminSignupSerializer,
    TaskCreationSerializer,
    TaskSubmissionProof,
    TaskReviewSerializer,
    ProfileSerializer,
    NotificationSerializer,
    ContractHistorySerializer,
    EditProfileSerializer
)
from .pagination import StandardResultsSetPagination
from .models import Task, TaskAssignment, HunterProfile, OTPRecord, User,Notification
from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_list(request):
    filter_priority = request.query_params.get('priority', '').strip()
    filter_category = request.query_params.get('category', '').strip()
    sort_by = request.query_params.get('sort', '').strip()

    open_bounties = Task.objects.filter(status="O").order_by('deadline')
    try:
        hunter_level = request.user.hunter_profile.level
        open_bounties = open_bounties.filter(required_level__lte=hunter_level)
    except ObjectDoesNotExist:
        pass

    if filter_category in ['INVESTIGATION', 'ELIMINATION', 'RESCUE', 'PATROL', 'DELIVERY', 'SPECIAL']:
        open_bounties = open_bounties.filter(category=filter_category)

    if filter_priority in ['L', 'H', 'M', 'C']:
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
        if filter_priority in ['L', 'H', 'M', 'C']:
            open_bounties = open_bounties.order_by(
                '-priority_match', valid_sort_options[sort_by]
            )
        else:
            open_bounties = open_bounties.order_by(valid_sort_options[sort_by])

    # filter Active assignment
    active_assignment = TaskAssignment.objects.filter(
        hunter__user=request.user,
        status='A'
        ).select_related('task')
    pagination = StandardResultsSetPagination()
    paginated_Tasks = pagination.paginate_queryset(open_bounties, request)

    open_bounties_serializer = TaskSerializer(paginated_Tasks, many=True, context={'request': request})
    assignment_serializer = TaskAssignmentSerializer(active_assignment, many=True)

    paginated_data = pagination.get_paginated_response(open_bounties_serializer.data)

    return Response({
        'meta': paginated_data['meta'],
        'open_bounties': paginated_data['results'],
        'active_assignment': assignment_serializer.data,
        'filters': {
            'selected_priority': filter_priority,
            'selected_category': filter_category,
            'selected_sort': sort_by
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def api_signup(request):
    serializer = HunterSignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        HunterProfile.objects.get_or_create(user=user)
        otp = str(random.randint(100000, 999999))
        OTPRecord.objects.create(user=user, otp_code=otp)
        try:
            send_mail(
                subject='Verify your guild account',
                message=f'Your OTP is: {otp}',
                from_email='skrakibulislam9623@gmail.com',
                recipient_list=[user.email],
                fail_silently=False
            )
        except Exception:
            return Response({
                'error': 'Account created, but the email failed to send. Please click Resend OTP.',
                'user_id': user.id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': 'Signup successful. Please verify OTP.',
            'user_id': user.id  # The frontend needs this for step 2!
        }, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def otp_view(request):
    user_id = request.data.get('user_id')
    entered_otp = request.data.get('otp_code')
    if not user_id or not entered_otp:
        return Response({'error': 'Both user_id and otp_code are required.'},
                         status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    otp_record = OTPRecord.objects.filter(user=user).first()
    if otp_record and otp_record.otp_code == entered_otp:
        if otp_record.is_valid():
            user.is_active = True
            user.save()
            otp_record.delete()
            return Response({'message': 'Account verified successfully! You can now log in.'}, status=status.HTTP_200_OK)
        else:
            otp_record.delete()
            return Response(
                {"error": "This verification window has expired. Please request a new OTP."}, 
                status=status.HTTP_410_GONE
            )
    else:
        return Response({'error': 'Invalid OTP, try again.'},
                        status=status.HTTP_400_BAD_REQUEST
                        )


@api_view(['POST'])
@permission_classes([AllowAny])
def api_resend_otp(request):
    user_id = request.data.get('user_id')

    if not user_id:
        return Response({'error': 'User ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # 1. Check if they are already verified (no need to send an OTP if they are!)
    if user.is_active:
        return Response({'error': 'Account is already verified. Please log in.'}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Generate a new OTP code
    new_otp = str(random.randint(100000, 999999))

    # 3. Update the existing OTP record, or create it if it somehow doesn't exist
    otp_record, created = OTPRecord.objects.get_or_create(user=user)
    otp_record.otp_code = new_otp
    otp_record.save()

    # 4. Try sending the new email
    try:
        send_mail(
            'Resend: Verify your guild account',
            f'Your new OTP is: {new_otp}',
            'skrakibulislam9623@gmail.com',
            [user.email],
            fail_silently=False
        )
        return Response({'message': 'A new OTP has been sent to your email.'}, status=status.HTTP_200_OK)

    except Exception:
        return Response({'error': 'Failed to resend the email. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Login Successful',
                'token': token.key,
                'user_id': user.id
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Account is not verified. Please verify your OTP.',
                'user_id': user.id
            }, status=status.HTTP_403_FORBIDDEN)
    else:
        return Response({
            'error': 'Incorrect Username or Password.'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def api_admin_signup(request):
    serializer = AdminSignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': f'New admin account{user.id} is created sucessfuly.',
            'admin_id': user.id
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_dashboard(request):
    user = request.user
    if not user.is_authenticated:
        return Response({
            'message': (
                'Welcome Traveler! Log in or sign up to view the '
                'Quest Board.'
            ),
            'public_features': ['View Top Hunters', 'Read Guild Rules']
        }, status=status.HTTP_200_OK)

    if user.is_staff:
        # return according to admin dash board requirment
        return Response({
            'message': f'Welcome back, Guild Master {user.username}.',
            'admin_features': [
                                'Create Tasks',
                                'Ban Hunters',
                                'View Guild Treasury'
                            ]
        }, status=status.HTTP_200_OK)

    # return according to hunter dash board requirment
    return Response({
        'message': f'Welcome, Hunter {user.username}. Get to work!',
        'hunter_features': ['View Available Tasks', 'Update Hunter Profile']
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def api_create_task(request):
    serializer = TaskCreationSerializer(data=request.data)
    if serializer.is_valid():
        task = serializer.save(created_by=request.user)
        return Response({
            'message': 'Task creation successful.',
            'task_id': task.id
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_submition_proof(request, assignment_id):
    try:
        hunter_profile = HunterProfile.objects.get(user=request.user)
    except HunterProfile.DoesNotExist:
        return Response({
                    'error': 'You do not have a Hunter profile set up.'
                }, status=status.HTTP_400_BAD_REQUEST)

    try:
        task_assignment = TaskAssignment.objects.get(id=assignment_id, hunter=hunter_profile)
    except TaskAssignment.DoesNotExist:
        return Response({
            'error': "You pass wrong assignment id or Hunter don't assigned by this task."
        }, status=status.HTTP_404_NOT_FOUND)

    if task_assignment.status in ['S', 'P']:
        return Response({
            'error': 'The Task Is already submitted or Approved'
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = TaskSubmissionProof(task_assignment, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save(status='S', submitted_at=timezone.now())
        return Response({
            'message': f'You successfuly submitted proof for {task_assignment.task.title}'
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_accept_task(request, task_id):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({
            'error': 'Invalid task id'
        }, status=status.HTTP_404_NOT_FOUND)

    if TaskAssignment.objects.filter(task=task).exists():
        return Response({
            'error': 'This task is already assigned to a Hunter.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        hunter_profile = HunterProfile.objects.get(user=request.user)
    except HunterProfile.DoesNotExist:
        return Response({
            'error': 'You do not have a Hunter profile set up.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        assignment = TaskAssignment.objects.create(
            task=task, 
            hunter=hunter_profile
        )
        
        return Response({
            'message': f'Task "{task.title}" is successfully assigned to you.',
            'assignment_id': assignment.id
        }, status=status.HTTP_201_CREATED)
    except IntegrityError as e:
        logger.error(f"Integrity error when assigning task {task_id}: {str(e)}")

        return Response({
            'error': 'Could not assign task due to a data conflict. It may have just been claimed.'
        }, status=status.HTTP_409_CONFLICT)
    except DatabaseError as e:
        logger.error(f"Database error when assigning task {task_id}: {str(e)}")
        
        # Send a standard 500 server error
        return Response({
            'error': 'An unexpected server error occurred. Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_review_task(request, assignment_id):
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id)
    except TaskAssignment.DoesNotExist:
        return Response({
            'error': 'You passed a wrong Assignment id.'
        }, status=status.HTTP_404_NOT_FOUND)

    if assignment.status == 'P':
        return Response({
            'message': f'Task: {assignment.task.title} Is already accepted.'
        }, status=status.HTTP_403_FORBIDDEN)

    decisions = request.data.get('status')
    admin_note = request.data.get('admin_notes')

    if decisions not in ['P', 'X']:
        return Response({
            'error': "Decision must be 'P' (Pass/Approve) or 'X' (Fail/Reject)."
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        with transaction.atomic():
            serializer = TaskReviewSerializer(assignment, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                hunter_profile = assignment.hunter

                if decisions == 'P':
                    hunter_profile.total_completed_contract += 1
                    task_level = assignment.task.required_level
                    xp_earned = 20 * task_level
                    hunter_profile.experience_points += xp_earned
                    notification_text = f"Your proof for '{assignment.task.title}' was APPROVED! Earned {xp_earned} XP."

                    level_ups = 0
                    while hunter_profile.experience_points >= 100:
                        hunter_profile.level += 1
                        hunter_profile.experience_points -= 100
                        level_ups += 1

                    if level_ups > 0:
                        notification_text += f" 🎉 LEVEL UP! You are now Level {hunter_profile.level}!"
                    Notification.objects.create(
                            recipient=hunter_profile.user,
                            message=notification_text
                        )
                    hunter_profile.save()
                    return Response({
                        'message': 'Bounty Approved! Stats and XP updated.'
                    }, status=status.HTTP_200_OK)
                else:
                    hunter_profile.total_failed_contract += 1
                    Notification.objects.create(
                            recipient=hunter_profile.user,
                            message=f"Your proof for '{assignment.task.title}' was REJECTED. Guild Master Notes: {admin_note}"
                        )
                    hunter_profile.save()
                    return Response({
                        'message': f'Your task is not accepted reason-{admin_note}',
                    }, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Database error in api_review_task: {e}")
        return Response({
            'error': 'An unexpected server error occurred. Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_api_view(request):
    try:
        hunter_profie = HunterProfile.objects.get(user=request.user)
    except HunterProfile.DoesNotExist:
        return Response({
                    'error': 'You do not have a Hunter profile set up.'
                }, status=status.HTTP_400_BAD_REQUEST)
    profile_serializer = ProfileSerializer(hunter_profie)
    return Response({
        'profile': profile_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def leaderboard_view(request):
    special_profile = None
    if request.user.is_authenticated:
        try:
            special_profile = HunterProfile.objects.get(user=request.user)
        except HunterProfile.DoesNotExist:
            special_profile = None

    leaderboard = list(HunterProfile.objects.order_by('-level', '-experience_points')[:10])
    if special_profile:
        if special_profile not in leaderboard:
            leaderboard.append(special_profile)

    leaderboard_serializer = ProfileSerializer(leaderboard, many=True)
    response_data = {
        'leaderboard': leaderboard_serializer.data
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_notification(request):
    notifications = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
    if not notifications.exists():
        return Response({
            'message': 'You have no unread notifications.'
        }, status=status.HTTP_404_NOT_FOUND)

    notification_serializer = NotificationSerializer(notifications, many=True)
    return Response({
        'notifications': notification_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_contract_history(request):
    try:
        hunter = HunterProfile.objects.get(user=request.user)
    except HunterProfile.DoesNotExist:
        return Response({
            'message': ''
        }, status=status.HTTP_404_NOT_FOUND)

    contract_history = TaskAssignment.objects.filter(
        hunter=hunter, 
        status__in=['P', 'X']
    ).order_by('-id')
    
    choice = request.query_params.get('status')

    if choice:
        if choice not in ['P', 'X']:
            return Response({
                'message': 'You provide wrong Parameter. Use P or X'
            }, status=status.HTTP_400_BAD_REQUEST)
        contract_history = contract_history.filter(status=choice)

    pagination = StandardResultsSetPagination()
    paginated_contract_history = pagination.paginate_queryset(contract_history, request)
    
    contract_history_serializer = ContractHistorySerializer(
        paginated_contract_history, 
        many=True, 
        context={'request': request}
    )
    
    paginated_data = pagination.get_paginated_response(contract_history_serializer.data)
    
    return Response({
        'meta': paginated_data['meta'],
        'contract_history': paginated_data['results']
    }, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def edit_profile_api(request):
    try:
        profile = HunterProfile.objects.get(user=request.user)
    except HunterProfile.DoesNotExist:
        return Response({'message': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = EditProfileSerializer(profile, data=request.data, partial=True, context={'request':request})
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Profile updated successfully!',
            'updated_data': serializer.data
        }, status=status.HTTP_200_OK)
        
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_profile_edit_otp(request):
    otp = random.randint(10000, 999999)
    cache.set(f'otp_{request.user.id}', str(otp), timeout=300)
    send_mail(
        subject='otp for profile editing',
        message=f'Your otp is {otp}',
        from_email='skrakibulislam9623@gmail.com',
        recipient_list=[request.user.email],
        fail_silently=False
    )
    return Response({
        'message': 'OTP sent to your email successfully.'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_pending_queue(request):
    pending_assignments = TaskAssignment.objects.filter(status='S').select_related('task', 'hunter').order_by('-submitted_at')
    pagination = StandardResultsSetPagination()
    paginated_queue = pagination.paginate_queryset(pending_assignments, request)
    queue_serializer = TaskAssignmentSerializer(paginated_queue, many=True)
    paginated_data = pagination.get_paginated_response(queue_serializer.data)

    return Response({
        'meta': paginated_data['meta'],
        'pending_reviews': paginated_data['results']
    }, status=status.HTTP_200_OK)