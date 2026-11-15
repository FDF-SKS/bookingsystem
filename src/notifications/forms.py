from django import forms

from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ['notify_bookings', 'notify_tasks', 'notify_upcoming']
        widgets = {
            'notify_bookings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_tasks': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_upcoming': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
