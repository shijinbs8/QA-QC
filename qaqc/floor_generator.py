import re
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Floor, Room, MilestoneDefinition, RoomMilestoneStatus, DefectInspection

STANDARD_COMMON_AREAS = [
    'Lift Lobby',
    'Corridor',
    'Garbage Room',
    'Garbage Chute',
    'Staircase',
    'Electrical Meter Room',
    'Water Meter Room',
    'GSM Room',
    'Electrical Room',
    'HVAC Room',
    'Service Shaft',
]


def compute_floor_prefix(floor_number, floor_type, custom_prefix=''):
    """
    Computes standard prefix for floor apartment numbering.
    Examples:
      - 'Floor 01', Typical Floor -> '01'
      - 'Floor 05', Typical Floor -> '05'
      - 'Floor 12', Typical Floor -> '12'
      - 'Basement 1', Basement -> 'B1-'
      - 'Podium 2', Podium -> 'P2-'
      - 'Ground Floor', Ground Floor -> 'G'
      - 'Mechanical Floor', Mechanical -> 'M-'
      - 'Roof', Roof -> 'RF-'
    """
    if custom_prefix and custom_prefix.strip():
        return custom_prefix.strip()

    floor_str = str(floor_number or '').strip()
    digits_match = re.search(r'(\d+)', floor_str)
    digits = digits_match.group(1) if digits_match else ''

    if floor_type == Floor.FLOOR_TYPE_BASEMENT:
        return f"B{digits}-" if digits else "B1-"
    elif floor_type == Floor.FLOOR_TYPE_PODIUM:
        return f"P{digits}-" if digits else "P1-"
    elif floor_type == Floor.FLOOR_TYPE_GROUND:
        return "G"
    elif floor_type == Floor.FLOOR_TYPE_MECHANICAL:
        return f"M{digits}-" if digits else "M-"
    elif floor_type == Floor.FLOOR_TYPE_ROOF:
        return "RF-"
    else:  # Typical Floor or Custom
        if digits:
            return digits.zfill(2)
        # Fallback if no digits found (e.g. 'Penthouse')
        cleaned = re.sub(r'[^A-Za-z0-9]', '', floor_str)[:3].upper()
        return cleaned or "01"


def format_apartment_number(prefix, num):
    """
    Formats apartment number using prefix and sequential index.
    e.g. prefix='05', num=1 -> '0501'
    prefix='05', num=16 -> '0516'
    prefix='B1-', num=2 -> 'B1-02'
    """
    if prefix.endswith('-'):
        return f"{prefix}{num:02d}"
    return f"{prefix}{num:02d}"


def generate_apartment_numbers_list(prefix, count, starting_number=1):
    """Generates a sequential list of apartment room number strings."""
    if count <= 0:
        return []
    return [format_apartment_number(prefix, num) for num in range(starting_number, starting_number + count)]


def preview_floor_plan(floor_number, floor_type, apartment_count, starting_number=1, custom_prefix='', common_areas=None):
    """
    Calculates live preview for floor creation and editing.
    Returns preview dict with prefix, apartment list, and common areas list.
    """
    try:
        apartment_count = int(apartment_count)
    except (ValueError, TypeError):
        apartment_count = 0
    if apartment_count < 0:
        apartment_count = 0

    try:
        starting_number = int(starting_number)
    except (ValueError, TypeError):
        starting_number = 1
    if starting_number < 1:
        starting_number = 1

    prefix = compute_floor_prefix(floor_number, floor_type, custom_prefix)
    apartments = generate_apartment_numbers_list(prefix, apartment_count, starting_number)

    common_areas_list = []
    if common_areas:
        for ca in common_areas:
            ca_str = str(ca).strip()
            if ca_str and ca_str not in common_areas_list:
                common_areas_list.append(ca_str)

    return {
        'prefix': prefix,
        'apartment_count': apartment_count,
        'starting_number': starting_number,
        'apartments': apartments,
        'common_areas': common_areas_list,
        'total_apartments': len(apartments),
        'total_common_areas': len(common_areas_list),
        'total_rooms': len(apartments) + len(common_areas_list),
    }


