import os
import json
import uuid
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.base import ContentFile

from .models import Drawing
from .cad_engine.dwg_converter import convert_dwg_to_dxf, DwgConversionError, detect_dwg_version
from .cad_engine.dxf_parser import parse_dxf_file
from .cad_engine.pdf_parser import parse_pdf_file
from .cad_engine.sample_generator import (
    generate_hvac_dxf,
    generate_plumbing_fire_dxf,
    generate_hvac_pdf,
    generate_plumbing_pdf
)

logger = logging.getLogger(__name__)

def ensure_sample_drawings_exist():
    """Ensures sample files are generated on disk and registered in DB."""
    samples_dir = os.path.join(settings.MEDIA_ROOT, 'samples')
    os.makedirs(samples_dir, exist_ok=True)

    samples = [
        ('sample_mep_hvac.dxf', 'dxf', 'HVAC Ductwork & Equipment Plan (DXF)', generate_hvac_dxf),
        ('sample_mep_plumbing_fire.dxf', 'dxf', 'Chilled Water & Fire Sprinkler Plan (DXF)', generate_plumbing_fire_dxf),
        ('sample_mep_hvac.pdf', 'pdf', 'HVAC Distribution & Schedules (PDF)', generate_hvac_pdf),
        ('sample_mep_plumbing_fire.pdf', 'pdf', 'Plumbing & Sprinkler Layout (PDF)', generate_plumbing_pdf),
    ]

    for fname, ftype, title, gen_fn in samples:
        fpath = os.path.join(samples_dir, fname)
        if not os.path.exists(fpath):
            try:
                gen_fn(fpath)
            except Exception as e:
                logger.error(f"Failed to generate sample {fname}: {e}")

        # Check DB
        rel_path = f"samples/{fname}"
        if not Drawing.objects.filter(original_filename=fname).exists() and os.path.exists(fpath):
            try:
                if ftype == 'dxf':
                    res = parse_dxf_file(fpath)
                    Drawing.objects.create(
                        title=title,
                        original_filename=fname,
                        file=rel_path,
                        file_type='dxf',
                        file_size=os.path.getsize(fpath),
                        scale_unit=res.get('scale_unit', 'mm'),
                        layers_data=res.get('layers', []),
                        components_data=res.get('components', []),
                        geometry_data=res.get('geometry', {}),
                        legends_data=res.get('legends', []),
                        is_3d_capable=res.get('is_3d_capable', True),
                        disclaimer_3d=res.get('disclaimer_3d', '')
                    )
                elif ftype == 'pdf':
                    res = parse_pdf_file(fpath)
                    Drawing.objects.create(
                        title=title,
                        original_filename=fname,
                        file=rel_path,
                        file_type='pdf',
                        file_size=os.path.getsize(fpath),
                        num_pages=res.get('num_pages', 1),
                        layers_data=res.get('layers', []),
                        components_data=res.get('components', []),
                        geometry_data=res.get('geometry', {}),
                        legends_data=res.get('legends', []),
                        intelligence_data={'search_index': res.get('search_index', [])},
                        is_3d_capable=res.get('is_3d_capable', True),
                        disclaimer_3d=res.get('disclaimer_3d', '')
                    )
            except Exception as ex:
                logger.error(f"Failed to ingest sample {fname}: {ex}")

def index(request):
    """Main MEP Drawing Viewer view."""
    ensure_sample_drawings_exist()

    drawing_id = request.GET.get('id')
    active_drawing = None
    if drawing_id:
        try:
            active_drawing = Drawing.objects.get(id=drawing_id)
        except Exception:
            pass

    if not active_drawing:
        # Pick the first available drawing (e.g. HVAC DXF)
        active_drawing = Drawing.objects.first()

    all_drawings = Drawing.objects.all().order_by('-uploaded_at')[:20]

    return render(request, 'viewer/index.html', {
        'active_drawing': active_drawing,
        'all_drawings': all_drawings,
    })

