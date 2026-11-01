from datetime import datetime, time

from django import forms
from django.core.exceptions import ValidationError

from .models import DepotBooking, DepotItem


class DepotItemForm(forms.ModelForm):
    class Meta:
        model = DepotItem
        fields = ['name', 'location', 'description', 'image', 'quantity', 'unit']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Navn på genstand'
            }),
            'location': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Beskrivelse'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Antal på lager'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enhed (f.eks. stk, liter, kg)',
                'value': 'stk'
            }),
        }


class DepotBookingForm(forms.ModelForm):
    start_date = forms.DateField(
        label='Startdato',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    start_time = forms.TimeField(
        label='Starttidspunkt',
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        }),
        required=False
    )
    end_date = forms.DateField(
        label='Slutdato',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_time = forms.TimeField(
        label='Sluttidspunkt',
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        }),
        required=False
    )

    class Meta:
        model = DepotBooking
        fields = ['item', 'team', 'team_contact', 'quantity', 'remarks']
        widgets = {
            'item': forms.Select(attrs={
                'class': 'form-control'
            }),
            'team': forms.Select(attrs={
                'class': 'form-control'
            }),
            'team_contact': forms.Select(attrs={
                'class': 'form-control'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Antal'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Booking bemærkninger'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate date/time fields for edit form
        if self.instance and self.instance.pk:
            self.fields['start_date'].initial = self.instance.start_date
            self.fields['start_time'].initial = self.instance.start_time
            self.fields['end_date'].initial = self.instance.end_date
            self.fields['end_time'].initial = self.instance.end_time

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate dates and times
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')
        end_date = cleaned_data.get('end_date')
        end_time = cleaned_data.get('end_time')
        
        if start_date and end_date:
            # Handle time fields - default to 00:00 if not provided
            if not start_time:
                start_time = time(0, 0)
            if not end_time:
                end_time = time(0, 0)
            
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)
            
            if start_datetime >= end_datetime:
                raise ValidationError("Sluttidspunkt skal være efter starttidspunkt")
        
        # Validate quantity against available inventory
        item = cleaned_data.get('item')
        quantity = cleaned_data.get('quantity')
        
        if item and quantity and start_date and end_date:
            if not start_time:
                start_time = time(0, 0)
            if not end_time:
                end_time = time(0, 0)
            
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)
            
            available = item.available_quantity(start_datetime, end_datetime)
            if quantity > available:
                raise ValidationError(
                    f"Anmodet antal ({quantity}) overstiger tilgængeligt antal ({available}) "
                    f"for den valgte periode."
                )
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Directly assign the date and time fields
        instance.start_date = self.cleaned_data.get('start_date')
        instance.start_time = self.cleaned_data.get('start_time') or time(0, 0)
        instance.end_date = self.cleaned_data.get('end_date')
        instance.end_time = self.cleaned_data.get('end_time') or time(0, 0)
        
        if commit:
            instance.save()
        return instance


