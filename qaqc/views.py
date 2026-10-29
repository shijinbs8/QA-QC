import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db.models import Count, Q
from django.utils import timezone

from .models import Project, DefectInspection, Floor, Room, MilestoneDefinition, RoomMilestoneStatus
from .forms import (
    LoginForm, RegisterForm, ProjectForm, DefectInspectionForm,
    FloorCreationForm, FloorEditForm, RoomManualForm, CommonAreaAddForm
)
from .floor_generator import (
    STANDARD_COMMON_AREAS,
    compute_floor_prefix,
    preview_floor_plan,
    create_floor_with_apartments,
    update_floor_with_apartments,
    add_common_areas_to_floor,
    add_manual_room,
    safe_delete_room,
    ensure_floor_milestones_initialized,
)


def ensure_default_milestones():
    """Seeds standard MEP milestone definitions if missing."""
    default_milestones = [
        {"name": "Suspension", "category": MilestoneDefinition.CATEGORY_GENERAL, "display_order": 1},
        {"name": "Dropings / Framing", "category": MilestoneDefinition.CATEGORY_GENERAL, "display_order": 2},
        {"name": "First Fix", "category": MilestoneDefinition.CATEGORY_GENERAL, "display_order": 3},
        {"name": "Ducting Installation & Insulation", "category": MilestoneDefinition.CATEGORY_HVAC, "display_order": 4},
        {"name": "Pressure Test", "category": MilestoneDefinition.CATEGORY_PLUMBING, "display_order": 5},
        {"name": "Cabling & Grounding", "category": MilestoneDefinition.CATEGORY_ELECTRICAL, "display_order": 6},
        {"name": "Sprinkler Droppers", "category": MilestoneDefinition.CATEGORY_FIREFIGHTING, "display_order": 7},
        {"name": "Ceiling Completion", "category": MilestoneDefinition.CATEGORY_GENERAL, "display_order": 8},
        {"name": "Civil High Wall Closing", "category": MilestoneDefinition.CATEGORY_CIVIL, "display_order": 9},
        {"name": "False Ceiling Framing", "category": MilestoneDefinition.CATEGORY_FITOUT, "display_order": 10},
        {"name": "False Ceiling Closure", "category": MilestoneDefinition.CATEGORY_FITOUT, "display_order": 11},
        {"name": "Final QA/QC Clearance", "category": MilestoneDefinition.CATEGORY_GENERAL, "display_order": 12},
    ]
    for m in default_milestones:
        MilestoneDefinition.objects.get_or_create(
            name=m["name"],
            defaults={"category": m["category"], "display_order": m["display_order"]}
        )


def ensure_project_floors_and_rooms(project):
    """Ensures a project has configured floors and rooms for matrix inspection."""
    if project.floors.exists():
        return

    floor_specs = [
        ("Basement 1", ["Plant Room B1", "Pump Room B1", "Electrical Switchgear", "Water Tank Room"]),
        ("Ground Floor", ["Main Lobby", "Security Control Room", "Service Corridor G", "Retail Unit 101"]),
        ("Floor 01", ["Room 101", "Room 102", "Room 103", "Corridor 1A", "Electrical Closet 1"]),
        ("Floor 02", ["Room 201", "Room 202", "Room 203", "Corridor 2A", "HVAC Riser 2"]),
        ("Floor 03", ["Room 301", "Room 302", "Apt 303", "Corridor 3A", "AHU Room 3"]),
    ]

    for floor_name, room_names in floor_specs:
        fl, _ = Floor.objects.get_or_create(project=project, floor_number=floor_name)
        for r_name in room_names:
            Room.objects.get_or_create(floor=fl, room_number=r_name)



