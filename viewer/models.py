import os
import uuid
from django.db import models

class Drawing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='drawings/%Y/%m/%d/')
    file_type = models.CharField(max_length=10, choices=[
        ('pdf', 'PDF Document'),
        ('dxf', 'AutoCAD DXF'),
        ('dwg', 'AutoCAD DWG'),
    ])
    file_size = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Processing status
    status = models.CharField(max_length=20, default='ready', choices=[
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ])
    error_message = models.TextField(blank=True, default='')
    
    # Scale & Units
    scale_ratio = models.FloatField(default=1.0) # 1 drawing unit in mm
    scale_unit = models.CharField(max_length=10, default='mm')
    is_calibrated = models.BooleanField(default=False)
    calibration_dimension = models.FloatField(null=True, blank=True)
    
    # Multi-sheet
    num_pages = models.IntegerField(default=1)
    current_page = models.IntegerField(default=1)
    
    # Parsed structural information
    layers_data = models.JSONField(default=list, blank=True)
    components_data = models.JSONField(default=list, blank=True)
    geometry_data = models.JSONField(default=dict, blank=True)
    legends_data = models.JSONField(default=list, blank=True)
    intelligence_data = models.JSONField(default=dict, blank=True)
    
    # 3D Capability & Honest Disclaimers
    is_3d_capable = models.BooleanField(default=False)
    disclaimer_3d = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.title} ({self.file_type.upper()})"

    @property
    def file_extension(self):
        return os.path.splitext(self.file.name)[1].lower().replace('.', '')
