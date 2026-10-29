from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import Project, DefectInspection
import json


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username or engineering ID',
            'autocomplete': 'username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a secure password',
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
        }),
        label="Confirm Password"
    )
    role = forms.ChoiceField(
        choices=[
            ('MEP QA/QC Lead', 'MEP QA/QC Lead Engineer'),
            ('HVAC Inspector', 'HVAC QA/QC Inspector'),
            ('Electrical Inspector', 'Electrical QA/QC Inspector'),
            ('Plumbing Inspector', 'Plumbing & Drainage Inspector'),
            ('Firefighting Inspector', 'Fire Protection Inspector'),
            ('Project Manager', 'MEP Project Manager'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='MEP QA/QC Lead',
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., jsmith_mep'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'engineer@mepgroup.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Passwords do not match.')
        return cleaned_data


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'pm_name', 'mechanical_lead', 'electrical_lead', 'hvac_lead', 'total_floors']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Marina Horizon Tower B'}),
            'pm_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Eng. Tariq Al-Mansoor'}),
            'mechanical_lead': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Eng. David Miller'}),
            'electrical_lead': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Eng. Sarah Jenkins'}),
            'hvac_lead': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Eng. Ahmed Zaki'}),
            'total_floors': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'e.g. 45'}),
        }


from .models import Project, DefectInspection, Floor, Room
import base64
import uuid
import re
from django.core.files.base import ContentFile

class DefectInspectionForm(forms.ModelForm):
    overlay_positions_raw = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    original_image_base64 = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    annotated_image_base64 = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    class Meta:
        model = DefectInspection
        fields = [
            'project',
            'floor',
            'room',
            'department',
            'floor_number',
            'apartment_number',
            'faults_description',
            'status',
            'original_image',
            'annotated_image',
        ]
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select', 'id': 'id_project'}),
            'floor': forms.Select(attrs={'class': 'form-select', 'id': 'id_floor'}),
            'room': forms.Select(attrs={'class': 'form-select', 'id': 'id_room'}),
            'department': forms.Select(attrs={'class': 'form-select', 'id': 'id_department'}),
            'floor_number': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_floor_number', 'placeholder': 'e.g. 14'}),
            'apartment_number': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_apartment_number', 'placeholder': 'e.g. Apt 1404 / Corridor East'}),
            'faults_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Specify non-conformance details, applicable standards (ASHRAE/NFPA/DEWA), root cause, and remedial action required...'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'original_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*', 'capture': 'environment'}),
            'annotated_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['floor'].required = False
        self.fields['room'].required = False
        self.fields['floor'].empty_label = "-- Select Floor Level --"
        self.fields['room'].empty_label = "-- Select Room / Zone --"

        project_id = None
        if 'project' in self.data:
            try:
                project_id = int(self.data.get('project'))
            except (ValueError, TypeError):
                pass
        elif self.initial.get('project'):
            try:
                project_id = int(self.initial.get('project'))
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.project_id:
            project_id = self.instance.project_id

        if project_id:
            self.fields['floor'].queryset = Floor.objects.filter(project_id=project_id).order_by('floor_number')
        else:
            self.fields['floor'].queryset = Floor.objects.all().order_by('project', 'floor_number')

        floor_id = None
        if 'floor' in self.data:
            try:
                floor_id = int(self.data.get('floor'))
            except (ValueError, TypeError):
                pass
        elif self.initial.get('floor'):
            try:
                floor_id = int(self.initial.get('floor'))
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.floor_id:
            floor_id = self.instance.floor_id

        if floor_id:
            self.fields['room'].queryset = Room.objects.filter(floor_id=floor_id).order_by('room_number')
        else:
            self.fields['room'].queryset = Room.objects.all().order_by('room_number')

    def clean_overlay_positions_raw(self):
        raw = self.cleaned_data.get('overlay_positions_raw')
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_overlays = self.cleaned_data.get('overlay_positions_raw')
        if raw_overlays is not None:
            instance.overlay_positions = raw_overlays

        # Sync Floor and Room relationships
        if instance.room and not instance.floor:
            instance.floor = instance.room.floor

        if instance.floor:
            instance.project = instance.floor.project
            # Parse digits if floor_number text contains numeric floor
            m = re.search(r'-?\d+', instance.floor.floor_number)
            if m:
                try:
                    instance.floor_number = int(m.group(0))
                except ValueError:
                    pass

        if instance.room and not instance.apartment_number:
            instance.apartment_number = instance.room.room_number


        # Handle base64 original image from camera if standard file field is empty
        orig_b64 = self.cleaned_data.get('original_image_base64')
        if orig_b64 and not instance.original_image:
            try:
                format_str, img_str = orig_b64.split(';base64,')
                ext = format_str.split('/')[-1] or 'jpg'
                file_name = f"cam_orig_{uuid.uuid4().hex[:8]}.{ext}"
                data = ContentFile(base64.b64decode(img_str), name=file_name)
                instance.original_image.save(file_name, data, save=False)
            except Exception:
                pass

        # Handle base64 annotated image from canvas markup
        annot_b64 = self.cleaned_data.get('annotated_image_base64')
        if annot_b64:
            try:
                format_str, img_str = annot_b64.split(';base64,')
                ext = format_str.split('/')[-1] or 'jpg'
                file_name = f"markup_{uuid.uuid4().hex[:8]}.{ext}"
                data = ContentFile(base64.b64decode(img_str), name=file_name)
                instance.annotated_image.save(file_name, data, save=False)
            except Exception:
                pass

        if commit:
            instance.save()
        return instance


