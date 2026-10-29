# Interactive MEP Drawing Viewer

A modern, responsive web application for exploring **Mechanical, Electrical, and Plumbing (MEP) engineering drawings** in **PDF, DXF, and DWG formats** in both **2D Plan** and **3D Volumetric BIM** representations.

---

## 🌟 Key Features

### 1. Multi-Format File Upload
- **PDF Drawings**: Multi-page and multi-sheet vector/scanned drawings. High-resolution canvas rendering with [PDF.js](https://mozilla.github.io/pdf.js/).
- **AutoCAD DXF**: Full native vector parsing with `ezdxf` (layers, lines, polylines, circles, arcs, texts, block inserts, and attributes).
- **AutoCAD DWG**: Version header detection (R13 up to AutoCAD 2024) with LibreDWG conversion workflow, informative error modals, and clear export guides.
- **Upload Security**: 50MB file size limit, format validation, and error reporting.

### 2. High-Performance 2D Viewer
- **Smooth Navigation**: Pan by dragging, mouse-wheel zoom centered on cursor, pinch-to-zoom for touch devices.
- **View Controls**: Fit to screen, 100% (1:1), zoom slider, and full-screen mode.
- **CAD Layer Management**: Toggle visibility for individual discipline layers (`M-HVAC-DUCT`, `M-PLUMB-PIPE`, `M-FIRE-SPRN`, `E-POWR-PANEL`, `A-WALL`).
- **Live Cursor Tracking**: Real-time readout of model coordinates ($X, Y$) in calibrated millimeters or inches.

### 3. Volumetric 3D MEP View (Three.js)
- **3D Ducts**: Extruded rectangular geometry with width, height, and insulation seams.
- **3D Piping**: Extruded cylinders with standard MEP service color coding (Chilled Water Blue, Domestic Cold Teal, Fire Red, Drainage Brown).
- **3D Equipment**: Parametric 3D representations of Air Handling Units (AHUs), Chillers, Pumps, and Electrical Distribution Boards.
- **Camera Presets**: Isometric NE, Isometric NW, Top (Plan), Front (Elevation), and Side (Section).
- **Discipline Isolation**: Filter 3D view by HVAC, Piping, Fire Protection, or Electrical.
- **Honest 3D Traceability**: Clear disclaimer indicating whether 3D geometry is extracted directly from CAD vectors or derived from 2D annotations with ceiling height coordination clearances (e.g. 2.7m AFF).

### 4. Clickable MEP Components & Inspector
- Click any component on the drawing to highlight it with a pulsing cyan glow.
- **Right Inspector Sidebar displays**:
  - **Component Tag & Name** (e.g., `AHU-01`, `VAV-101`, `SP-04`, `DB-L1`, `DUCT-02`).
  - **MEP Discipline Badge** (HVAC, Electrical, Plumbing, Fire Protection).
  - **Verified Physical Dimensions** (e.g., $800 \times 400\text{ mm}$, $\text{DN}100\text{ }(4'')$).
  - **Material & Standard** (e.g., Galvanized Sheet Steel SMACNA, Schedule 40 Carbon Steel).
  - **Engineering Specifications** (Airflow CFM, Cooling TR, Flow Rate GPM, Voltage, ESP, Pressure).
  - **Drawing Source Evidence**: The exact text string or CAD block attribute in the file that verified the component.
  - **Honesty Principle**: Missing fields are explicitly marked as `Not specified` rather than invented.

### 5. Drawing Intelligence & Search
- Instant autocomplete search for tags, sizes, and equipment names.
- Clicking a search result smoothly pans and zooms directly to the component.
- **Scale Calibration**: Select two points on the drawing, enter the known real-world dimension (e.g., $5000\text{ mm}$), and the drawing scale is calibrated.
- **Manual Region Tagging**: Allows marking and tagging components when automatic recognition fails.

### 6. Built-in Measurement Tools
- Point-to-point distance measurement with dimension lines and value badges.
- Polyline / run measurement for pipe and duct runs.
- Area calculation tool for rooms and service zones.

---

## 🛠️ Technology Stack
- **Backend**: Python 3.12, Django 5.1 / 6.0, SQLite.
- **CAD Parsing**: `ezdxf`, `pymupdf` (PyMuPDF), `pypdf`, `reportlab`.
- **Frontend**: HTML5 Canvas, SVG Overlay, CSS3 (CAD Dark Theme), JavaScript ES6+, Bootstrap 5.3.
- **Rendering Libraries**: [PDF.js](https://mozilla.github.io/pdf.js/) for vector PDFs, [Three.js](https://threejs.org/) (r128) for 3D MEP models.

---

## 🚀 How to Run Locally

1. **Activate the Virtual Environment**:
   ```bash
   source /Users/shijinbs/Desktop/MyVenv/venv/bin/activate
   ```

2. **Navigate to the Project**:
   ```bash
   cd /Users/shijinbs/.gemini/antigravity-ide/scratch/mep_viewer
   ```

3. **Start the Django Development Server**:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

4. **Open in Your Browser**:
   Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in any modern browser (Chrome, Safari, Firefox, Edge).

---

## 📂 Pre-Loaded Sample Drawings

The application comes with 4 sample engineering drawings accessible via the **Samples** dropdown:
1. `sample_mep_hvac.dxf` — Commercial HVAC Ductwork & Equipment Plan (DXF)
2. `sample_mep_plumbing_fire.dxf` — Chilled Water Piping & Fire Sprinkler Layout (DXF)
3. `sample_mep_hvac.pdf` — Multi-Page HVAC Distribution & Equipment Schedule (PDF)
4. `sample_mep_plumbing_fire.pdf` — Hospital Laboratory Plumbing & Sprinkler Plan (PDF)
