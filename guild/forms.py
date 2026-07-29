from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import User, HunterProfile, Task, TaskAssignment


class HunterSignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'phone_number', 'profile_image')

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
        return user


class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label='Verification Code',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 6 digit otp',
            'class': 'form-control',
            'autocomplete': 'one-time-code'
        })
    )


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'category', 'priority',
                  'reward_amount',
                  'required_level',
                  'deadline',
                  'status',
                  ]
        widgets = {
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.TextInput(attrs={'rows': 4, 'placeholder': 'Detailed intel here....'})
        }


class TaskSubmissionForm(forms.ModelForm):
    class Meta:
        model = TaskAssignment

        # We ONLY ask the Hunter for the proof. 
        # The View will handle the status change behind the scenes!
        fields = ['completion_proof']

        labels = {
            'completion_proof': 'Upload Completion Proof (Screenshots/Logs)',
        }

        widgets = {
            # Adding a clean CSS class so you can style the file upload button
            'completion_proof': forms.FileInput(attrs={'class': 'file-upload-btn'}),
        }

