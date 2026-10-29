/**
 * Interactive 2D Vector CAD & Canvas Viewer
 * Handles high-performance rendering, mouse-wheel zoom, pan, measurements, and component selection.
 */
class CadViewer2D {
  constructor(containerId, overlaySvgId) {
    this.container = document.getElementById(containerId);
    this.canvas = document.getElementById('cad-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.overlaySvg = document.getElementById(overlaySvgId);
    this.pdfContainer = document.getElementById('pdf-container');

    // Transform State
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isPanning = false;
    this.startX = 0;
    this.startY = 0;

    // Drawing Data
    this.drawingData = null;
    this.layersMap = {};
    this.components = [];
    this.selectedComponent = null;

    // Measurement & Active Tools: 'pan', 'select', 'distance', 'polyline', 'area', 'calibrate', 'manual_tag'
    this.activeTool = 'pan';
    this.measurePoints = [];
    this.tempPoint = null;
    this.measurementsList = [];

    // Scale
    this.scaleRatio = 1.0; // 1 unit = scaleRatio mm
    this.scaleUnit = 'mm';

    this.initEvents();
  }

  initEvents() {
    window.addEventListener('resize', () => this.resizeCanvas());

    // Mouse Navigation & Panning
    this.container.addEventListener('mousedown', (e) => this.onMouseDown(e));
    window.addEventListener('mousemove', (e) => this.onMouseMove(e));
    window.addEventListener('mouseup', (e) => this.onMouseUp(e));

    // Mouse Wheel Zoom anchored to cursor
    this.container.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });

    // Touch Support for tablets / mobile
    let touchStartDist = 0;
    this.container.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isPanning = true;
        this.startX = e.touches[0].clientX - this.panX;
        this.startY = e.touches[0].clientY - this.panY;
      } else if (e.touches.length === 2) {
        this.isPanning = false;
        touchStartDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    }, { passive: true });

    this.container.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && this.isPanning) {
        this.panX = e.touches[0].clientX - this.startX;
        this.panY = e.touches[0].clientY - this.startY;
        this.applyTransform();
      } else if (e.touches.length === 2) {
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const factor = dist / touchStartDist;
        if (factor > 0.5 && factor < 2.0) {
          this.zoom = Math.min(Math.max(this.zoom * factor, 0.05), 50.0);
          touchStartDist = dist;
          this.applyTransform();
        }
      }
    }, { passive: true });

    this.container.addEventListener('touchend', () => {
      this.isPanning = false;
    });
  }

  resizeCanvas() {
    const rect = this.container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.scale(dpr, dpr);
    this.render();
  }

  loadData(data) {
    this.drawingData = data;
    this.scaleRatio = data.scale_ratio || 1.0;
    this.scaleUnit = data.scale_unit || 'mm';
    this.components = data.components || [];

    // Map layer visibility
    this.layersMap = {};
    if (data.layers) {
      data.layers.forEach(l => {
        this.layersMap[l.name] = l.visible !== false;
      });
    }

    this.resizeCanvas();
    this.fitToScreen();
    this.updateSvgOverlay();
  }

  setLayerVisibility(layerName, visible) {
    this.layersMap[layerName] = visible;
    this.render();
  }

  setTool(tool) {
    this.activeTool = tool;
    this.measurePoints = [];
    this.tempPoint = null;
    this.container.classList.remove('panning', 'crosshair');
    if (tool === 'pan') {
      this.container.style.cursor = 'grab';
    } else {
      this.container.style.cursor = 'crosshair';
    }
    this.renderSvgMeasurements();
  }

  screenToModel(clientX, clientY) {
    const rect = this.container.getBoundingClientRect();
    const sx = clientX - rect.left;
    const sy = clientY - rect.top;
    const mx = (sx - this.panX) / this.zoom;
    const my = (sy - this.panY) / this.zoom;
    return { x: mx, y: my };
  }

  modelToScreen(mx, my) {
    return {
      x: mx * this.zoom + this.panX,
      y: my * this.zoom + this.panY
    };
  }

  onMouseDown(e) {
    if (e.button !== 0 && e.button !== 1) return; // Left or Middle click

    if (this.activeTool === 'pan' || e.button === 1 || e.spaceKey) {
      this.isPanning = true;
      this.startX = e.clientX - this.panX;
      this.startY = e.clientY - this.panY;
      this.container.classList.add('panning');
      return;
    }

    const mPos = this.screenToModel(e.clientX, e.clientY);

    // Measurement Tools
    if (this.activeTool === 'distance') {
      this.measurePoints.push([mPos.x, mPos.y]);
      if (this.measurePoints.length === 2) {
        // Complete distance measurement
        const p1 = this.measurePoints[0];
        const p2 = this.measurePoints[1];
        const dist = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) * this.scaleRatio;
        this.measurementsList.push({
          type: 'distance',
          p1: p1,
          p2: p2,
          val: dist,
          unit: this.scaleUnit,
          label: `${dist.toFixed(1)} ${this.scaleUnit}`
        });
        this.measurePoints = [];
        this.renderSvgMeasurements();
      }
    } else if (this.activeTool === 'polyline') {
      this.measurePoints.push([mPos.x, mPos.y]);
      this.renderSvgMeasurements();
    } else if (this.activeTool === 'area') {
      this.measurePoints.push([mPos.x, mPos.y]);
      this.renderSvgMeasurements();
    } else if (this.activeTool === 'calibrate') {
      this.measurePoints.push([mPos.x, mPos.y]);
      if (this.measurePoints.length === 2) {
        // Trigger Calibration Modal
        window.app.promptCalibration(this.measurePoints[0], this.measurePoints[1]);
        this.measurePoints = [];
        this.setTool('select');
      }
      this.renderSvgMeasurements();
    } else if (this.activeTool === 'manual_tag') {
      if (this.measurePoints.length === 0) {
        this.measurePoints.push([mPos.x, mPos.y]);
      } else {
        const p1 = this.measurePoints[0];
        const p2 = [mPos.x, mPos.y];
        const bbox = [
          Math.min(p1[0], p2[0]),
          Math.min(p1[1], p2[1]),
          Math.max(p1[0], p2[0]),
          Math.max(p1[1], p2[1])
        ];
        window.app.promptManualTag(bbox);
        this.measurePoints = [];
        this.setTool('select');
      }
      this.renderSvgMeasurements();
    }
  }

  onMouseMove(e) {
    const rect = this.container.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
      return;
    }

    const mPos = this.screenToModel(e.clientX, e.clientY);

    // Update Bottom Status Coordinates
    const coordEl = document.getElementById('status-coordinates');
    if (coordEl) {
      const realX = (mPos.x * this.scaleRatio).toFixed(1);
      const realY = (mPos.y * this.scaleRatio).toFixed(1);
      coordEl.textContent = `X: ${realX} ${this.scaleUnit}   Y: ${realY} ${this.scaleUnit}`;
    }

    if (this.isPanning) {
      this.panX = e.clientX - this.startX;
      this.panY = e.clientY - this.startY;
      this.applyTransform();
      return;
    }

    if (['distance', 'polyline', 'area', 'calibrate', 'manual_tag'].includes(this.activeTool) && this.measurePoints.length > 0) {
      this.tempPoint = [mPos.x, mPos.y];
      this.renderSvgMeasurements();
    }
  }

  onMouseUp() {
    this.isPanning = false;
    this.container.classList.remove('panning');
  }

  onWheel(e) {
    e.preventDefault();
    const rect = this.container.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const newZoom = Math.min(Math.max(this.zoom * zoomFactor, 0.02), 80.0);

    // Zoom centered at mouse pointer
    this.panX = mouseX - (mouseX - this.panX) * (newZoom / this.zoom);
    this.panY = mouseY - (mouseY - this.panY) * (newZoom / this.zoom);
    this.zoom = newZoom;

    this.applyTransform();
  }

  applyTransform() {
    this.updateZoomDisplay();
    this.render();
    this.updateSvgOverlay();
    this.renderSvgMeasurements();
  }

  updateZoomDisplay() {
    const zoomEl = document.getElementById('status-zoom');
    if (zoomEl) {
      zoomEl.textContent = `${Math.round(this.zoom * 100)}%`;
    }
    const slider = document.getElementById('zoom-slider');
    if (slider) {
      slider.value = Math.round(this.zoom * 100);
    }
  }

  zoomBy(factor) {
    const rect = this.container.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const newZoom = Math.min(Math.max(this.zoom * factor, 0.02), 80.0);
    this.panX = centerX - (centerX - this.panX) * (newZoom / this.zoom);
    this.panY = centerY - (centerY - this.panY) * (newZoom / this.zoom);
    this.zoom = newZoom;
    this.applyTransform();
  }

  fitToScreen() {
    if (!this.drawingData) return;
    const rect = this.container.getBoundingClientRect();
    const geom = this.drawingData.geometry;

    if (geom && geom.bounds) {
      const b = geom.bounds;
      const bW = b.width || 1000;
      const bH = b.height || 1000;
      const margin = 60;
      const scaleX = (rect.width - margin * 2) / bW;
      const scaleY = (rect.height - margin * 2) / bH;
      this.zoom = Math.min(scaleX, scaleY, 2.0);

      // Center model bounds in viewport (Note: CAD Y is positive UP)
      this.panX = (rect.width - bW * this.zoom) / 2 - b.min_x * this.zoom;
      this.panY = (rect.height + bH * this.zoom) / 2 + b.min_y * this.zoom;
    } else {
      this.zoom = 1.0;
      this.panX = rect.width / 2;
      this.panY = rect.height / 2;
    }

    this.applyTransform();
  }

  resetZoom() {
    this.zoom = 1.0;
    this.applyTransform();
  }

  render() {
    const rect = this.container.getBoundingClientRect();
    this.ctx.clearRect(0, 0, rect.width, rect.height);

    if (!this.drawingData || this.drawingData.file_type === 'pdf') {
      return; // PDF rendered via PDF.js
    }

    const geom = this.drawingData.geometry;
    if (!geom) return;

    this.ctx.save();
    // CAD Transform: Translate and scale. CAD Y is positive UP so we invert Y!
    this.ctx.translate(this.panX, this.panY);
    this.ctx.scale(this.zoom, -this.zoom);

    // 1. Render Lines
    if (geom.lines) {
      this.ctx.lineWidth = 1.2 / this.zoom;
      geom.lines.forEach(line => {
        if (this.layersMap[line.layer] === false) return;
        this.ctx.strokeStyle = line.color || '#00e5ff';
        this.ctx.beginPath();
        this.ctx.moveTo(line.start[0], line.start[1]);
        this.ctx.lineTo(line.end[0], line.end[1]);
        this.ctx.stroke();
      });
    }

    // 2. Render Polylines
    if (geom.polylines) {
      this.ctx.lineWidth = 1.4 / this.zoom;
      geom.polylines.forEach(pl => {
        if (this.layersMap[pl.layer] === false) return;
        if (!pl.points || pl.points.length < 2) return;
        this.ctx.strokeStyle = pl.color || '#00e5ff';
        this.ctx.beginPath();
        this.ctx.moveTo(pl.points[0][0], pl.points[0][1]);
        for (let i = 1; i < pl.points.length; i++) {
          this.ctx.lineTo(pl.points[i][0], pl.points[i][1]);
        }
        if (pl.closed) {
          this.ctx.closePath();
        }
        this.ctx.stroke();
      });
    }

    // 3. Render Circles & Arcs
    if (geom.circles) {
      this.ctx.lineWidth = 1.2 / this.zoom;
      geom.circles.forEach(c => {
        if (this.layersMap[c.layer] === false) return;
        this.ctx.strokeStyle = c.color || '#00e5ff';
        this.ctx.beginPath();
        if (c.is_arc) {
          const sAngle = (c.start_angle * Math.PI) / 180;
          const eAngle = (c.end_angle * Math.PI) / 180;
          this.ctx.arc(c.center[0], c.center[1], c.radius, sAngle, eAngle);
        } else {
          this.ctx.arc(c.center[0], c.center[1], c.radius, 0, Math.PI * 2);
        }
        this.ctx.stroke();
      });
    }

    // 4. Render Text Annotations
    if (geom.texts) {
      geom.texts.forEach(txt => {
        if (this.layersMap[txt.layer] === false) return;
        this.ctx.save();
        this.ctx.translate(txt.x, txt.y);
        // Invert Y back for readable text!
        this.ctx.scale(1, -1);
        const rotRad = (-(txt.rotation || 0) * Math.PI) / 180;
        this.ctx.rotate(rotRad);

        const fontSize = Math.max(txt.height || 10, 4);
        this.ctx.font = `${fontSize}px 'JetBrains Mono', monospace`;
        this.ctx.fillStyle = txt.color || '#ffffff';
        this.ctx.fillText(txt.text, 0, 0);
        this.ctx.restore();
      });
    }

    this.ctx.restore();
  }

  updateSvgOverlay() {
    if (!this.overlaySvg) return;
    this.overlaySvg.innerHTML = '';

    if (!this.components || this.components.length === 0) return;

    const isPdf = this.drawingData && this.drawingData.file_type === 'pdf';

    this.components.forEach(comp => {
      const bbox = comp.bbox;
      if (!bbox || bbox.length < 4) return;

      let p1, p2;
      if (isPdf) {
        // PDF: Y is positive DOWN
        p1 = this.modelToScreen(bbox[0], bbox[1]);
        p2 = this.modelToScreen(bbox[2], bbox[3]);
      } else {
        // CAD: Y is positive UP
        p1 = {
          x: bbox[0] * this.zoom + this.panX,
          y: -bbox[3] * this.zoom + this.panY
        };
        p2 = {
          x: bbox[2] * this.zoom + this.panX,
          y: -bbox[1] * this.zoom + this.panY
        };
      }

      const rx = Math.min(p1.x, p2.x);
      const ry = Math.min(p1.y, p2.y);
      const rw = Math.max(Math.abs(p2.x - p1.x), 18);
      const rh = Math.max(Math.abs(p2.y - p1.y), 18);

      const isSelected = this.selectedComponent && this.selectedComponent.id === comp.id;

      // Create SVG clickable element
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', 'mep-component-node');
      g.style.cursor = 'pointer';

      // Discipline color
      const colMap = {
        'HVAC': '#00e5ff',
        'Plumbing': '#06d6a0',
        'Fire Protection': '#ff4d6d',
        'Electrical': '#ffb703'
      };
      const strokeCol = colMap[comp.discipline] || '#00e5ff';

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', rx);
      rect.setAttribute('y', ry);
      rect.setAttribute('width', rw);
      rect.setAttribute('height', rh);
      rect.setAttribute('rx', 4);
      rect.setAttribute('fill', isSelected ? 'rgba(0, 229, 255, 0.25)' : 'rgba(0, 229, 255, 0.05)');
      rect.setAttribute('stroke', isSelected ? '#00e5ff' : strokeCol);
      rect.setAttribute('stroke-width', isSelected ? '3' : '1.5');
      rect.setAttribute('stroke-dasharray', isSelected ? 'none' : '4,2');

      if (isSelected) {
        rect.setAttribute('class', 'component-highlight-rect');
      }

      // Hover tag label
      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = `${comp.tag} | ${comp.name} (${comp.discipline})`;
      g.appendChild(title);

      g.appendChild(rect);

      // Event listener
      g.addEventListener('click', (ev) => {
        ev.stopPropagation();
        this.selectComponent(comp);
      });

      this.overlaySvg.appendChild(g);
    });
  }

  selectComponent(comp) {
    this.selectedComponent = comp;
    this.updateSvgOverlay();
    if (window.app) {
      window.app.displayComponentDetails(comp);
    }
  }

  zoomToComponent(comp) {
    if (!comp || !comp.bbox) return;
    this.selectComponent(comp);

    const isPdf = this.drawingData && this.drawingData.file_type === 'pdf';
    const cx = (comp.bbox[0] + comp.bbox[2]) / 2;
    const cy = (comp.bbox[1] + comp.bbox[3]) / 2;

    const rect = this.container.getBoundingClientRect();
    this.zoom = Math.max(this.zoom, 1.8);

    if (isPdf) {
      this.panX = rect.width / 2 - cx * this.zoom;
      this.panY = rect.height / 2 - cy * this.zoom;
    } else {
      this.panX = rect.width / 2 - cx * this.zoom;
      this.panY = rect.height / 2 + cy * this.zoom;
    }

    this.applyTransform();
  }

  renderSvgMeasurements() {
    const isPdf = this.drawingData && this.drawingData.file_type === 'pdf';
    const svg = this.overlaySvg;
    if (!svg) return;

    // Remove old measurements layer
    const oldM = svg.querySelectorAll('.measurement-graphic');
    oldM.forEach(el => el.remove());

    const toScreen = (pt) => {
      if (isPdf) {
        return this.modelToScreen(pt[0], pt[1]);
      } else {
        return {
          x: pt[0] * this.zoom + this.panX,
          y: -pt[1] * this.zoom + this.panY
        };
      }
    };

    // Render Completed Measurements
    this.measurementsList.forEach(m => {
      const p1 = toScreen(m.p1);
      const p2 = toScreen(m.p2);

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', 'measurement-graphic');

      // Line
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1.x);
      line.setAttribute('y1', p1.y);
      line.setAttribute('x2', p2.x);
      line.setAttribute('y2', p2.y);
      line.setAttribute('stroke', '#ffb703');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('stroke-dasharray', '5,3');
      g.appendChild(line);

      // Dimension ticks / points
      [p1, p2].forEach(p => {
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', p.x);
        c.setAttribute('cy', p.y);
        c.setAttribute('r', '4');
        c.setAttribute('fill', '#ffb703');
        g.appendChild(c);
      });

      // Dimension Text Badge
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;

      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      bg.setAttribute('x', midX - 35);
      bg.setAttribute('y', midY - 12);
      bg.setAttribute('width', 70);
      bg.setAttribute('height', 20);
      bg.setAttribute('rx', 4);
      bg.setAttribute('fill', '#141822');
      bg.setAttribute('stroke', '#ffb703');
      bg.setAttribute('stroke-width', '1');
      g.appendChild(bg);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', midX);
      text.setAttribute('y', midY + 2);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', '#ffffff');
      text.setAttribute('font-size', '11');
      text.setAttribute('font-family', 'JetBrains Mono, monospace');
      text.textContent = m.label;
      g.appendChild(text);

      svg.appendChild(g);
    });

    // Render In-Progress Active Measurement
    if (this.measurePoints.length > 0 && this.tempPoint) {
      const p1 = toScreen(this.measurePoints[this.measurePoints.length - 1]);
      const p2 = toScreen(this.tempPoint);

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', 'measurement-graphic');

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1.x);
      line.setAttribute('y1', p1.y);
      line.setAttribute('x2', p2.x);
      line.setAttribute('y2', p2.y);
      line.setAttribute('stroke', '#00e5ff');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('stroke-dasharray', '4,2');
      g.appendChild(line);

      const dist = Math.hypot(
        this.tempPoint[0] - this.measurePoints[this.measurePoints.length - 1][0],
        this.tempPoint[1] - this.measurePoints[this.measurePoints.length - 1][1]
      ) * this.scaleRatio;

      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', midX);
      text.setAttribute('y', midY - 8);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', '#00e5ff');
      text.setAttribute('font-size', '12');
      text.setAttribute('font-weight', 'bold');
      text.setAttribute('font-family', 'JetBrains Mono, monospace');
      text.textContent = `${dist.toFixed(1)} ${this.scaleUnit}`;
      g.appendChild(text);

      svg.appendChild(g);
    }
  }

  clearMeasurements() {
    this.measurementsList = [];
    this.measurePoints = [];
    this.tempPoint = null;
    this.renderSvgMeasurements();
  }
}