from .floor_generator import STANDARD_COMMON_AREAS

class FloorCreationForm(forms.Form):
    floor_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Floor 05, Basement 1, Podium 1',
            'id': 'id_floor_number',
            'required': True,
        }),
        label="Floor Name / Number"
    )
    floor_type = forms.ChoiceField(
        choices=Floor.FLOOR_TYPE_CHOICES,
        initial=Floor.FLOOR_TYPE_TYPICAL,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_floor_type',
        }),
        label="Floor Type"
    )
    apartment_count = forms.IntegerField(
        min_value=0,
        initial=16,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_apartment_count',
            'min': 0,
            'placeholder': 'e.g. 16 (or 0 for common-area only floor)',
        }),
        label="Number of Apartments"
    )
    starting_number = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_starting_number',
            'min': 1,
            'placeholder': '1',
        }),
        label="Starting Apartment Index"
    )
    numbering_prefix = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_numbering_prefix',
            'placeholder': 'Auto-detected (e.g. 05, B1-)',
        }),
        label="Apartment Number Prefix (Optional)",
        help_text="Leave blank to automatically detect from floor number/type"
    )
    common_areas = forms.MultipleChoiceField(
        choices=[(item, item) for item in STANDARD_COMMON_AREAS],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input common-area-check'
        }),
        label="Common Areas to Include"
    )
    custom_common_areas = forms.CharField(
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_common_areas',
            'placeholder': 'Comma-separated (e.g. Prayer Room, Fire Control)',
        }),
        label="Custom Common Areas (Optional)"
    )

    def clean_apartment_count(self):
        count = self.cleaned_data.get('apartment_count')
        if count is None or count < 0:
            raise forms.ValidationError("Apartment count must be a non-negative integer.")
        return count


class FloorEditForm(forms.Form):
    floor_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_edit_floor_number',
            'required': True,
        }),
        label="Floor Name / Number"
    )
    floor_type = forms.ChoiceField(
        choices=Floor.FLOOR_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_edit_floor_type',
        }),
        label="Floor Type"
    )
    apartment_count = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_edit_apartment_count',
            'min': 0,
        }),
        label="Target Number of Apartments"
    )
    starting_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_edit_starting_number',
            'min': 1,
        }),
        label="Starting Apartment Index"
    )
    numbering_prefix = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_edit_numbering_prefix',
        }),
        label="Number Prefix"
    )
    confirm_removal = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_confirm_removal',
        }),
        label="Confirm removal of excess empty apartments without defect history"
    )

    def clean_apartment_count(self):
        count = self.cleaned_data.get('apartment_count')
        if count is None or count < 0:
            raise forms.ValidationError("Apartment count must be a non-negative integer.")
        return count


class RoomManualForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'room_type']
        widgets = {
            'room_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 0517, Penthouse 1, Terrace Garden',
                'required': True,
            }),
            'room_type': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class CommonAreaAddForm(forms.Form):
    selected_common_areas = forms.MultipleChoiceField(
        choices=[(item, item) for item in STANDARD_COMMON_AREAS],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label="Select Common Areas"
    )
    custom_common_area = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Roof Terrace, Fire Command Room',
        }),
        label="Additional Custom Common Area"
    )


