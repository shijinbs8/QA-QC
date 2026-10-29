import os
import sys
from io import BytesIO
from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class Project(models.Model):
    name = models.CharField(max_length=200, help_text="Project title or site code (e.g., Burj Crown Tower B)")
    date_created = models.DateTimeField(default=timezone.now, help_text="Date when project was initialized")
    pm_name = models.CharField(max_length=150, verbose_name="Project Manager Name")
    mechanical_lead = models.CharField(max_length=150, verbose_name="Mechanical Lead Engineer")
    electrical_lead = models.CharField(max_length=150, verbose_name="Electrical Lead Engineer")
    hvac_lead = models.CharField(max_length=150, verbose_name="HVAC Lead Engineer")
    total_floors = models.PositiveIntegerField(default=1, help_text="Total number of floors/levels in the project")

    class Meta:
        ordering = ['-date_created']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return f"{self.name} (PM: {self.pm_name})"

    @property
    def total_inspections(self):
        return self.inspections.count()

    @property
    def pending_count(self):
        return self.inspections.filter(status='Pending Clearance').count()

    @property
    def clearance_count(self):
        return self.inspections.filter(status='Given Clearance').count()

    @property
    def open_ncr_count(self):
        return self.inspections.filter(status='Open NCR').count()

    @property
    def clearance_rate(self):
        total = self.total_inspections
        if total == 0:
            return 100
        return round((self.clearance_count / total) * 100, 1)


# ==============================================================================
# Phase 5: Dynamic Floor & Room Milestone Tracking & Matrix Engine Models
# ==============================================================================

class Floor(models.Model):
    FLOOR_TYPE_TYPICAL = 'Typical Floor'
    FLOOR_TYPE_BASEMENT = 'Basement'
    FLOOR_TYPE_PODIUM = 'Podium'
    FLOOR_TYPE_GROUND = 'Ground Floor'
    FLOOR_TYPE_MECHANICAL = 'Mechanical Floor'
    FLOOR_TYPE_ROOF = 'Roof'
    FLOOR_TYPE_CUSTOM = 'Custom'

    FLOOR_TYPE_CHOICES = [
        (FLOOR_TYPE_TYPICAL, 'Typical Floor'),
        (FLOOR_TYPE_BASEMENT, 'Basement'),
        (FLOOR_TYPE_PODIUM, 'Podium'),
        (FLOOR_TYPE_GROUND, 'Ground Floor'),
        (FLOOR_TYPE_MECHANICAL, 'Mechanical Floor'),
        (FLOOR_TYPE_ROOF, 'Roof'),
        (FLOOR_TYPE_CUSTOM, 'Custom'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='floors',
        help_text="Project site this floor belongs to"
    )
    floor_number = models.CharField(
        max_length=50,
        help_text="e.g. 'Floor 05', 'Basement 1', 'Ground Floor'"
    )
    floor_type = models.CharField(
        max_length=50,
        choices=FLOOR_TYPE_CHOICES,
        default=FLOOR_TYPE_TYPICAL,
        help_text="Floor classification"
    )
    apartment_count = models.PositiveIntegerField(
        default=0,
        help_text="Target number of apartments on this floor"
    )
    numbering_prefix = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text="Prefix used for apartment numbering (e.g. '05', '12', 'B1-')"
    )
    starting_number = models.PositiveIntegerField(
        default=1,
        help_text="Starting sequential index for apartments (usually 1)"
    )

    class Meta:
        ordering = ['floor_number']
        unique_together = ('project', 'floor_number')
        verbose_name = 'Floor'
        verbose_name_plural = 'Floors'

    def __str__(self):
        return f"{self.project.name} - {self.floor_number}"

    @property
    def total_rooms(self):
        return self.rooms.count()

    @property
    def apartments(self):
        return self.rooms.filter(room_type=Room.ROOM_TYPE_APARTMENT)

    @property
    def common_areas(self):
        return self.rooms.filter(room_type=Room.ROOM_TYPE_COMMON_AREA)

    @property
    def total_apartments(self):
        return self.apartments.count()

    @property
    def total_common_areas(self):
        return self.common_areas.count()


class Room(models.Model):
    ROOM_TYPE_APARTMENT = 'Apartment'
    ROOM_TYPE_COMMON_AREA = 'Common Area'

    ROOM_TYPE_CHOICES = [
        (ROOM_TYPE_APARTMENT, 'Apartment'),
        (ROOM_TYPE_COMMON_AREA, 'Common Area'),
    ]

    floor = models.ForeignKey(
        Floor,
        on_delete=models.CASCADE,
        related_name='rooms',
        help_text="Building level/floor"
    )
    room_number = models.CharField(
        max_length=100,
        help_text="e.g. '0501', 'Room 101', 'Apt 1402', 'Corridor A', 'Electrical Plant Room'"
    )
    room_type = models.CharField(
        max_length=50,
        choices=ROOM_TYPE_CHOICES,
        default=ROOM_TYPE_APARTMENT,
        help_text="Designation: Apartment or Common Area"
    )

    class Meta:
        ordering = ['room_number']
        unique_together = ('floor', 'room_number')
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'

    def __str__(self):
        return f"{self.floor.floor_number} &bull; {self.room_number}"

    @property
    def is_apartment(self):
        return self.room_type == self.ROOM_TYPE_APARTMENT

    @property
    def is_common_area(self):
        return self.room_type == self.ROOM_TYPE_COMMON_AREA

    @property
    def open_defects_count(self):
        """Returns total open defect inspections (Open NCR + Pending) for this room."""
        return self.defect_inspections.filter(
            models.Q(status='Open NCR') | models.Q(status='Pending Clearance')
        ).count()

    @property
    def total_defects_count(self):
        return self.defect_inspections.count()


