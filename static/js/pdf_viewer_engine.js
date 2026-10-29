/**
 * PDF.js Integration Engine for MEP Drawings
 * Renders vector PDF sheets with crisp zoom, synchronized with 2D pan/zoom stage.
 */
class PdfViewerEngine {
  constructor(containerId, cadViewer2D) {
    this.container = document.getElementById(containerId);
    this.cadViewer = cadViewer2D;
    this.pdfDoc = null;
    this.currentPage = 1;
    this.totalPages = 1;
    this.currentRenderTask = null;
    this.pdfCanvas = null;
    this.pageWidth = 0;
    this.pageHeight = 0;

    if (typeof pdfjsLib !== 'undefined') {
      pdfjsLib.GlobalWorkerOptions.workerSrc =
        'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }
  }

  async loadPdf(url, pageNum = 1) {
    if (typeof pdfjsLib === 'undefined') {
      console.warn('PDF.js not loaded.');
      return;
    }
    try {
      this.pdfDoc = await pdfjsLib.getDocument(url).promise;
      this.totalPages = this.pdfDoc.numPages;
      this.currentPage = Math.min(pageNum, this.totalPages);
      this.updateSheetSelector();
      await this.renderPage(this.currentPage);
    } catch (err) {
      console.error('Error loading PDF:', err);
    }
  }

  async renderPage(pageNum) {
    if (!this.pdfDoc) return;
    this.currentPage = pageNum;

    const page = await this.pdfDoc.getPage(pageNum);
    // Use 2x scale for retina sharpness
    const viewport = page.getViewport({ scale: 2.0 });

    if (!this.pdfCanvas) {
      this.pdfCanvas = document.createElement('canvas');
      this.pdfCanvas.id = 'pdf-render-canvas';
      this.container.innerHTML = '';
      this.container.appendChild(this.pdfCanvas);
    }

    const canvas = this.pdfCanvas;
    const ctx = canvas.getContext('2d');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    // Display at 50% of the rendered size (for retina)
    this.pageWidth = viewport.width / 2;
    this.pageHeight = viewport.height / 2;
    canvas.style.width = `${this.pageWidth}px`;
    canvas.style.height = `${this.pageHeight}px`;

    if (this.currentRenderTask) {
      try { this.currentRenderTask.cancel(); } catch (e) {}
    }

    this.currentRenderTask = page.render({
      canvasContext: ctx,
      viewport: viewport
    });

    try {
      await this.currentRenderTask.promise;
    } catch (e) {
      if (e.name !== 'RenderingCancelledException') console.error(e);
    }

    this.container.style.display = 'block';

    // Update CAD viewer's geometry bounds to match PDF dimensions
    // PDF coordinate space: origin top-left, Y positive downward
    if (this.cadViewer && this.cadViewer.drawingData) {
      if (!this.cadViewer.drawingData.geometry) {
        this.cadViewer.drawingData.geometry = {};
      }
      this.cadViewer.drawingData.geometry.bounds = {
        min_x: 0, min_y: 0,
        max_x: this.pageWidth, max_y: this.pageHeight,
        width: this.pageWidth, height: this.pageHeight
      };
      this.cadViewer.isPdfMode = true;
      this.cadViewer.fitToScreen();
    }
  }

  updateSheetSelector() {
    const container = document.getElementById('sheet-list-container');
    if (!container) return;
    container.innerHTML = '';

    for (let p = 1; p <= this.totalPages; p++) {
      const item = document.createElement('div');
      const isCurrent = p === this.currentPage;
      item.className = `p-2 mb-2 rounded border ${isCurrent ? 'border-info bg-dark' : 'border-secondary'} d-flex align-items-center justify-content-between`;
      item.style.cursor = 'pointer';
      item.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <i class="bi bi-file-earmark-pdf text-danger"></i>
          <div>
            <div class="fw-bold small text-light">Sheet ${p}</div>
            <div class="text-muted" style="font-size:0.7rem;">Page ${p} of ${this.totalPages}</div>
          </div>
        </div>
        <span class="badge ${isCurrent ? 'bg-info text-dark' : 'bg-secondary'}">${p}</span>
      `;
      item.addEventListener('click', () => {
        this.renderPage(p);
        this.updateSheetSelector();
        const el = document.getElementById('status-active-sheet');
        if (el) el.textContent = `Sheet ${p} of ${this.totalPages}`;
      });
      container.appendChild(item);
    }

    const el = document.getElementById('status-active-sheet');
    if (el) el.textContent = `Sheet ${this.currentPage} of ${this.totalPages}`;
  }
}
