from django.contrib import admin
from .models import Project, DefectInspection, Floor, Room, MilestoneDefinition, RoomMilestoneStatus


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 1


class RoomMilestoneStatusInline(admin.TabularInline):
    model = RoomMilestoneStatus
    extra = 0
    autocomplete_fields = ['milestone']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'pm_name', 'mechanical_lead', 'electrical_lead', 'hvac_lead', 'total_floors', 'date_created')
    search_fields = ('name', 'pm_name', 'mechanical_lead', 'electrical_lead', 'hvac_lead')
    list_filter = ('date_created',)
    inlines = [FloorInline]


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('floor_number', 'floor_type', 'project', 'total_apartments', 'total_common_areas', 'total_rooms')
    list_filter = ('floor_type', 'project')
    search_fields = ('floor_number', 'project__name')
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'floor', 'open_defects_count', 'total_defects_count')
    list_filter = ('room_type', 'floor__project', 'floor')
    search_fields = ('room_number', 'floor__floor_number', 'floor__project__name')
    inlines = [RoomMilestoneStatusInline]


@admin.register(MilestoneDefinition)
class MilestoneDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'display_order')
    list_filter = ('category',)
    search_fields = ('name',)
    list_editable = ('display_order', 'category')
    ordering = ('display_order', 'id')


@admin.register(RoomMilestoneStatus)
class RoomMilestoneStatusAdmin(admin.ModelAdmin):
    list_display = ('room', 'milestone', 'status', 'updated_at')
    list_filter = ('status', 'milestone__category', 'milestone', 'room__floor__project')
    search_fields = ('room__room_number', 'milestone__name', 'notes')
    list_editable = ('status',)


@admin.register(DefectInspection)
class DefectInspectionAdmin(admin.ModelAdmin):
    list_display = ('project', 'floor', 'room', 'department', 'floor_number', 'apartment_number', 'status', 'date_recorded')
    list_filter = ('department', 'status', 'project', 'floor')
    search_fields = ('faults_description', 'apartment_number', 'project__name', 'room__room_number')
    date_hierarchy = 'date_recorded'