class MilestoneDefinition(models.Model):
    CATEGORY_GENERAL = 'General'
    CATEGORY_CIVIL = 'Civil'
    CATEGORY_HVAC = 'HVAC'
    CATEGORY_PLUMBING = 'Plumbing'
    CATEGORY_ELECTRICAL = 'Electrical'
    CATEGORY_FIREFIGHTING = 'Firefighting'
    CATEGORY_FITOUT = 'Fit-Out'

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, 'MEP General'),
        (CATEGORY_CIVIL, 'Civil / Structural'),
        (CATEGORY_HVAC, 'HVAC'),
        (CATEGORY_PLUMBING, 'Plumbing'),
        (CATEGORY_ELECTRICAL, 'Electrical'),
        (CATEGORY_FIREFIGHTING, 'Firefighting'),
        (CATEGORY_FITOUT, 'Fit-Out & Finishes'),
    ]

    name = models.CharField(
        max_length=150,
        unique=True,
        help_text="e.g. 'Civil High Wall Closing', 'False Ceiling Framing', 'First Fix', 'Pressure Test'"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_GENERAL
    )
    display_order = models.IntegerField(default=0, help_text="Sequence order in matrix columns")

    class Meta:
        ordering = ['display_order', 'id']
        verbose_name = 'Milestone Definition'
        verbose_name_plural = 'Milestone Definitions'

    def __str__(self):
        return f"[{self.category}] {self.name}"


class RoomMilestoneStatus(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_IN_PROGRESS = 'In Progress'
    STATUS_DONE = 'Done'
    STATUS_NA = 'Not Applicable'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE, 'Done'),
        (STATUS_NA, 'Not Applicable'),
    ]

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    milestone = models.ForeignKey(
        MilestoneDefinition,
        on_delete=models.CASCADE,
        related_name='room_statuses'
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True, help_text="Clearance remarks or deficiency notes")

    class Meta:
        ordering = ['milestone__display_order', 'milestone__id']
        constraints = [
            models.UniqueConstraint(fields=['room', 'milestone'], name='unique_room_milestone')
        ]
        verbose_name = 'Room Milestone Status'
        verbose_name_plural = 'Room Milestone Statuses'

    def __str__(self):
        return f"{self.room} &bull; {self.milestone.name}: {self.status}"

    @property
    def badge_class(self):
        if self.status == self.STATUS_DONE:
            return 'badge-milestone-done'
        elif self.status == self.STATUS_IN_PROGRESS:
            return 'badge-milestone-progress'
        elif self.status == self.STATUS_NA:
            return 'badge-milestone-na'
        return 'badge-milestone-pending'


# ==============================================================================
# Signal: Auto-create RoomMilestoneStatus on new Room creation
# ==============================================================================

@receiver(post_save, sender=Room)
def create_room_milestone_statuses(sender, instance, created, **kwargs):
    """Whenever a new Room is created, automatically create a RoomMilestoneStatus instance
    for every existing MilestoneDefinition in the database with status set to 'Pending'."""
    if created:
        definitions = MilestoneDefinition.objects.all()
        statuses = [
            RoomMilestoneStatus(
                room=instance,
                milestone=m,
                status=RoomMilestoneStatus.STATUS_PENDING
            )
            for m in definitions
        ]
        if statuses:
            RoomMilestoneStatus.objects.bulk_create(statuses, ignore_conflicts=True)


@receiver(post_save, sender=MilestoneDefinition)
def create_statuses_for_new_milestone(sender, instance, created, **kwargs):
    """Whenever a new MilestoneDefinition is created, automatically initialize RoomMilestoneStatus
    for every existing Room across all projects and floors with status set to 'Pending'."""
    if created:
        rooms = Room.objects.all()
        statuses = [
            RoomMilestoneStatus(
                room=r,
                milestone=instance,
                status=RoomMilestoneStatus.STATUS_PENDING
            )
            for r in rooms
        ]
        if statuses:
            RoomMilestoneStatus.objects.bulk_create(statuses, ignore_conflicts=True)