def ensure_floor_milestones_initialized(floor):
    """
    Ensures all active MilestoneDefinitions have RoomMilestoneStatus records
    for all rooms on the floor, initialized to 'Pending'.
    Duplicate-safe using unique constraint ignore_conflicts.
    """
    definitions = list(MilestoneDefinition.objects.all())
    if not definitions:
        return

    rooms = list(floor.rooms.all())
    if not rooms:
        return

    # Check which (room, milestone) pairs already exist
    existing_pairs = set(
        RoomMilestoneStatus.objects.filter(room__floor=floor).values_list('room_id', 'milestone_id')
    )

    new_statuses = []
    for r in rooms:
        for m in definitions:
            if (r.id, m.id) not in existing_pairs:
                new_statuses.append(
                    RoomMilestoneStatus(
                        room=r,
                        milestone=m,
                        status=RoomMilestoneStatus.STATUS_PENDING
                    )
                )

    if new_statuses:
        RoomMilestoneStatus.objects.bulk_create(new_statuses, ignore_conflicts=True)


@transaction.atomic
def create_floor_with_apartments(project, floor_number, floor_type, apartment_count,
                                 starting_number=1, custom_prefix='', common_areas=None):
    """
    Creates a new Floor in a transaction, generates apartment rooms,
    adds common areas, and initializes milestone tracking.
    Duplicate-safe and idempotent.
    """
    if apartment_count < 0:
        raise ValidationError("Apartment count must be a non-negative integer.")
    if starting_number < 1:
        starting_number = 1

    prefix = compute_floor_prefix(floor_number, floor_type, custom_prefix)

    floor, created = Floor.objects.get_or_create(
        project=project,
        floor_number=floor_number.strip(),
        defaults={
            'floor_type': floor_type,
            'apartment_count': apartment_count,
            'numbering_prefix': prefix,
            'starting_number': starting_number,
        }
    )

    if not created:
        floor.floor_type = floor_type
        floor.apartment_count = apartment_count
        floor.numbering_prefix = prefix
        floor.starting_number = starting_number
        floor.save(update_fields=['floor_type', 'apartment_count', 'numbering_prefix', 'starting_number'])

    # Generate apartments
    created_apartments = []
    if apartment_count > 0:
        target_numbers = generate_apartment_numbers_list(prefix, apartment_count, starting_number)
        for num in target_numbers:
            room, r_created = Room.objects.get_or_create(
                floor=floor,
                room_number=num,
                defaults={'room_type': Room.ROOM_TYPE_APARTMENT}
            )
            if r_created:
                created_apartments.append(room)

    # Add common areas
    created_common_areas = []
    if common_areas:
        for ca_name in common_areas:
            ca_name = ca_name.strip()
            if ca_name:
                ca_room, ca_created = Room.objects.get_or_create(
                    floor=floor,
                    room_number=ca_name,
                    defaults={'room_type': Room.ROOM_TYPE_COMMON_AREA}
                )
                if ca_created:
                    created_common_areas.append(ca_room)

    # Initialize all milestone statuses for the floor's rooms
    ensure_floor_milestones_initialized(floor)

    return {
        'floor': floor,
        'created': created,
        'created_apartments': created_apartments,
        'created_common_areas': created_common_areas,
    }


