/**
 * MEP Drawing Viewer - Application Controller
 */
class MepViewerApp {
  constructor() {
    this.currentDrawingId = null;
    this.drawingData = null;
    this.currentMode = '2d'; // '2d' or '3d'

    this.viewer2D = new CadViewer2D('viewport-2d', 'overlay-svg');
    this.viewer3D = new CadViewer3D('viewport-3d');
    this.pdfEngine = new PdfViewerEngine('pdf-container', this.viewer2D);

    this.initUI();
  }

  initUI() {
    // Mode Switcher (2D / 3D)
    document.getElementById('btn-mode-2d').addEventListener('click', () => this.switchMode('2d'));
    document.getElementById('btn-mode-3d').addEventListener('click', () => this.switchMode('3d'));

    // Top Zoom / Pan Controls
    document.getElementById('btn-zoom-in').addEventListener('click', () => this.viewer2D.zoomBy(1.2));
    document.getElementById('btn-zoom-out').addEventListener('click', () => this.viewer2D.zoomBy(1 / 1.2));
    document.getElementById('btn-fit-screen').addEventListener('click', () => this.viewer2D.fitToScreen());
    document.getElementById('btn-reset-zoom').addEventListener('click', () => this.viewer2D.resetZoom());
    document.getElementById('btn-fullscreen').addEventListener('click', () => this.toggleFullscreen());

    const zoomSlider = document.getElementById('zoom-slider');
    if (zoomSlider) {
      zoomSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value) / 100;
        this.viewer2D.zoom = Math.max(val, 0.05);
        this.viewer2D.applyTransform();
      });
    }

    // Active Tool Buttons
    const toolBtns = document.querySelectorAll('.cad-tool-btn[data-tool]');
    toolBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        toolBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tool = btn.getAttribute('data-tool');
        this.viewer2D.setTool(tool);
      });
    });

    // Clear Measurements
    const clearMBtn = document.getElementById('btn-clear-measurements');
    if (clearMBtn) {
      clearMBtn.addEventListener('click', () => this.viewer2D.clearMeasurements());
    }

    // Sidebar Tabs
    const tabs = document.querySelectorAll('.cad-sidebar-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const targetId = tab.getAttribute('data-tab');
        document.querySelectorAll('.cad-tab-pane').forEach(p => p.classList.remove('active'));
        const pane = document.getElementById(targetId);
        if (pane) pane.classList.add('active');
      });
    });

    // 3D Camera Controls
    document.querySelectorAll('[data-3d-cam]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const cam = e.currentTarget.getAttribute('data-3d-cam');
        this.viewer3D.setCameraView(cam);
      });
    });

    // 3D Discipline Filter
    document.querySelectorAll('[data-3d-filter]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('[data-3d-filter]').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        const disc = e.currentTarget.getAttribute('data-3d-filter');
        this.viewer3D.filterDiscipline(disc);
      });
    });

    // Component Search & Discipline Filter
    const searchInput = document.getElementById('comp-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', () => this.filterComponentList());
    }

    document.querySelectorAll('.filter-discipline-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-discipline-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        this.filterComponentList();
      });
    });

    // Upload Form
    this.initUploadHandler();

    // Scale Calibration Form
    const calibForm = document.getElementById('calibration-form');
    if (calibForm) {
      calibForm.addEventListener('submit', (e) => this.handleCalibrationSubmit(e));
    }

    // Manual Tag Form
    const manualForm = document.getElementById('manual-tag-form');
    if (manualForm) {
      manualForm.addEventListener('submit', (e) => this.handleManualTagSubmit(e));
    }
  }

  switchMode(mode) {
    this.currentMode = mode;
    const btn2D = document.getElementById('btn-mode-2d');
    const btn3D = document.getElementById('btn-mode-3d');
    const vp2D = document.getElementById('viewport-2d');
    const vp3D = document.getElementById('viewport-3d');

    if (mode === '2d') {
      btn2D.classList.add('active');
      btn3D.classList.remove('active');
      vp2D.style.display = 'block';
      vp3D.style.display = 'none';
      this.viewer2D.render();
      this.viewer2D.updateSvgOverlay();
    } else {
      btn3D.classList.add('active');
      btn2D.classList.remove('active');
      vp2D.style.display = 'none';
      vp3D.style.display = 'block';
      this.viewer3D.onResize();
    }
  }

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => console.log(err));
    } else {
      document.exitFullscreen().catch(err => console.log(err));
    }
  }

  async loadDrawing(drawingId) {
    this.currentDrawingId = drawingId;

    try {
      const resp = await fetch(`/api/drawing/${drawingId}/`);
      if (!resp.ok) throw new Error("Failed to load drawing data.");
      const data = await resp.json();
      this.drawingData = data;

      // Update Header & Status
      document.getElementById('drawing-title-display').textContent = data.title;
      const typeBadge = document.getElementById('drawing-type-badge');
      if (typeBadge) {
        typeBadge.textContent = data.file_type.toUpperCase();
      }

      const statusUnit = document.getElementById('status-scale-unit');
      if (statusUnit) {
        statusUnit.textContent = `${data.scale_unit} ${data.is_calibrated ? '(Calibrated)' : ''}`;
      }

      // Check if PDF or CAD
      if (data.file_type === 'pdf') {
        document.getElementById('cad-canvas').style.display = 'none';
        document.getElementById('pdf-container').style.display = 'block';
        await this.pdfEngine.loadPdf(data.file_url, data.current_page || 1);
        this.viewer2D.loadData(data);
      } else {
        document.getElementById('cad-canvas').style.display = 'block';
        document.getElementById('pdf-container').style.display = 'none';
        this.viewer2D.loadData(data);
      }

      // Load 3D Viewer
      this.viewer3D.loadData(data);

      // Populate Sidebars
      this.populateLayersList(data.layers || []);
      this.populateComponentsList(data.components || []);
      this.populateLegendsList(data.legends || []);
      this.populateSheetsList(data);

      // Select first component if available
      if (data.components && data.components.length > 0) {
        this.displayComponentDetails(data.components[0]);
      } else {
        this.clearInspector();
      }

    } catch (err) {
      console.error(err);
      alert("Error loading drawing: " + err.message);
    }
  }

  populateLayersList(layers) {
    const list = document.getElementById('layers-list-container');
    if (!list) return;
    list.innerHTML = '';

    if (layers.length === 0) {
      list.innerHTML = `<div class="text-muted small p-2">No CAD layers detected in this drawing format.</div>`;
      return;
    }

    layers.forEach(layer => {
      const item = document.createElement('div');
      item.className = 'layer-item';
      item.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <span class="layer-color-dot" style="background-color: ${layer.color || '#00e5ff'};"></span>
          <div>
            <div class="small fw-semibold text-light">${layer.name}</div>
            <span class="text-muted" style="font-size: 0.72rem;">${layer.discipline} • ${layer.count || 0} items</span>
          </div>
        </div>
        <div class="form-check form-switch m-0">
          <input class="form-check-input" type="checkbox" role="switch" checked data-layer="${layer.name}">
        </div>
      `;

      const checkbox = item.querySelector('input');
      checkbox.addEventListener('change', (e) => {
        this.viewer2D.setLayerVisibility(layer.name, e.target.checked);
      });

      list.appendChild(item);
    });
  }

  populateComponentsList(components) {
    this.allComponents = components || [];
    this.filterComponentList();
  }

  filterComponentList() {
    const list = document.getElementById('components-list-container');
    if (!list) return;
    list.innerHTML = '';

    const query = (document.getElementById('comp-search-input')?.value || '').toLowerCase();
    const activeFilterBtn = document.querySelector('.filter-discipline-btn.active');
    const activeDiscipline = activeFilterBtn ? activeFilterBtn.getAttribute('data-discipline') : 'All';

    const filtered = (this.allComponents || []).filter(c => {
      const matchesDisc = activeDiscipline === 'All' || c.discipline === activeDiscipline;
      const matchesQuery = !query || 
        c.tag.toLowerCase().includes(query) || 
        c.name.toLowerCase().includes(query) || 
        c.dimensions.toLowerCase().includes(query);
      return matchesDisc && matchesQuery;
    });

    const countEl = document.getElementById('components-count-badge');
    if (countEl) countEl.textContent = `${filtered.length} found`;

    if (filtered.length === 0) {
      list.innerHTML = `<div class="text-muted small p-3 text-center">No components match search criteria.</div>`;
      return;
    }

    filtered.forEach(comp => {
      const item = document.createElement('div');
      item.className = 'comp-list-item';

      const badgeClass = {
        'HVAC': 'badge-hvac',
        'Plumbing': 'badge-plumb',
        'Fire Protection': 'badge-fire',
        'Electrical': 'badge-elec'
      }[comp.discipline] || 'badge-hvac';

      item.innerHTML = `
        <div class="d-flex align-items-center justify-content-between mb-1">
          <span class="comp-tag-badge ${badgeClass}">${comp.tag}</span>
          <span class="text-muted" style="font-size: 0.7rem;">Sheet ${comp.sheet || 1}</span>
        </div>
        <div class="small fw-semibold text-light mb-1">${comp.name}</div>
        <div class="d-flex justify-content-between text-muted" style="font-size: 0.72rem;">
          <span>${comp.dimensions !== 'Not specified' ? comp.dimensions : comp.type}</span>
          <span class="text-info">${comp.discipline}</span>
        </div>
      `;

      item.addEventListener('click', () => {
        document.querySelectorAll('.comp-list-item').forEach(el => el.classList.remove('selected'));
        item.classList.add('selected');
        this.viewer2D.zoomToComponent(comp);
      });

      list.appendChild(item);
    });
  }

  populateLegendsList(legends) {
    const list = document.getElementById('legends-list-container');
    if (!list) return;
    list.innerHTML = '';

    if (!legends || legends.length === 0) {
      list.innerHTML = `<div class="text-muted small p-2">Standard MEP layer conventions applied.</div>`;
      return;
    }

    legends.forEach(leg => {
      const item = document.createElement('div');
      item.className = 'p-2 mb-2 rounded border border-secondary bg-dark d-flex gap-2 align-items-center';
      item.innerHTML = `
        <span style="width: 14px; height: 14px; border-radius: 3px; background-color: ${leg.color || '#00e5ff'}; display: inline-block;"></span>
        <div class="flex-grow-1">
          <div class="small fw-bold text-light">${leg.discipline}</div>
          <div class="text-muted" style="font-size: 0.72rem;">${leg.description}</div>
        </div>
      `;
      list.appendChild(item);
    });
  }

  populateSheetsList(data) {
    const list = document.getElementById('sheet-list-container');
    if (!list) return;
    if (data.file_type === 'pdf') {
      // PDF engine populates this
      return;
    }

    // CAD Drawing single/multi modelspace
    list.innerHTML = `
      <div class="p-3 rounded border border-primary bg-dark mb-2">
        <div class="d-flex align-items-center gap-2 mb-1">
          <i class="bi bi-file-earmark-code text-info fs-5"></i>
          <div>
            <div class="fw-bold small text-light">Model Space</div>
            <div class="text-muted" style="font-size: 0.72rem;">Complete 2D Coordination Plan</div>
          </div>
        </div>
        <div class="mt-2 text-muted" style="font-size: 0.75rem;">
          Units: <strong>${data.scale_unit}</strong> • Entities: <strong>${data.geometry.lines ? data.geometry.lines.length : 0} lines</strong>
        </div>
      </div>
    `;
  }

  displayComponentDetails(comp) {
    if (!comp) return;

    document.getElementById('insp-tag').textContent = comp.tag || 'N/A';
    document.getElementById('insp-discipline').textContent = comp.discipline || 'General';
    document.getElementById('insp-discipline-badge').className = `badge ${
      comp.discipline === 'HVAC' ? 'bg-info' : 
      (comp.discipline === 'Fire Protection' ? 'bg-danger' : 
      (comp.discipline === 'Electrical' ? 'bg-warning text-dark' : 'bg-success'))
    }`;

    document.getElementById('insp-name').textContent = comp.name || 'MEP Component';
    document.getElementById('insp-type').textContent = comp.type || 'Not specified';

    // Dimensions
    const dimsEl = document.getElementById('insp-dimensions');
    if (comp.dimensions && comp.dimensions !== 'Not specified') {
      dimsEl.innerHTML = `<span class="text-light fw-bold">${comp.dimensions}</span>`;
    } else {
      dimsEl.innerHTML = `<span class="badge bg-secondary">Not specified</span>`;
    }

    // Material
    const matEl = document.getElementById('insp-material');
    if (comp.material && comp.material !== 'Not specified') {
      matEl.innerHTML = `<span class="text-light">${comp.material}</span>`;
    } else {
      matEl.innerHTML = `<span class="badge bg-secondary">Not specified</span>`;
    }

    // Location / Elevation
    const locEl = document.getElementById('insp-location');
    if (comp.position) {
      locEl.textContent = `X: ${comp.position[0].toFixed(1)}, Y: ${comp.position[1].toFixed(1)} (${comp.elevation_aff || 2700} mm AFF)`;
    } else {
      locEl.textContent = `Sheet ${comp.sheet || 1}`;
    }

    // Engineering Specs
    const specsContainer = document.getElementById('insp-specs-container');
    specsContainer.innerHTML = '';
    const specs = comp.specs || {};
    const specKeys = Object.keys(specs);

    if (specKeys.length > 0) {
      specKeys.forEach(k => {
        const row = document.createElement('div');
        row.className = 'inspector-row';
        row.innerHTML = `
          <span class="inspector-label">${k}</span>
          <span class="inspector-value text-info">${specs[k]}</span>
        `;
        specsContainer.appendChild(row);
      });
    } else {
      specsContainer.innerHTML = `<div class="text-muted" style="font-size: 0.78rem;">No additional parameters specified in drawing text.</div>`;
    }

    // Source Evidence / Traceability
    const evidBox = document.getElementById('insp-evidence');
    if (comp.source_evidence) {
      evidBox.textContent = comp.source_evidence;
    } else {
      evidBox.textContent = "Extracted from CAD layer geometry.";
    }
  }

  clearInspector() {
    document.getElementById('insp-tag').textContent = 'No Selection';
    document.getElementById('insp-name').textContent = 'Click any component on the drawing to inspect specifications.';
  }

  initUploadHandler() {
    const uploadInput = document.getElementById('upload-file-input');
    const uploadForm = document.getElementById('upload-modal-form');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressContainer = document.getElementById('upload-progress-container');

    if (uploadForm && uploadInput) {
      uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const file = uploadInput.files[0];
        if (!file) {
          alert("Please select a drawing file to upload.");
          return;
        }

        const formData = new FormData();
        formData.append('drawing_file', file);

        progressContainer.style.display = 'block';
        progressBar.style.width = '30%';

        try {
          const resp = await fetch('/api/upload/', {
            method: 'POST',
            body: formData
          });

          progressBar.style.width = '90%';
          const res = await resp.json();

          if (resp.ok && res.success) {
            progressBar.style.width = '100%';
            // Close upload modal
            bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
            window.location.href = `/?id=${res.drawing_id}`;
          } else if (res.error_type === 'dwg_unsupported') {
            // DWG Error Modal
            progressContainer.style.display = 'none';
            bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
            this.showDwgErrorModal(res);
          } else {
            progressContainer.style.display = 'none';
            alert("Upload failed: " + (res.message || "Unknown error"));
          }
        } catch (err) {
          progressContainer.style.display = 'none';
          alert("Network or server error: " + err.message);
        }
      });
    }
  }

  showDwgErrorModal(errorData) {
    const modalEl = document.getElementById('dwgNoticeModal');
    if (!modalEl) return;

    document.getElementById('dwg-version-detected').textContent = errorData.version || 'AutoCAD DWG';
    document.getElementById('dwg-error-desc').textContent = errorData.message || '';

    const suggestionsList = document.getElementById('dwg-suggestions-list');
    suggestionsList.innerHTML = '';
    (errorData.suggestions || []).forEach(s => {
      const li = document.createElement('li');
      li.className = 'mb-2 text-light';
      li.textContent = s;
      suggestionsList.appendChild(li);
    });

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }

  promptCalibration(p1, p2) {
    this.calibP1 = p1;
    this.calibP2 = p2;
    const distUnits = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]).toFixed(1);
    document.getElementById('calib-measured-units').textContent = distUnits;

    const modal = new bootstrap.Modal(document.getElementById('calibrationModal'));
    modal.show();
  }

  async handleCalibrationSubmit(e) {
    e.preventDefault();
    const knownDim = parseFloat(document.getElementById('calib-known-dim').value);
    const unit = document.getElementById('calib-unit-select').value;

    if (!knownDim || knownDim <= 0) {
      alert("Please enter a valid positive dimension.");
      return;
    }

    try {
      const resp = await fetch(`/api/drawing/${this.currentDrawingId}/calibrate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          point1: this.calibP1,
          point2: this.calibP2,
          known_distance: knownDim,
          unit: unit
        })
      });
      const res = await resp.json();
      if (res.success) {
        this.viewer2D.scaleRatio = res.scale_ratio;
        this.viewer2D.scaleUnit = res.scale_unit;
        document.getElementById('status-scale-unit').textContent = `${res.scale_unit} (Calibrated: 1unit = ${res.scale_ratio.toFixed(2)}${res.scale_unit})`;
        bootstrap.Modal.getInstance(document.getElementById('calibrationModal')).hide();
        alert(`Scale successfully calibrated: 1 drawing unit = ${res.scale_ratio.toFixed(3)} ${res.scale_unit}`);
      }
    } catch (err) {
      alert("Calibration failed: " + err.message);
    }
  }

  promptManualTag(bbox) {
    this.manualBbox = bbox;
    const modal = new bootstrap.Modal(document.getElementById('manualTagModal'));
    modal.show();
  }

  async handleManualTagSubmit(e) {
    e.preventDefault();
    const tag = document.getElementById('manual-comp-tag').value;
    const name = document.getElementById('manual-comp-name').value;
    const disc = document.getElementById('manual-comp-disc').value;
    const dims = document.getElementById('manual-comp-dims').value || 'Not specified';
    const mat = document.getElementById('manual-comp-mat').value || 'Not specified';

    try {
      const resp = await fetch(`/api/drawing/${this.currentDrawingId}/add-component/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tag: tag,
          type: name,
          discipline: disc,
          dimensions: dims,
          material: mat,
          bbox: this.manualBbox
        })
      });
      const res = await resp.json();
      if (res.success) {
        this.allComponents.push(res.component);
        this.viewer2D.components.push(res.component);
        this.viewer2D.updateSvgOverlay();
        this.filterComponentList();
        this.displayComponentDetails(res.component);
        bootstrap.Modal.getInstance(document.getElementById('manualTagModal')).hide();
      }
    } catch (err) {
      alert("Failed to add manual component: " + err.message);
    }
  }
}

// Global application bootstrap
window.addEventListener('DOMContentLoaded', () => {
  window.app = new MepViewerApp();
  const initId = document.getElementById('active-drawing-meta')?.getAttribute('data-id');
  if (initId) {
    window.app.loadDrawing(initId);
  }
});
