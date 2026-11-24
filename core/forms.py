from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Booking, Category, Destination, Profile, Review


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProfileForm(forms.ModelForm):
    preferred_categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Profile
        fields = ["phone", "preferred_categories", "interests", "budget_level", "travel_style", "passport_expiry"]
        widgets = {"passport_expiry": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["destination", "package", "hotel", "start_date", "end_date", "travellers", "budget", "notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}),
                   "end_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["package"].required = False
        self.fields["hotel"].required = False
        self.fields["travellers"].min_value = 1

    def clean(self):
        data = super().clean()
        s, e, dest = data.get("start_date"), data.get("end_date"), data.get("destination")
        if s and s < date.today():
            self.add_error("start_date", "Choose a date from today onwards.")
        if s and e and e < s:
            self.add_error("end_date", "End date must be after the start date.")
        for key in ("package", "hotel"):
            obj = data.get(key)
            if obj and dest and obj.destination_id != dest.id:
                self.add_error(key, f"This {key} belongs to a different destination.")
        if data.get("travellers") is not None and data["travellers"] < 1:
            self.add_error("travellers", "At least one traveller is required.")
        return data


class PlannerForm(forms.Form):
    destination = forms.ModelChoiceField(queryset=Destination.objects.all())
    days = forms.IntegerField(min_value=1, max_value=14, initial=3)
    travellers = forms.IntegerField(min_value=1, max_value=20, initial=2)
    budget = forms.IntegerField(min_value=0, initial=25000, label="Total budget (₹)")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    interests = forms.CharField(required=False, max_length=200, help_text="e.g. boating, waterfalls, local food")


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "text"]
        widgets = {"rating": forms.NumberInput(attrs={"min": 1, "max": 5}), "text": forms.Textarea(attrs={"rows": 3})}