def get_drawing_data(request, drawing_id):
    """Returns JSON payload of drawing data for interactive 2D & 3D viewers."""
    drawing = get_object_or_404(Drawing, id=drawing_id)

    data = {
        'id': str(drawing.id),
        'title': drawing.title,
        'original_filename': drawing.original_filename,
        'file_url': drawing.file.url if drawing.file else '',
        'file_type': drawing.file_type,
        'file_size': drawing.file_size,
        'scale_unit': drawing.scale_unit,
        'scale_ratio': drawing.scale_ratio,
        'is_calibrated': drawing.is_calibrated,
        'calibration_dimension': drawing.calibration_dimension,
        'num_pages': drawing.num_pages,
        'current_page': drawing.current_page,
        'layers': drawing.layers_data,
        'components': drawing.components_data,
        'geometry': drawing.geometry_data,
        'legends': drawing.legends_data,
        'intelligence': drawing.intelligence_data,
        'is_3d_capable': drawing.is_3d_capable,
        'disclaimer_3d': drawing.disclaimer_3d,
        'status': drawing.status,
        'error_message': drawing.error_message,
    }
    return JsonResponse(data)

@csrf_exempt
def upload_drawing(request):
    """Handles upload of PDF, DXF, or DWG drawing files."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST method allowed.")

    uploaded_file = request.FILES.get('drawing_file')
    if not uploaded_file:
        return JsonResponse({'success': False, 'message': 'No file uploaded.'}, status=400)

    filename = uploaded_file.name
    ext = os.path.splitext(filename)[1].lower().replace('.', '')
    
    # Validation: File size limit (50 MB)
    if uploaded_file.size > 52428800:
        return JsonResponse({
            'success': False, 
            'message': 'File size exceeds 50MB limit. Please upload a smaller drawing file.'
        }, status=400)

    # Validation: File extension
    if ext not in ('pdf', 'dxf', 'dwg'):
        return JsonResponse({
            'success': False, 
            'message': f"Unsupported file format '.{ext}'. Supported formats are: PDF, DXF, and DWG."
        }, status=400)

    # Save initial record
    drawing = Drawing(
        title=filename.rsplit('.', 1)[0].replace('_', ' ').title(),
        original_filename=filename,
        file=uploaded_file,
        file_type=ext,
        file_size=uploaded_file.size,
        status='processing'
    )
    drawing.save()
    file_path = drawing.file.path

    try:
        # DWG handling
        if ext == 'dwg':
            try:
                converted_dxf_path = convert_dwg_to_dxf(file_path)
                # Parse converted DXF
                parse_res = parse_dxf_file(converted_dxf_path)
                drawing.file_type = 'dxf'
                drawing.scale_unit = parse_res.get('scale_unit', 'mm')
                drawing.layers_data = parse_res.get('layers', [])
                drawing.components_data = parse_res.get('components', [])
                drawing.geometry_data = parse_res.get('geometry', {})
                drawing.legends_data = parse_res.get('legends', [])
                drawing.is_3d_capable = parse_res.get('is_3d_capable', True)
                drawing.disclaimer_3d = parse_res.get('disclaimer_3d', '')
                drawing.status = 'ready'
                drawing.save()
                return JsonResponse({'success': True, 'drawing_id': str(drawing.id)})
            except DwgConversionError as dwg_err:
                drawing.status = 'error'
                drawing.error_message = dwg_err.args[0]
                drawing.save()
                return JsonResponse({
                    'success': False,
                    'error_type': 'dwg_unsupported',
                    'version': dwg_err.version_str,
                    'message': str(dwg_err),
                    'suggestions': dwg_err.suggestions,
                    'drawing_id': str(drawing.id)
                }, status=422)

        # DXF handling
        elif ext == 'dxf':
            parse_res = parse_dxf_file(file_path)
            drawing.scale_unit = parse_res.get('scale_unit', 'mm')
            drawing.layers_data = parse_res.get('layers', [])
            drawing.components_data = parse_res.get('components', [])
            drawing.geometry_data = parse_res.get('geometry', {})
            drawing.legends_data = parse_res.get('legends', [])
            drawing.is_3d_capable = parse_res.get('is_3d_capable', True)
            drawing.disclaimer_3d = parse_res.get('disclaimer_3d', '')
            drawing.status = 'ready'
            drawing.save()
            return JsonResponse({'success': True, 'drawing_id': str(drawing.id)})

        # PDF handling
        elif ext == 'pdf':
            parse_res = parse_pdf_file(file_path)
            drawing.num_pages = parse_res.get('num_pages', 1)
            drawing.layers_data = parse_res.get('layers', [])
            drawing.components_data = parse_res.get('components', [])
            drawing.geometry_data = parse_res.get('geometry', {})
            drawing.legends_data = parse_res.get('legends', [])
            drawing.intelligence_data = {'search_index': parse_res.get('search_index', [])}
            drawing.is_3d_capable = parse_res.get('is_3d_capable', True)
            drawing.disclaimer_3d = parse_res.get('disclaimer_3d', '')
            drawing.status = 'ready'
            drawing.save()
            return JsonResponse({'success': True, 'drawing_id': str(drawing.id)})

    except Exception as e:
        logger.exception("Error processing uploaded drawing")
        drawing.status = 'error'
        drawing.error_message = str(e)
        drawing.save()
        return JsonResponse({
            'success': False,
            'message': f"Failed to process drawing file: {str(e)}",
            'drawing_id': str(drawing.id)
        }, status=500)

@csrf_exempt
def calibrate_scale(request, drawing_id):
    """Calibrate drawing scale based on two clicked points and a known real-world dimension."""
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")

    drawing = get_object_or_404(Drawing, id=drawing_id)
    try:
        data = json.loads(request.body)
        p1 = data.get('point1') # [x, y]
        p2 = data.get('point2') # [x, y]
        known_distance = float(data.get('known_distance')) # e.g. 5000
        unit = data.get('unit', 'mm')

        # Distance in drawing units
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        drawing_distance = (dx**2 + dy**2) ** 0.5

        if drawing_distance <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid points selected.'}, status=400)

        # Scale ratio: real mm per 1 drawing unit
        scale_ratio = known_distance / drawing_distance

        drawing.scale_ratio = scale_ratio
        drawing.scale_unit = unit
        drawing.is_calibrated = True
        drawing.calibration_dimension = known_distance
        drawing.save()

        return JsonResponse({
            'success': True,
            'scale_ratio': scale_ratio,
            'scale_unit': unit,
            'known_distance': known_distance
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@csrf_exempt
def add_manual_component(request, drawing_id):
    """Allows manual component tagging when automatic recognition misses it."""
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")

    drawing = get_object_or_404(Drawing, id=drawing_id)
    try:
        data = json.loads(request.body)
        tag = data.get('tag', 'CUSTOM-01')
        comp_type = data.get('type', 'Custom MEP Component')
        disc = data.get('discipline', 'HVAC')
        dims = data.get('dimensions', 'Not specified')
        material = data.get('material', 'Not specified')
        specs = data.get('specs', {})
        bbox = data.get('bbox', [0, 0, 100, 100])
        sheet = data.get('sheet', 1)

        new_comp = {
            'id': f"comp-manual-{uuid.uuid4().hex[:6]}",
            'tag': tag,
            'name': f"{disc} - {comp_type}",
            'discipline': disc,
            'type': comp_type,
            'dimensions': dims,
            'material': material,
            'specs': specs,
            'sheet': sheet,
            'bbox': bbox,
            'position': [(bbox[0] + bbox[2])/2, (bbox[1] + bbox[3])/2],
            'elevation_aff': 2700,
            'source_evidence': f"Manually calibrated and marked on Sheet {sheet}",
            'source_type': 'User Defined Inspection Annotation',
            'confidence': 'User Verified'
        }

        comps = drawing.components_data or []
        comps.append(new_comp)
        drawing.components_data = comps
        drawing.save()

        return JsonResponse({'success': True, 'component': new_comp})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

def load_sample(request, sample_type):
    """Loads a preconfigured sample drawing."""
    ensure_sample_drawings_exist()
    sample_map = {
        'hvac_dxf': 'sample_mep_hvac.dxf',
        'plumbing_dxf': 'sample_mep_plumbing_fire.dxf',
        'hvac_pdf': 'sample_mep_hvac.pdf',
        'plumbing_pdf': 'sample_mep_plumbing_fire.pdf',
    }
    target_fname = sample_map.get(sample_type, 'sample_mep_hvac.dxf')
    drawing = Drawing.objects.filter(original_filename=target_fname).first()
    if drawing:
        return redirect(f"/?id={drawing.id}")
    return redirect("/")

def list_drawings(request):
    """Returns list of recent drawings for quick switching."""
    drawings = Drawing.objects.all().order_by('-uploaded_at')[:30]
    data = [{
        'id': str(d.id),
        'title': d.title,
        'filename': d.original_filename,
        'file_type': d.file_type,
        'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        'components_count': len(d.components_data) if d.components_data else 0,
        'layers_count': len(d.layers_data) if d.layers_data else 0,
    } for d in drawings]
    return JsonResponse({'drawings': data})