def get_global_metrics(user=None):
    """Computes real-time user metrics for top header and dashboard."""
    total_projects = Project.objects.count()
    total_inspections = DefectInspection.objects.count()
    open_ncrs = DefectInspection.objects.filter(status=DefectInspection.STATUS_NCR).count()
    pending = DefectInspection.objects.filter(status=DefectInspection.STATUS_PENDING).count()
    cleared = DefectInspection.objects.filter(status=DefectInspection.STATUS_CLEARED).count()

    clearance_rate = 0
    if total_inspections > 0:
        clearance_rate = round((cleared / total_inspections) * 100, 1)

    return {
        'total_projects': total_projects,
        'total_inspections': total_inspections,
        'open_ncrs': open_ncrs,
        'pending_clearance': pending,
        'given_clearance': cleared,
        'clearance_rate': clearance_rate,
        'system_time': timezone.now().strftime('%b %d, %Y - %H:%M UTC'),
    }


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}! QA/QC session active.")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = LoginForm()

    return render(request, 'qaqc/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Store role in profile or user model
            role = form.cleaned_data.get('role', 'MEP QA/QC Engineer')
            # Log the new user in
            login(request, user)
            messages.success(request, f"Account created successfully as {role}! Welcome to MEP QA/QC Cloud.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please resolve the errors highlighted below.")
    else:
        form = RegisterForm()

    return render(request, 'qaqc/register.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out safely.")
    return redirect('login')


@login_required
def dashboard_view(request):
    metrics = get_global_metrics(request.user)

    # Department breakdown
    departments = [
        DefectInspection.DEPARTMENT_HVAC,
        DefectInspection.DEPARTMENT_PLUMBING,
        DefectInspection.DEPARTMENT_ELECTRICAL,
        DefectInspection.DEPARTMENT_FIREFIGHTING,
    ]

    dept_stats = []
    total_count = metrics['total_inspections'] or 1
    for dept in departments:
        count = DefectInspection.objects.filter(department=dept).count()
        ncr_count = DefectInspection.objects.filter(department=dept, status=DefectInspection.STATUS_NCR).count()
        pending_count = DefectInspection.objects.filter(department=dept, status=DefectInspection.STATUS_PENDING).count()
        cleared_count = DefectInspection.objects.filter(department=dept, status=DefectInspection.STATUS_CLEARED).count()
        pct = round((count / total_count) * 100, 1) if metrics['total_inspections'] > 0 else 0
        dept_stats.append({
            'name': dept,
            'count': count,
            'percentage': pct,
            'ncr_count': ncr_count,
            'pending_count': pending_count,
            'cleared_count': cleared_count,
        })

    # Recent inspections
    recent_inspections = DefectInspection.objects.select_related('project').order_by('-date_recorded')[:8]

    # Projects overview
    projects = Project.objects.annotate(
        defect_count=Count('inspections')
    ).order_by('-date_created')[:6]

    # Critical Open NCRs
    critical_ncrs = DefectInspection.objects.filter(
        status=DefectInspection.STATUS_NCR
    ).select_related('project').order_by('-date_recorded')[:5]

    context = {
        'page_title': 'QA/QC Executive Dashboard',
        'metrics': metrics,
        'dept_stats': dept_stats,
        'recent_inspections': recent_inspections,
        'projects': projects,
        'critical_ncrs': critical_ncrs,
    }
    return render(request, 'qaqc/dashboard.html', context)


@login_required
def projects_list_view(request):
    query = request.GET.get('q', '').strip()
    projects = Project.objects.prefetch_related('inspections').order_by('-date_created')

    if query:
        projects = projects.filter(
            Q(name__icontains=query) |
            Q(pm_name__icontains=query) |
            Q(mechanical_lead__icontains=query) |
            Q(electrical_lead__icontains=query) |
            Q(hvac_lead__icontains=query)
        )

    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            new_proj = form.save()
            messages.success(request, f"Project '{new_proj.name}' initialized successfully with {new_proj.total_floors} floors.")
            return redirect('projects_list')
        else:
            messages.error(request, "Failed to create project. Please verify the form inputs.")
    else:
        form = ProjectForm()

    context = {
        'page_title': 'Projects Directory',
        'projects': projects,
        'form': form,
        'query': query,
        'metrics': get_global_metrics(request.user),
    }
    return render(request, 'qaqc/projects_list.html', context)


@login_required
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    ensure_default_milestones()
    ensure_project_floors_and_rooms(project)

    all_inspections = project.inspections.all().order_by('-date_recorded')

    # -------------------------------------------------------------
    # Phase 5: Dynamic Floor & Room Milestone Tracking & Matrix Engine
    # -------------------------------------------------------------
    floors = project.floors.all().order_by('floor_number')
    selected_matrix_floor_id = request.GET.get('matrix_floor', '')
    current_matrix_floor = None

    if selected_matrix_floor_id and selected_matrix_floor_id.isdigit():
        current_matrix_floor = floors.filter(pk=int(selected_matrix_floor_id)).first()
    if not current_matrix_floor and floors.exists():
        current_matrix_floor = floors.first()
        selected_matrix_floor_id = str(current_matrix_floor.id)

    selected_category = request.GET.get('category', 'ALL')
    milestones_qs = MilestoneDefinition.objects.all().order_by('display_order', 'id')
    if selected_category and selected_category != 'ALL':
        milestones_qs = milestones_qs.filter(category=selected_category)
    matrix_milestones = list(milestones_qs)

    matrix_rows = []
    matrix_stats = {
        'total_cells': 0,
        'done_cells': 0,
        'in_progress_cells': 0,
        'pending_cells': 0,
        'na_cells': 0,
        'completion_rate': 0,
    }

    room_type_filter = request.GET.get('room_type', 'ALL')

    if current_matrix_floor:
        all_floor_rooms = list(current_matrix_floor.rooms.all().order_by('room_number'))
        all_defs = list(MilestoneDefinition.objects.all())

        # Ensure status exists for every room & milestone
        existing_statuses = RoomMilestoneStatus.objects.filter(room__in=all_floor_rooms).select_related('milestone')
        status_map = {(s.room_id, s.milestone_id): s for s in existing_statuses}

        missing_to_create = []
        for r in all_floor_rooms:
            for m in all_defs:
                if (r.id, m.id) not in status_map:
                    missing_to_create.append(RoomMilestoneStatus(room=r, milestone=m, status=RoomMilestoneStatus.STATUS_PENDING))
        if missing_to_create:
            RoomMilestoneStatus.objects.bulk_create(missing_to_create, ignore_conflicts=True)
            existing_statuses = RoomMilestoneStatus.objects.filter(room__in=all_floor_rooms).select_related('milestone')
            status_map = {(s.room_id, s.milestone_id): s for s in existing_statuses}

        # Filter rooms by room_type if specified
        matrix_rooms = all_floor_rooms
        if room_type_filter == 'APARTMENT':
            matrix_rooms = [r for r in all_floor_rooms if r.room_type == Room.ROOM_TYPE_APARTMENT]
        elif room_type_filter == 'COMMON_AREA':
            matrix_rooms = [r for r in all_floor_rooms if r.room_type == Room.ROOM_TYPE_COMMON_AREA]

        done_cnt = 0
        in_prog_cnt = 0
        pend_cnt = 0
        na_cnt = 0
        total_cnt = 0

        for room in matrix_rooms:
            cells = []
            for m in matrix_milestones:
                st = status_map.get((room.id, m.id))
                if st:
                    total_cnt += 1
                    if st.status == RoomMilestoneStatus.STATUS_DONE:
                        done_cnt += 1
                    elif st.status == RoomMilestoneStatus.STATUS_IN_PROGRESS:
                        in_prog_cnt += 1
                    elif st.status == RoomMilestoneStatus.STATUS_NA:
                        na_cnt += 1
                    else:
                        pend_cnt += 1

                cells.append({
                    'milestone': m,
                    'status_obj': st,
                })

            matrix_rows.append({
                'room': room,
                'open_defects': room.open_defects_count,
                'total_defects': room.total_defects_count,
                'cells': cells,
            })

        matrix_stats = {
            'total_cells': total_cnt,
            'done_cells': done_cnt,
            'in_progress_cells': in_prog_cnt,
            'pending_cells': pend_cnt,
            'na_cells': na_cnt,
            'completion_rate': round((done_cnt / total_cnt) * 100, 1) if total_cnt > 0 else 0,
        }

    # Tab: Pending Clearances
    pending_inspections = all_inspections.filter(status=DefectInspection.STATUS_PENDING)

    # Tab: Given Clearances
    cleared_inspections = all_inspections.filter(status=DefectInspection.STATUS_CLEARED)

    # Tab: Damages / Improper Work
    damage_keywords = ['damage', 'improper', 'leak', 'crack', 'loose', 'corrosion', 'misalign', 'detached', 'broken', 'displaced', 'excessive']
    q_damage = Q()
    for kw in damage_keywords:
        q_damage |= Q(faults_description__icontains=kw)
    damages_inspections = all_inspections.filter(q_damage)
    if not damages_inspections.exists():
        damages_inspections = all_inspections.exclude(status=DefectInspection.STATUS_CLEARED)

    # Tab: NCR Reports (Non-Conformance Reports)
    ncr_inspections = all_inspections.filter(status=DefectInspection.STATUS_NCR)

    # Tab: Daily Inspection Findings (Grouped by date recorded)
    daily_findings = {}
    for insp in all_inspections:
        date_key = insp.date_recorded.date()
        if date_key not in daily_findings:
            daily_findings[date_key] = []
        daily_findings[date_key].append(insp)

    daily_findings_list = [
        {'date': d, 'items': items, 'count': len(items)}
        for d, items in sorted(daily_findings.items(), key=lambda x: x[0], reverse=True)
    ]

    # Tab: Floor-Based Photo Gallery filterable by floor numbers
    distinct_floors = list(all_inspections.values_list('floor_number', flat=True).distinct().order_by('floor_number'))
    selected_floor = request.GET.get('floor', '')
    
    gallery_inspections = all_inspections
    if selected_floor != '' and selected_floor.lstrip('-').isdigit():
        gallery_inspections = gallery_inspections.filter(floor_number=int(selected_floor))

    active_tab = request.GET.get('tab', 'matrix')
    valid_tabs = ['matrix', 'pending', 'cleared', 'damages', 'ncr', 'daily', 'gallery']
    if active_tab not in valid_tabs:
        active_tab = 'matrix'

    floor_edit_form = None
    if current_matrix_floor:
        floor_edit_form = FloorEditForm(initial={
            'floor_number': current_matrix_floor.floor_number,
            'floor_type': current_matrix_floor.floor_type,
            'apartment_count': current_matrix_floor.total_apartments or current_matrix_floor.apartment_count,
            'starting_number': current_matrix_floor.starting_number,
            'numbering_prefix': current_matrix_floor.numbering_prefix or compute_floor_prefix(current_matrix_floor.floor_number, current_matrix_floor.floor_type),
        })

    context = {
        'page_title': f"{project.name} Workspace",
        'project': project,
        'all_inspections': all_inspections,
        'pending_inspections': pending_inspections,
        'cleared_inspections': cleared_inspections,
        'damages_inspections': damages_inspections,
        'ncr_inspections': ncr_inspections,
        'daily_findings_list': daily_findings_list,
        'distinct_floors': distinct_floors,
        'gallery_inspections': gallery_inspections,
        'selected_floor': selected_floor,
        'active_tab': active_tab,
        'metrics': get_global_metrics(request.user),
        # Matrix context
        'floors': floors,
        'current_matrix_floor': current_matrix_floor,
        'selected_matrix_floor_id': selected_matrix_floor_id,
        'categories': MilestoneDefinition.CATEGORY_CHOICES,
        'selected_category': selected_category,
        'matrix_milestones': matrix_milestones,
        'matrix_rows': matrix_rows,
        'matrix_stats': matrix_stats,
        'milestone_status_choices': RoomMilestoneStatus.STATUS_CHOICES,
        'room_type_filter': room_type_filter,
        # Floor & Apartment Management Forms & Presets
        'floor_creation_form': FloorCreationForm(),
        'floor_edit_form': floor_edit_form,
        'common_area_form': CommonAreaAddForm(),
        'room_manual_form': RoomManualForm(),
        'standard_common_areas': STANDARD_COMMON_AREAS,
    }
    return render(request, 'qaqc/project_detail.html', context)



@login_required
def inspections_list_view(request):
    department = request.GET.get('department', '')
    status = request.GET.get('status', '')
    project_id = request.GET.get('project', '')
    search = request.GET.get('q', '').strip()

    inspections = DefectInspection.objects.select_related('project')

    if department:
        inspections = inspections.filter(department=department)
    if status:
        inspections = inspections.filter(status=status)
    if project_id:
        inspections = inspections.filter(project_id=project_id)
    if search:
        inspections = inspections.filter(
            Q(faults_description__icontains=search) |
            Q(apartment_number__icontains=search) |
            Q(project__name__icontains=search)
        )

    projects = Project.objects.all()

    context = {
        'page_title': 'Defect Inspections Registry',
        'inspections': inspections,
        'projects': projects,
        'selected_department': department,
        'selected_status': status,
        'selected_project': project_id,
        'search_query': search,
        'metrics': get_global_metrics(request.user),
    }
    return render(request, 'qaqc/inspections_list.html', context)


@login_required
def defects_gallery_view(request):
    """
    Dedicated Defects Photo Gallery with multi-criteria filtering:
    Floor-wise, Date-wise, MEP Discipline-wise, Project-wise, and Status-wise.
    Enables multi-selection and direct 1-click sharing to WhatsApp.
    """
    project_id = request.GET.get('project', '').strip()
    floor_number = request.GET.get('floor', '').strip()
    department = request.GET.get('department', '').strip()
    status = request.GET.get('status', '').strip()
    date_filter = request.GET.get('date_filter', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    search = request.GET.get('q', '').strip()

    # Query items that have photos
    inspections = DefectInspection.objects.select_related('project').filter(
        Q(original_image__isnull=False, original_image__gt='') |
        Q(annotated_image__isnull=False, annotated_image__gt='')
    ).order_by('-date_recorded')

    # 1. Project Filter
    if project_id and project_id != 'all':
        inspections = inspections.filter(project_id=project_id)

    # 2. Floor-wise Filter
    if floor_number and floor_number != 'all':
        try:
            inspections = inspections.filter(floor_number=int(floor_number))
        except ValueError:
            pass

    # 3. MEP-wise Filter
    if department and department != 'all':
        inspections = inspections.filter(department=department)

    # 4. Status Filter
    if status and status != 'all':
        inspections = inspections.filter(status=status)

    # 5. Date-wise Filter
    now = timezone.now()
    if date_filter == 'today':
        inspections = inspections.filter(date_recorded__date=now.date())
    elif date_filter == 'week':
        week_ago = now - timezone.timedelta(days=7)
        inspections = inspections.filter(date_recorded__gte=week_ago)
    elif date_filter == 'month':
        month_ago = now - timezone.timedelta(days=30)
        inspections = inspections.filter(date_recorded__gte=month_ago)
    elif date_filter == 'custom':
        if date_from:
            inspections = inspections.filter(date_recorded__date__gte=date_from)
        if date_to:
            inspections = inspections.filter(date_recorded__date__lte=date_to)

    # 6. Search query
    if search:
        inspections = inspections.filter(
            Q(faults_description__icontains=search) |
            Q(apartment_number__icontains=search) |
            Q(project__name__icontains=search)
        )

    # Extract distinct floors for active project or across all
    floor_qs = DefectInspection.objects.filter(
        Q(original_image__isnull=False, original_image__gt='') |
        Q(annotated_image__isnull=False, annotated_image__gt='')
    )
    if project_id and project_id != 'all':
        floor_qs = floor_qs.filter(project_id=project_id)
    distinct_floors = list(floor_qs.values_list('floor_number', flat=True).distinct().order_by('floor_number'))

    projects = Project.objects.all().order_by('name')

    context = {
        'page_title': 'MEP Defects Photo Gallery',
        'inspections': inspections,
        'projects': projects,
        'distinct_floors': distinct_floors,
        'selected_project': project_id,
        'selected_floor': floor_number,
        'selected_department': department,
        'selected_status': status,
        'selected_date_filter': date_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search,
        'total_photos_count': inspections.count(),
        'metrics': get_global_metrics(request.user),
    }
    return render(request, 'qaqc/defects_gallery.html', context)



@login_required
def inspection_create_view(request):
    if request.method == 'POST':
        form = DefectInspectionForm(request.POST, request.FILES)
        if form.is_valid():
            inspection = form.save()
            messages.success(request, f"Defect Inspection #{inspection.id} recorded for {inspection.project.name}.")
            return redirect('inspection_detail', inspection_id=inspection.id)
        else:
            messages.error(request, "Failed to register inspection. Please verify highlighted fields.")
    else:
        initial = {}
        if request.GET.get('project'):
            initial['project'] = request.GET.get('project')
        if request.GET.get('department'):
            initial['department'] = request.GET.get('department')
        form = DefectInspectionForm(initial=initial)

    context = {
        'page_title': 'New QA/QC Defect Inspection',
        'form': form,
        'metrics': get_global_metrics(request.user),
    }
    return render(request, 'qaqc/inspection_form.html', context)


@login_required
def inspection_detail_view(request, inspection_id):
    inspection = get_object_or_404(DefectInspection.objects.select_related('project'), pk=inspection_id)

    # Serialize overlays for JavaScript consumption
    overlay_json = json.dumps(inspection.overlay_positions if isinstance(inspection.overlay_positions, list) else [])

    context = {
        'page_title': f"Defect Inspection #{inspection.id} Details",
        'inspection': inspection,
        'overlay_json': overlay_json,
        'metrics': get_global_metrics(request.user),
    }
    return render(request, 'qaqc/inspection_detail.html', context)


@login_required
@require_POST
def inspection_update_status_api(request, inspection_id):
    inspection = get_object_or_404(DefectInspection, pk=inspection_id)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status in dict(DefectInspection.STATUS_CHOICES):
            inspection.status = new_status
            inspection.save(update_fields=['status'])
            return JsonResponse({
                'success': True,
                'status': inspection.status,
                'badge_class': inspection.status_badge_class
            })
        return JsonResponse({'success': False, 'error': 'Invalid status choice.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def inspection_update_overlay_api(request, inspection_id):
    inspection = get_object_or_404(DefectInspection, pk=inspection_id)
    try:
        data = json.loads(request.body)
        overlays = data.get('overlays', [])
        if isinstance(overlays, list):
            inspection.overlay_positions = overlays
            inspection.save(update_fields=['overlay_positions'])
            return JsonResponse({'success': True, 'count': len(overlays)})
        return JsonResponse({'success': False, 'error': 'Overlays must be a list.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_room_milestone_update(request, status_id):
    """AJAX endpoint to update RoomMilestoneStatus without reloading the page."""
    status_obj = get_object_or_404(RoomMilestoneStatus, pk=status_id)
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        notes = data.get('notes')
        valid_statuses = dict(RoomMilestoneStatus.STATUS_CHOICES)
        if new_status in valid_statuses:
            status_obj.status = new_status
            update_fields = ['status', 'updated_at']
            if notes is not None:
                status_obj.notes = notes
                update_fields.append('notes')
            status_obj.save(update_fields=update_fields)
            return JsonResponse({
                'success': True,
                'status': status_obj.status,
                'badge_class': status_obj.badge_class,
                'updated_at': status_obj.updated_at.strftime('%b %d, %H:%M'),
                'room_id': status_obj.room_id,
                'milestone_id': status_obj.milestone_id,
                'status_id': status_obj.id,
            })
        return JsonResponse({'success': False, 'error': f"Invalid status choice '{new_status}'."}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_floor_rooms(request, floor_id):
    """Returns dynamic room list for the specified floor in JSON."""
    floor = get_object_or_404(Floor, pk=floor_id)
    rooms = floor.rooms.all().order_by('room_number')
    data = [
        {
            'id': r.id,
            'room_number': r.room_number,
            'open_defects': r.open_defects_count,
            'total_defects': r.total_defects_count,
        }
        for r in rooms
    ]
    return JsonResponse({
        'success': True,
        'floor_id': floor.id,
        'floor_number': floor.floor_number,
        'rooms': data
    })


@login_required
def api_project_floors(request, project_id):
    """Returns dynamic floor list for the specified project in JSON."""
    project = get_object_or_404(Project, pk=project_id)
    floors = project.floors.all().order_by('floor_number')
    data = [
        {
            'id': f.id,
            'floor_number': f.floor_number,
            'room_count': f.rooms.count()
        }
        for f in floors
    ]
    return JsonResponse({
        'success': True,
        'project_id': project.id,
        'floors': data
    })


# ==============================================================================
# Floor & Room Automatic Generation & Management Views
# ==============================================================================

@login_required
def floor_create_view(request, project_id):
    """
    Creates a new floor with automatic apartment generation, optional common areas,
    and duplicate-safe milestone initialization in a transaction.
    """
    project = get_object_or_404(Project, pk=project_id)

    if request.method == 'POST':
        form = FloorCreationForm(request.POST)
        if form.is_valid():
            floor_number = form.cleaned_data['floor_number']
            floor_type = form.cleaned_data['floor_type']
            apartment_count = form.cleaned_data['apartment_count']
            starting_number = form.cleaned_data['starting_number']
            custom_prefix = form.cleaned_data['numbering_prefix']
            common_areas = list(form.cleaned_data.get('common_areas') or [])
            custom_ca = form.cleaned_data.get('custom_common_areas', '').strip()
            if custom_ca:
                for item in custom_ca.split(','):
                    c = item.strip()
                    if c and c not in common_areas:
                        common_areas.append(c)

            try:
                res = create_floor_with_apartments(
                    project=project,
                    floor_number=floor_number,
                    floor_type=floor_type,
                    apartment_count=apartment_count,
                    starting_number=starting_number,
                    custom_prefix=custom_prefix,
                    common_areas=common_areas,
                )
                floor = res['floor']
                apt_count = len(res['created_apartments'])
                ca_count = len(res['created_common_areas'])

                msg = f"Floor '{floor.floor_number}' ({floor.floor_type}) created successfully! "
                if apt_count > 0:
                    first_apt = res['created_apartments'][0].room_number
                    last_apt = res['created_apartments'][-1].room_number
                    msg += f"Generated {apt_count} apartment(s) ({first_apt} to {last_apt}). "
                else:
                    msg += "Created without apartments (0 units). "
                if ca_count > 0:
                    msg += f"Added {ca_count} common area(s). "
                msg += "All MEP milestone statuses initialized to Pending."

                messages.success(request, msg)

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                    return JsonResponse({
                        'success': True,
                        'floor_id': floor.id,
                        'floor_number': floor.floor_number,
                        'message': msg,
                        'redirect_url': f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}",
                    })
                return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}")
            except Exception as e:
                messages.error(request, f"Error creating floor: {str(e)}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                    return JsonResponse({'success': False, 'error': str(e)}, status=500)
        else:
            errors_str = " ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
            messages.error(request, f"Please correct the form errors: {errors_str}")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = FloorCreationForm()

    return render(request, 'qaqc/floor_create.html', {
        'page_title': f"Add Floor &bull; {project.name}",
        'project': project,
        'form': form,
        'standard_common_areas': STANDARD_COMMON_AREAS,
    })


@login_required
def floor_edit_view(request, floor_id):
    """
    Edits a floor's metadata and adjusts apartment count safely:
    - If count increases, generates only missing apartment numbers.
    - If count decreases, checks for defect history; rooms with defect inspections are NEVER deleted.
      Empty rooms require explicit confirmation before deletion.
    """
    floor = get_object_or_404(Floor, pk=floor_id)
    project = floor.project

    if request.method == 'POST':
        form = FloorEditForm(request.POST)
        if form.is_valid():
            floor_number = form.cleaned_data['floor_number']
            floor_type = form.cleaned_data['floor_type']
            apartment_count = form.cleaned_data['apartment_count']
            starting_number = form.cleaned_data['starting_number']
            custom_prefix = form.cleaned_data['numbering_prefix']
            confirm_removal = form.cleaned_data['confirm_removal']

            try:
                res = update_floor_with_apartments(
                    floor=floor,
                    floor_number=floor_number,
                    floor_type=floor_type,
                    apartment_count=apartment_count,
                    starting_number=starting_number,
                    custom_prefix=custom_prefix,
                    confirm_removal=confirm_removal,
                )

                if res['requires_confirmation']:
                    cand_names = [r.room_number for r in res['pending_confirmation_rooms']]
                    warning_msg = (
                        f"Apartment count decreased to {apartment_count}. "
                        f"The following {len(cand_names)} empty apartment(s) ({', '.join(cand_names)}) will be removed. "
                        f"Please check 'Confirm removal' to proceed with deletion."
                    )
                    messages.warning(request, warning_msg)
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                        return JsonResponse({
                            'success': False,
                            'requires_confirmation': True,
                            'pending_removal': cand_names,
                            'message': warning_msg,
                        })
                    return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}&edit_floor=1&warn_pending=1")

                msg_parts = [f"Floor '{floor.floor_number}' updated successfully."]
                if res['newly_created']:
                    msg_parts.append(f"Generated {len(res['newly_created'])} new unit(s): {', '.join([r.room_number for r in res['newly_created']])}.")
                if res['deleted_rooms']:
                    msg_parts.append(f"Safely removed {len(res['deleted_rooms'])} unused apartment(s): {', '.join(res['deleted_rooms'])}.")
                if res['retained_due_to_defects']:
                    retained_names = [r.room_number for r in res['retained_due_to_defects']]
                    msg_parts.append(f"Safety Protection: {len(retained_names)} unit(s) ({', '.join(retained_names)}) contain QA/QC inspection or NCR history and were preserved.")

                full_msg = " ".join(msg_parts)
                messages.success(request, full_msg)

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                    return JsonResponse({
                        'success': True,
                        'message': full_msg,
                        'redirect_url': f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}",
                    })
                return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}")
            except Exception as e:
                messages.error(request, f"Error updating floor: {str(e)}")
        else:
            errors_str = " ".join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
            messages.error(request, f"Please resolve form errors: {errors_str}")

    return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}")


@login_required
@require_POST
def floor_delete_view(request, floor_id):
    """
    Deletes a floor after verifying the user's password.
    Protects against accidental or unauthorized deletion.
    """
    floor = get_object_or_404(Floor, pk=floor_id)
    project = floor.project
    password = request.POST.get('password', '').strip()

    # 1. Require and verify user's login password
    if not password or not request.user.check_password(password):
        messages.error(request, "Authentication failed: Incorrect password. Level deletion cancelled.")
        return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}")

    # 2. Defect Inspection Check
    inspections_count = DefectInspection.objects.filter(floor=floor).count()
    confirm_force = request.POST.get('confirm_force_delete') == '1'
    if inspections_count > 0 and not confirm_force:
        messages.error(
            request, 
            f"Safety Protection: Level '{floor.floor_number}' contains {inspections_count} QA/QC inspection record(s). "
            f"Please check 'I acknowledge this floor contains defect records' if you wish to permanently delete it."
        )
        return redirect(f"/projects/{project.id}/?tab=matrix&matrix_floor={floor.id}&delete_floor=1")

    floor_name = floor.floor_number
    floor.delete()
    messages.success(request, f"Level '{floor_name}' and its rooms have been permanently deleted.")
    return redirect(f"/projects/{project.id}/?tab=matrix")


@login_required
@require_POST
def project_delete_view(request, project_id):
    """
    Deletes an entire project site after verifying the user's password.
    Protects against accidental or unauthorized deletion.
    """
    project = get_object_or_404(Project, pk=project_id)
    password = request.POST.get('password', '').strip()
    fallback_redirect = request.POST.get('next') or request.META.get('HTTP_REFERER') or f"/projects/{project.id}/"

    # 1. Require and verify user's login password
    if not password or not request.user.check_password(password):
        messages.error(request, "Authentication failed: Incorrect password. Project site deletion cancelled.")
        return redirect(fallback_redirect)

    project_name = project.name
    project.delete()
    messages.success(request, f"Project Site '{project_name}' and all associated floors, rooms, and QA/QC records have been permanently deleted.")
    return redirect('projects_list')


@login_required
@require_POST
def inspection_delete_view(request, inspection_id):
    """
    Deletes a defect inspection record after verifying the user's password.
    Also cleans up associated image files from storage if present.
    """
    inspection = get_object_or_404(DefectInspection, pk=inspection_id)
    password = request.POST.get('password', '').strip()
    fallback_redirect = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('dashboard')

    # 1. Require and verify user's login password
    if not password or not request.user.check_password(password):
        messages.error(request, "Authentication failed: Incorrect password. Defect inspection deletion cancelled.")
        return redirect(fallback_redirect)

    insp_id = inspection.id
    dept = inspection.department
    proj_name = inspection.project.name

    # 2. Cleanup associated image files from disk/storage so no orphaned files remain
    try:
        if inspection.original_image:
            inspection.original_image.delete(save=False)
        if inspection.annotated_image:
            inspection.annotated_image.delete(save=False)
    except Exception:
        pass

    inspection.delete()
    messages.success(request, f"Defect Inspection #{insp_id} ({dept} - {proj_name}) has been permanently deleted.")
    return redirect(fallback_redirect)



@login_required
def api_floor_preview(request):
    """AJAX endpoint providing live preview of generated apartment numbers and common areas."""
    floor_number = request.GET.get('floor_number') or request.POST.get('floor_number', 'Floor 05')
    floor_type = request.GET.get('floor_type') or request.POST.get('floor_type', 'Typical Floor')
    apartment_count = request.GET.get('apartment_count') or request.POST.get('apartment_count', 16)
    starting_number = request.GET.get('starting_number') or request.POST.get('starting_number', 1)
    custom_prefix = request.GET.get('numbering_prefix') or request.POST.get('numbering_prefix', '')

    common_areas = request.GET.getlist('common_areas[]') or request.GET.getlist('common_areas')
    if not common_areas and request.POST:
        common_areas = request.POST.getlist('common_areas[]') or request.POST.getlist('common_areas')
    custom_ca = request.GET.get('custom_common_areas') or request.POST.get('custom_common_areas', '')
    if custom_ca:
        for ca in custom_ca.split(','):
            c = ca.strip()
            if c and c not in common_areas:
                common_areas.append(c)

    preview = preview_floor_plan(
        floor_number=floor_number,
        floor_type=floor_type,
        apartment_count=apartment_count,
        starting_number=starting_number,
        custom_prefix=custom_prefix,
        common_areas=common_areas,
    )
    return JsonResponse({'success': True, 'preview': preview})


@login_required
@require_POST
def add_common_areas_view(request, floor_id):
    """Adds common areas (Lift Lobby, Corridor, Shafts, etc.) without counting them as apartments."""
    floor = get_object_or_404(Floor, pk=floor_id)
    selected = request.POST.getlist('selected_common_areas')
    custom = request.POST.get('custom_common_area', '').strip()
    if custom:
        for item in custom.split(','):
            c = item.strip()
            if c and c not in selected:
                selected.append(c)

    if not selected:
        messages.warning(request, "No common areas were selected.")
        return redirect(f"/projects/{floor.project_id}/?tab=matrix&matrix_floor={floor.id}")

    created = add_common_areas_to_floor(floor, selected)
    names = [r.room_number for r in created]
    if created:
        messages.success(request, f"Added {len(created)} common area(s) to {floor.floor_number}: {', '.join(names)}. (Not counted as apartments). Milestones initialized.")
    else:
        messages.info(request, "Selected common areas already exist on this floor.")
    return redirect(f"/projects/{floor.project_id}/?tab=matrix&matrix_floor={floor.id}")


@login_required
@require_POST
def room_create_view(request, floor_id):
    """Manually adds a room/apartment to a floor."""
    floor = get_object_or_404(Floor, pk=floor_id)
    room_number = request.POST.get('room_number', '').strip()
    room_type = request.POST.get('room_type', Room.ROOM_TYPE_APARTMENT)

    if not room_number:
        messages.error(request, "Room number is required.")
        return redirect(f"/projects/{floor.project_id}/?tab=matrix&matrix_floor={floor.id}")

    try:
        room, created = add_manual_room(floor, room_number, room_type)
        if created:
            messages.success(request, f"{room_type} '{room.room_number}' added successfully with milestone tracking initialized.")
        else:
            messages.info(request, f"Room '{room.room_number}' already exists on {floor.floor_number}.")
    except Exception as e:
        messages.error(request, f"Error adding room: {str(e)}")

    return redirect(f"/projects/{floor.project_id}/?tab=matrix&matrix_floor={floor.id}")


@login_required
@require_POST
def room_edit_view(request, room_id):
    """Corrects room numbering or updates room designation (Apartment vs Common Area)."""
    room = get_object_or_404(Room, pk=room_id)
    new_number = request.POST.get('room_number', '').strip()
    new_type = request.POST.get('room_type', room.room_type)

    if not new_number:
        messages.error(request, "Room number cannot be empty.")
        return redirect(f"/projects/{room.floor.project_id}/?tab=matrix&matrix_floor={room.floor.id}")

    old_number = room.room_number
    if Room.objects.filter(floor=room.floor, room_number=new_number).exclude(pk=room.id).exists():
        messages.error(request, f"A room with number '{new_number}' already exists on this floor.")
        return redirect(f"/projects/{room.floor.project_id}/?tab=matrix&matrix_floor={room.floor.id}")

    room.room_number = new_number
    room.room_type = new_type
    room.save(update_fields=['room_number', 'room_type'])
    messages.success(request, f"Room '{old_number}' successfully updated to '{new_number}' ({new_type}).")
    return redirect(f"/projects/{room.floor.project_id}/?tab=matrix&matrix_floor={room.floor.id}")


@login_required
@require_POST
def room_delete_view(request, room_id):
    """Deletes a room only if it has zero defect inspections or NCR records."""
    room = get_object_or_404(Room, pk=room_id)
    floor = room.floor
    success, msg = safe_delete_room(room)
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, f"Safety restriction: {msg}")
    return redirect(f"/projects/{floor.project_id}/?tab=matrix&matrix_floor={floor.id}")


@login_required
@require_POST
def milestone_create_view(request):
    """Creates a new milestone definition (e.g. Civil High Wall Closing, False Ceiling) and initializes it across all rooms."""
    name = request.POST.get('name', '').strip()
    category = request.POST.get('category', MilestoneDefinition.CATEGORY_CIVIL)
    display_order = request.POST.get('display_order', 10)
    try:
        display_order = int(display_order)
    except (ValueError, TypeError):
        display_order = 10

    if not name:
        messages.error(request, "Milestone name is required.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

    milestone, created = MilestoneDefinition.objects.get_or_create(
        name=name,
        defaults={
            'category': category,
            'display_order': display_order,
        }
    )

    if created:
        messages.success(request, f"New milestone '[{milestone.category}] {milestone.name}' added successfully! Automatically initialized for all rooms as 'Pending'.")
    else:
        messages.info(request, f"Milestone '{milestone.name}' already exists.")

    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required
def seed_demo_data_view(request):
    """Utility endpoint to seed rich realistic MEP QA/QC demo data."""
    created_projects, created_inspections = create_realistic_seed_data()
    messages.success(request, f"Demo MEP QA/QC dataset loaded! ({created_projects} Projects, {created_inspections} Inspections with image overlays & milestone matrices).")
    return redirect('dashboard')


def create_realistic_seed_data():
    """Seeds realistic MEP projects, floors, rooms, milestones, and defect inspections."""
    ensure_default_milestones()

    projects_data = [
        {
            'name': 'Al Wasl Sky Tower - Phase 1',
            'pm_name': 'Eng. Omar Mansoori',
            'mechanical_lead': 'Eng. Bilal Siddiqui',
            'electrical_lead': 'Eng. Elena Rostova',
            'hvac_lead': 'Eng. Tariq Al-Hassan',
            'total_floors': 52,
        },
        {
            'name': 'Marina Promenade Waterfront Residences',
            'pm_name': 'Eng. Michael Sterling',
            'mechanical_lead': 'Eng. Rajesh Sharma',
            'electrical_lead': 'Eng. Liam O’Connor',
            'hvac_lead': 'Eng. Ahmed El-Sayed',
            'total_floors': 38,
        },
        {
            'name': 'Apex Medical City Specialized Clinic Package',
            'pm_name': 'Eng. Fatima Al-Zahra',
            'mechanical_lead': 'Eng. Carlos Mendes',
            'electrical_lead': 'Eng. David Kim',
            'hvac_lead': 'Eng. Nasser Al-Ghamdi',
            'total_floors': 18,
        },
        {
            'name': 'Gateway Logistics Center & Cold Storage',
            'pm_name': 'Eng. Robert Chen',
            'mechanical_lead': 'Eng. Farooq Azam',
            'electrical_lead': 'Eng. Julian Vance',
            'hvac_lead': 'Eng. Marcus Thorne',
            'total_floors': 6,
        },
    ]

    project_objs = []
    created_p_count = 0
    for pdata in projects_data:
        p, created = Project.objects.get_or_create(
            name=pdata['name'],
            defaults=pdata
        )
        project_objs.append(p)
        if created:
            created_p_count += 1
        ensure_project_floors_and_rooms(p)

    # Let's seed realistic sample milestones for existing rooms
    all_milestones = list(MilestoneDefinition.objects.all().order_by('display_order'))
    statuses_cycle = [
        RoomMilestoneStatus.STATUS_DONE,
        RoomMilestoneStatus.STATUS_DONE,
        RoomMilestoneStatus.STATUS_IN_PROGRESS,
        RoomMilestoneStatus.STATUS_PENDING,
        RoomMilestoneStatus.STATUS_DONE,
        RoomMilestoneStatus.STATUS_NA,
        RoomMilestoneStatus.STATUS_PENDING,
    ]

    for p in project_objs:
        for fl in p.floors.all()[:3]:
            for r_idx, rm in enumerate(fl.rooms.all()):
                for m_idx, ml in enumerate(all_milestones):
                    st_val = statuses_cycle[(r_idx + m_idx) % len(statuses_cycle)]
                    st_obj, _ = RoomMilestoneStatus.objects.get_or_create(
                        room=rm,
                        milestone=ml,
                        defaults={'status': st_val}
                    )
                    if st_obj.status == RoomMilestoneStatus.STATUS_PENDING and st_val != RoomMilestoneStatus.STATUS_PENDING:
                        st_obj.status = st_val
                        st_obj.save(update_fields=['status'])

    # Find or create target floors and rooms for inspections
    p1 = project_objs[0]
    p1_f24, _ = Floor.objects.get_or_create(project=p1, floor_number="Floor 24")
    p1_f24_r1, _ = Room.objects.get_or_create(floor=p1_f24, room_number="Apt 2408 Ceiling Void")
    p1_f24_r2, _ = Room.objects.get_or_create(floor=p1_f24, room_number="Main Electrical Riser #2")
    p1_f18, _ = Floor.objects.get_or_create(project=p1, floor_number="Floor 18")
    p1_f18_r1, _ = Room.objects.get_or_create(floor=p1_f18, room_number="Service Shaft S-18B")

    p2 = project_objs[1]
    p2_f12, _ = Floor.objects.get_or_create(project=p2, floor_number="Floor 12")
    p2_f12_r1, _ = Room.objects.get_or_create(floor=p2_f12, room_number="Corridor East Lift Lobby")
    p2_f15, _ = Floor.objects.get_or_create(project=p2, floor_number="Floor 15")
    p2_f15_r1, _ = Room.objects.get_or_create(floor=p2_f15, room_number="Apt 1502 Mechanical Closet")

    p3 = project_objs[2]
    p3_f4, _ = Floor.objects.get_or_create(project=p3, floor_number="Floor 04")
    p3_f4_r1, _ = Room.objects.get_or_create(floor=p3_f4, room_number="ICU Ward Corridor 4A")
    p3_f2, _ = Floor.objects.get_or_create(project=p3, floor_number="Floor 02")
    p3_f2_r1, _ = Room.objects.get_or_create(floor=p3_f2, room_number="Isolated Power Panel IPS-2")

    p4 = project_objs[3]
    p4_f1, _ = Floor.objects.get_or_create(project=p4, floor_number="Floor 01")
    p4_f1_r1, _ = Room.objects.get_or_create(floor=p4_f1, room_number="Cold Room Chilled Buffer Tank")

    inspections_data = [
        {
            'project': p1,
            'floor': p1_f24,
            'room': p1_f24_r1,
            'department': DefectInspection.DEPARTMENT_HVAC,
            'floor_number': 24,
            'apartment_number': 'Apt 2408 Ceiling Void',
            'faults_description': 'FCU-24-03 flexible duct connection disconnected at plenum box collar. Missing acoustic insulation wrap and Jubilee clip loose. Risk of condensation dripping onto gypsum false ceiling.',
            'status': DefectInspection.STATUS_PENDING,
            'overlay_positions': [
                {'x': 42.5, 'y': 38.0, 'label': 'Flexible Duct Disconnection', 'severity': 'High'},
                {'x': 65.0, 'y': 52.0, 'label': 'Missing Jubilee Clip', 'severity': 'Medium'}
            ]
        },
        {
            'project': p1,
            'floor': p1_f24,
            'room': p1_f24_r2,
            'department': DefectInspection.DEPARTMENT_ELECTRICAL,
            'floor_number': 24,
            'apartment_number': 'Main Electrical Riser #2',
            'faults_description': 'Cable tray earth continuity bonding copper tape not terminated to riser ground bar. Cable tie spacing exceeds 300mm standard per DEWA specification regulations.',
            'status': DefectInspection.STATUS_NCR,
            'overlay_positions': [
                {'x': 50.0, 'y': 30.5, 'label': 'Missing Ground Bonding Tape', 'severity': 'Critical'},
                {'x': 52.0, 'y': 72.0, 'label': 'Excessive Tie Spacing (450mm)', 'severity': 'Low'}
            ]
        },
        {
            'project': p1,
            'floor': p1_f18,
            'room': p1_f18_r1,
            'department': DefectInspection.DEPARTMENT_PLUMBING,
            'floor_number': 18,
            'apartment_number': 'Service Shaft S-18B',
            'faults_description': 'Acoustic HDPE drainage pipe expansion socket seal displaced during pressure test. Minor seepage observed around acoustic clamp fixing.',
            'status': DefectInspection.STATUS_CLEARED,
            'overlay_positions': [
                {'x': 34.0, 'y': 48.0, 'label': 'Repaired HDPE O-ring seal', 'severity': 'Resolved'}
            ]
        },
        {
            'project': p2,
            'floor': p2_f12,
            'room': p2_f12_r1,
            'department': DefectInspection.DEPARTMENT_FIREFIGHTING,
            'floor_number': 12,
            'apartment_number': 'Corridor East Lift Lobby',
            'faults_description': 'Sprinkler head droppers installed without approved ceiling rose escutcheons. Distance to pendant deflector exceeds NFPA 13 maximum 300mm limit.',
            'status': DefectInspection.STATUS_NCR,
            'overlay_positions': [
                {'x': 48.0, 'y': 28.0, 'label': 'Deflector clearance 380mm (Exceeds NFPA 13)', 'severity': 'Critical'},
                {'x': 78.0, 'y': 45.0, 'label': 'Missing Escutcheon Collar', 'severity': 'Medium'}
            ]
        },
        {
            'project': p2,
            'floor': p2_f15,
            'room': p2_f15_r1,
            'department': DefectInspection.DEPARTMENT_HVAC,
            'floor_number': 15,
            'apartment_number': 'Apt 1502 Mechanical Closet',
            'faults_description': 'Condensate drainage trap lacks prime water U-seal depth. Static head backpressure causing water pooling inside secondary drain pan.',
            'status': DefectInspection.STATUS_PENDING,
            'overlay_positions': [
                {'x': 58.0, 'y': 62.0, 'label': 'Shallow P-Trap (< 50mm head)', 'severity': 'High'}
            ]
        },
        {
            'project': p3,
            'floor': p3_f4,
            'room': p3_f4_r1,
            'department': DefectInspection.DEPARTMENT_FIREFIGHTING,
            'floor_number': 4,
            'apartment_number': 'ICU Ward Corridor 4A',
            'faults_description': 'Motorized fire smoke damper (MFSD-4-01) fail-safe actuator terminal block loose. Actuator does not reset automatically on fire alarm signal test.',
            'status': DefectInspection.STATUS_PENDING,
            'overlay_positions': [
                {'x': 36.0, 'y': 41.0, 'label': 'Loose Actuator 24V Signal Wire', 'severity': 'High'}
            ]
        },
        {
            'project': p3,
            'floor': p3_f2,
            'room': p3_f2_r1,
            'department': DefectInspection.DEPARTMENT_ELECTRICAL,
            'floor_number': 2,
            'apartment_number': 'Isolated Power Panel IPS-2',
            'faults_description': 'Medical grade line insulation monitor (LIM) alarm calibrated and zeroed. Passed testing under HTM 06-01 hospital engineering requirements.',
            'status': DefectInspection.STATUS_CLEARED,
            'overlay_positions': [
                {'x': 50.0, 'y': 50.0, 'label': 'Certified LIM Calibration Pass', 'severity': 'Resolved'}
            ]
        },
        {
            'project': p4,
            'floor': p4_f1,
            'room': p4_f1_r1,
            'department': DefectInspection.DEPARTMENT_PLUMBING,
            'floor_number': 1,
            'apartment_number': 'Cold Room Chilled Buffer Tank',
            'faults_description': 'Pressure relief valve discharge piped with 90 degree elbow reduction instead of direct downward gravity run. Safety hazard for hot glycol discharge.',
            'status': DefectInspection.STATUS_NCR,
            'overlay_positions': [
                {'x': 60.0, 'y': 35.0, 'label': 'Non-compliant Relief Discharge Piping', 'severity': 'Critical'}
            ]
        },
    ]

    created_i_count = 0
    for idata in inspections_data:
        insp, created = DefectInspection.objects.get_or_create(
            project=idata['project'],
            department=idata['department'],
            floor_number=idata['floor_number'],
            apartment_number=idata['apartment_number'],
            defaults=idata
        )
        # Update foreign keys if created earlier without them
        if insp.floor != idata.get('floor') or insp.room != idata.get('room'):
            insp.floor = idata.get('floor')
            insp.room = idata.get('room')
            insp.save(update_fields=['floor', 'room'])
        if created:
            created_i_count += 1

    return created_p_count, created_i_count

