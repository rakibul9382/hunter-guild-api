from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
# Create your models here.


""" id, password, last_login,
    " is_superuser, username, first_name, last_name,
    email, is_staff, is_active, and date_joined. """


class User(AbstractUser):
    phone_number = PhoneNumberField(
        region="IN",
        null=True,
        blank=True,
        unique=True
    )
    profile_image = models.ImageField(
        upload_to='profile_pic/',
        blank=True,
        null=True
    )


class HunterProfile(models.Model):
    AVAIL_STATUS = [
        ('AV', 'AVAILABLE'),
        ('B', 'BUSY'),
        ('I', 'INACTIVE'),
    ]
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='hunter_profile'
      )
    level = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    experience_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    total_completed_contract = models.IntegerField(default=0)
    total_failed_contract = models.IntegerField(default=0)
    availability_status = models.CharField(
      max_length=2,
      choices=AVAIL_STATUS,
      default='AV'
    )
    rating = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    location = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def success_rate(self):
        total_contract = (
            self.total_completed_contract + self.total_failed_contract
        )
        if total_contract == 0:
            return 0
        return (self.total_completed_contract / total_contract)*100

    def __str__(self):
        return f"{self.user.username}"


class Task(models.Model):
    PRIORITY = [
        ('L', 'LOW'),
        ('M', 'MEDIUM'),
        ('H', 'HIGH'),
        ('C', 'CRITICAL'),
    ]
    STATUS = [
        ('O', 'OPEN'),
        ('A', 'ASSIGNED'),
        ('C', 'COMPLETE'),
        ('X', 'CANCELLED')
    ]
    CATEGORY = [
        ('GENERAL', 'General'),
        ('INVESTIGATION', 'Investigation'),
        ('ELIMINATION', 'Elimination'),
        ('RESCUE', 'Rescue'),
        ('PATROL', 'Patrol'),
        ('DELIVERY', 'Delivery'),
        ('SPECIAL', 'Special'),
    ]
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(
        max_length=15,
        choices=CATEGORY,
        default='GENERAL'
    )
    priority = models.CharField(max_length=1, choices=PRIORITY, default='M')
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    required_level = models.IntegerField(validators=[MinValueValidator(0)])
    deadline = models.DateTimeField()
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        default='O',
        db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tasks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class TaskAssignment(models.Model):
    STATUS = [
        ('A', 'ASSIGNED'),
        ('S', 'SUBMITTED'),
        ('P', 'APPROVED'),
        ('X', 'REJECTED'),
    ]
    task = models.ForeignKey(
        'Task',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    hunter = models.ForeignKey(
        'HunterProfile',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        default='A',
        db_index=True
    )
    admin_notes = models.TextField(blank=True, null=True)
    completion_proof = models.FileField(
        upload_to='com_proof/',
        blank=True,
        null=True
    )

    def __str__(self):
        return (
            f"{self.task.title} assigned to {self.hunter.user.username} "
            f"and status: {self.status}"
        )

    def clean(self):
        super().clean()
        if self.pk is None and self.task.status != 'O':
            raise ValidationError('Task must be open ')

        current_start = self.assigned_at or timezone.now()
        if self.submitted_at:
            if self.submitted_at < current_start:
                raise ValidationError({
                    'submitted_at': "Submitted date must be after Assigned date."
                })
        if self.task.required_level > self.hunter.level:
            raise ValidationError("Hunter level is less than Task required level")

        if self.submitted_at and self.task.deadline:
            if self.submitted_at > self.task.deadline:
                raise ValidationError("task must be submitted with in deadline")

        if self.pk is None:
            if self.task.deadline < timezone.now():
                raise ValidationError("You cannot assigned task after deadline")

        # Logic: If proof exists, status just shouldn't be 'A' (Assigned)
        # UNLESS we are in the middle of saving it from the hunter view.
        if self.completion_proof and self.status == 'A':
            # We check if this is a hunter submission by seeing if proof is NEW
            raise ValidationError("Please ensure status is set to 'S' when submitting proof.")

        if self.status in ['S', 'P'] and not self.completion_proof:
            raise ValidationError("Completion proof is required for Submitted or Approved status.")


    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)

            if is_new:
                self.task.status = 'A'
            else:
                if self.status in ['A', 'S']:
                    self.task.status = 'A'
                elif self.status == 'P':
                    self.task.status = 'C'
                elif self.status == 'X':
                    self.task.status = 'O'
            self.task.save(update_fields=['status'])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['task'],
                condition=~Q(status='X'),
                name='unique_active_assignment_per_task',
            )
        ]


class Payment(models.Model):
    STATUS = [
        ('P', 'PENDING'),
        ('S', 'SETTLED'),  # S for satteled/ success
        ('F', 'FAILED'),
    ]
    PAYMENT_METHOD = [
        ('UPI', 'Upi'),
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('WALLET', 'Wallet'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]
    assignment = models.OneToOneField(
        'TaskAssignment',
        on_delete=models.PROTECT,
        related_name='payment_details'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=1,
        choices=STATUS,
        default='P',
        db_index=True
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD,
        default='UPI'
    )
    payment_date = models.DateTimeField(blank=True, null=True)
    transaction_reference = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.assignment.status != "P" and self.status == 'S':
            raise ValidationError({
                'status': "Payment cannot be 'SETTLED' because the task is not completed yet."
            })

        if self.pk:
            original_instance = type(self).objects.get(pk=self.pk)
            if original_instance.amount != self.amount and original_instance.status == 'S':
                raise ValidationError({
                    'amount': "The amount cannot be changed once the status is 'Settled'."
                })

    def __str__(self):
        return (
            f"payment is {self.status} "
            f"for task {self.assignment.task.title}"
        )


class AuditLog(models.Model):
    ACTION = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('PAYMENT_SUCCESS', 'Payment Success'),
        ('PAYMENT_FAILED', 'Payment Failed'),
    ]
    user = models.ForeignKey(
        'User',
        null=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=16, choices=ACTION)
    """ model_name = models.CharField(max_length=100)
    object_id = models.IntegerField() """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=250)
    content_object = GenericForeignKey('content_type', 'object_id')
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)
    extra_data = models.JSONField(blank=True, null=True)

    def __str__(self):
        username = self.user.username if self.user else 'System'
        return (
            f"{username} performed {self.action} on "
            f"{self.content_type}(object_id: {self.object_id})"
        )

    class Meta:
        indexes = [
            models.Index(
                fields=['content_type', 'object_id'],
                name='content_obj_id_idx'
            ),
            models.Index(fields=['timestamp',], name='timestamp_idx'),
        ]
        ordering = ['-timestamp']


class OTPRecord(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"otp for {self.user.username}"

    def is_valid(self):
        # For testing: OTP expires immediately
        expire_time = self.created_at + timedelta(seconds=55)
        return timezone.now() < expire_time


class Notification(models.Model):
    recipient = models.ForeignKey('User', on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message[:20]}"