class DefectInspection(models.Model):
    DEPARTMENT_HVAC = 'HVAC'
    DEPARTMENT_PLUMBING = 'Plumbing'
    DEPARTMENT_ELECTRICAL = 'Electrical'
    DEPARTMENT_FIREFIGHTING = 'Firefighting'

    DEPARTMENT_CHOICES = [
        (DEPARTMENT_HVAC, 'HVAC'),
        (DEPARTMENT_PLUMBING, 'Plumbing'),
        (DEPARTMENT_ELECTRICAL, 'Electrical'),
        (DEPARTMENT_FIREFIGHTING, 'Firefighting'),
    ]

    STATUS_PENDING = 'Pending Clearance'
    STATUS_CLEARED = 'Given Clearance'
    STATUS_NCR = 'Open NCR'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Clearance'),
        (STATUS_CLEARED, 'Given Clearance'),
        (STATUS_NCR, 'Open NCR'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='inspections',
        help_text="Target project site"
    )
    floor = models.ForeignKey(
        Floor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='defect_inspections',
        help_text="Dynamic Floor model reference"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='defect_inspections',
        help_text="Dynamic Room model reference"
    )
    department = models.CharField(
        max_length=50,
        choices=DEPARTMENT_CHOICES,
        default=DEPARTMENT_HVAC,
        help_text="MEP Engineering Department"
    )
    floor_number = models.IntegerField(
        default=1,
        help_text="Floor/Level number (legacy fallback, e.g. 1, 14, -1)"
    )
    apartment_number = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Apartment, unit, or MEP service corridor zone"
    )
    faults_description = models.TextField(
        help_text="Detailed description of QA/QC defect, non-conformance, or clearance notes"
    )
    date_recorded = models.DateTimeField(
        default=timezone.now,
        help_text="Inspection timestamp"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Current QA/QC inspection clearance status"
    )
    original_image = models.ImageField(
        upload_to='defects/original/%Y/%m/',
        blank=True,
        null=True,
        help_text="Unannotated site inspection photo or drawing slice"
    )
    annotated_image = models.ImageField(
        upload_to='defects/annotated/%Y/%m/',
        blank=True,
        null=True,
        help_text="Annotated site photo showing highlighted defect / marked zones"
    )
    overlay_positions = models.JSONField(
        default=list,
        blank=True,
        help_text="Pin & bounding box overlay coordinate metadata, e.g. [{'x': 45, 'y': 30, 'label': 'Leak', 'severity': 'High'}]"
    )

    class Meta:
        ordering = ['-date_recorded']
        verbose_name = 'Defect Inspection'
        verbose_name_plural = 'Defect Inspections'

    def __str__(self):
        unit_str = f" - Unit {self.apartment_number}" if self.apartment_number else ""
        return f"[{self.department}] {self.project.name} (Fl. {self.floor_number}{unit_str}) - {self.status}"

    @property
    def status_badge_class(self):
        if self.status == self.STATUS_CLEARED:
            return 'badge-cleared'
        elif self.status == self.STATUS_NCR:
            return 'badge-ncr'
        return 'badge-pending'

    @property
    def department_badge_class(self):
        mapping = {
            self.DEPARTMENT_HVAC: 'dept-hvac',
            self.DEPARTMENT_PLUMBING: 'dept-plumbing',
            self.DEPARTMENT_ELECTRICAL: 'dept-electrical',
            self.DEPARTMENT_FIREFIGHTING: 'dept-firefighting',
        }
        return mapping.get(self.department, 'dept-default')

    @property
    def overlay_count(self):
        if isinstance(self.overlay_positions, list):
            return len(self.overlay_positions)
        elif isinstance(self.overlay_positions, dict):
            return len(self.overlay_positions)
        return 0

    def save(self, *args, **kwargs):
        # Auto-optimize defect inspection photos to lightweight WebP before writing to storage
        if self.original_image and getattr(self.original_image, '_committed', True) is False:
            self.original_image = optimize_uploaded_image(self.original_image)
        if self.annotated_image and getattr(self.annotated_image, '_committed', True) is False:
            self.annotated_image = optimize_uploaded_image(self.annotated_image)
        super().save(*args, **kwargs)


def optimize_uploaded_image(image_field, max_dimension=1920, quality=82):
    """
    Compresses and converts raw mobile construction photos into optimized WebP format.
    Reduces 8-15 MB phone images down to ~150-250 KB without visible loss of MEP defect details.
    Allows 10GB free storage on Cloudflare R2 to store ~50,000 photos safely.
    """
    if not image_field:
        return image_field

    filename = getattr(image_field, 'name', '')
    if not filename or filename.lower().endswith('.webp'):
        return image_field

    try:
        if not hasattr(image_field, 'file'):
            return image_field

        image_field.file.seek(0)
        img = Image.open(image_field.file)

        # Convert to RGB mode
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Auto-orient based on smartphone camera EXIF tag
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Scale down if dimensions exceed max_dimension
        if max(img.width, img.height) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format='WEBP', quality=quality, method=6)
        output.seek(0)

        base_name = os.path.splitext(os.path.basename(filename))[0]
        new_filename = f"{base_name}.webp"

        return InMemoryUploadedFile(
            file=output,
            field_name='ImageField',
            name=new_filename,
            content_type='image/webp',
            size=len(output.getvalue()),
            charset=None
        )
    except Exception:
        # Fallback cleanly to original file if processing fails on unusual format
        return image_field