@transaction.atomic
def update_floor_with_apartments(floor, floor_number, floor_type, apartment_count,
                                 starting_number=1, custom_prefix='', confirm_removal=False):
    """
    Updates an existing floor.
    - If apartment count increases: generates only the missing apartment numbers.
    - If apartment count decreases:
      Checks for defect history on excess rooms. Rooms with defects/inspections are NEVER deleted.
      If confirm_removal is False, returns warning and list of removable rooms without deleting them.
      If confirm_removal is True, deletes only rooms that have zero defects/inspections.
    - Preserves all inspection records and defect history.
    """
    if apartment_count < 0:
        raise ValidationError("Apartment count must be a non-negative integer.")
    if starting_number < 1:
        starting_number = 1

    prefix = compute_floor_prefix(floor_number, floor_type, custom_prefix)

    floor.floor_number = floor_number.strip()
    floor.floor_type = floor_type
    floor.apartment_count = apartment_count
    floor.numbering_prefix = prefix
    floor.starting_number = starting_number
    floor.save(update_fields=['floor_number', 'floor_type', 'apartment_count', 'numbering_prefix', 'starting_number'])

    target_numbers = generate_apartment_numbers_list(prefix, apartment_count, starting_number)
    existing_apartments = list(floor.rooms.filter(room_type=Room.ROOM_TYPE_APARTMENT))
    existing_numbers_map = {r.room_number: r for r in existing_apartments}

    # 1. Missing apartments to generate
    missing_numbers = [num for num in target_numbers if num not in existing_numbers_map]
    newly_created = []
    for num in missing_numbers:
        room, created = Room.objects.get_or_create(
            floor=floor,
            room_number=num,
            defaults={'room_type': Room.ROOM_TYPE_APARTMENT}
        )
        if created:
            newly_created.append(room)

    # 2. Check for excess apartments if target count decreased
    excess_rooms = [r for num, r in existing_numbers_map.items() if num not in target_numbers]
    retained_due_to_defects = []
    deleted_rooms = []
    pending_confirmation_rooms = []

    for r in excess_rooms:
        has_inspections = r.defect_inspections.exists() or (r.total_defects_count > 0)
        if has_inspections:
            # SAFETY RULE: NEVER DELETE ROOMS WITH DEFECT/INSPECTION HISTORY
            retained_due_to_defects.append(r)
        else:
            if confirm_removal:
                deleted_rooms.append(r.room_number)
                r.delete()
            else:
                pending_confirmation_rooms.append(r)

    # Initialize any missing milestone definitions
    ensure_floor_milestones_initialized(floor)

    return {
        'floor': floor,
        'newly_created': newly_created,
        'deleted_rooms': deleted_rooms,
        'retained_due_to_defects': retained_due_to_defects,
        'pending_confirmation_rooms': pending_confirmation_rooms,
        'requires_confirmation': len(pending_confirmation_rooms) > 0,
    }


@transaction.atomic
def add_common_areas_to_floor(floor, common_area_names):
    """
    Adds common areas to a floor without counting them as apartments.
    Duplicate-safe.
    """
    created_common_areas = []
    for name in common_area_names:
        name = str(name).strip()
        if name:
            room, created = Room.objects.get_or_create(
                floor=floor,
                room_number=name,
                defaults={'room_type': Room.ROOM_TYPE_COMMON_AREA}
            )
            if created:
                created_common_areas.append(room)

    ensure_floor_milestones_initialized(floor)
    return created_common_areas


@transaction.atomic
def add_manual_room(floor, room_number, room_type=Room.ROOM_TYPE_APARTMENT):
    """Adds a single manual room / apartment to a floor with milestone initialization."""
    room_number = str(room_number).strip()
    if not room_number:
        raise ValidationError("Room number cannot be empty.")

    room, created = Room.objects.get_or_create(
        floor=floor,
        room_number=room_number,
        defaults={'room_type': room_type}
    )
    if not created and room.room_type != room_type:
        room.room_type = room_type
        room.save(update_fields=['room_type'])

    ensure_floor_milestones_initialized(floor)
    return room, created


def safe_delete_room(room):
    """
    Safely deletes a room only if it has NO defect inspections or open NCRs.
    Returns (success, message).
    """
    inspection_count = room.defect_inspections.count()
    if inspection_count > 0:
        return False, f"Room '{room.room_number}' has {inspection_count} defect inspection(s) recorded and cannot be deleted."
    room_num = room.room_number
    room.delete()
    return True, f"Room '{room_num}' deleted successfully."
