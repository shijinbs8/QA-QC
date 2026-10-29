/**
 * 3D Volumetric MEP Viewer using Three.js
 * Renders HVAC ducts, piping systems, fire sprinklers, and equipment as true 3D meshes.
 */
class CadViewer3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.canvas = document.getElementById('three-canvas');
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.meshes = [];
    this.selectedMesh = null;
    this.drawingData = null;
    this.isInitialized = false;

    this.init();
  }

  init() {
    if (!this.container || !this.canvas) return;

    const w = this.container.clientWidth || 800;
    const h = this.container.clientHeight || 600;

    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0c1018);

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, w / h, 1, 100000);
    this.camera.position.set(12000, 16000, 12000);

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. Controls
    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 + 0.1; // allow slight under-view
    }

    // 5. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    this.scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(15000, 30000, 20000);
    dirLight1.castShadow = true;
    this.scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x00e5ff, 0.35);
    dirLight2.position.set(-15000, 10000, -15000);
    this.scene.add(dirLight2);

    // 6. Grid Helper (Floor Plan)
    const grid = new THREE.GridHelper(30000, 60, 0x00e5ff, 0x1f293d);
    grid.position.y = 0;
    this.scene.add(grid);

    // 7. Events
    window.addEventListener('resize', () => this.onResize());
    this.canvas.addEventListener('click', (e) => this.onCanvasClick(e));

    this.isInitialized = true;
    this.animate();
  }

  onResize() {
    if (!this.container || !this.renderer) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  loadData(data) {
    this.drawingData = data;
    this.clearScene();

    const prims = data.geometry && data.geometry.primitives_3d ? data.geometry.primitives_3d : [];
    const comps = data.components || [];

    // Map components by id
    const compMap = {};
    comps.forEach(c => compMap[c.id] = c);

    // Build 3D Meshes
    prims.forEach(p => {
      const compData = compMap[p.id] || {
        id: p.id,
        tag: p.tag || 'MEP-3D',
        name: p.name || 'MEP Element',
        discipline: p.discipline || 'HVAC',
        dimensions: 'Extruded from Drawing',
        material: 'Standard Engineering Specification',
        specs: p.specs || {},
        source_evidence: 'Generated from 2D Vector Drawing Coordinates'
      };

      let mesh = null;

      if (p.type === 'duct') {
        mesh = this.createDuctMesh(p);
      } else if (p.type === 'pipe') {
        mesh = this.createPipeMesh(p);
      } else if (p.type === 'equipment') {
        mesh = this.createEquipmentMesh(p);
      }

      if (mesh) {
        mesh.userData = {
          primitive: p,
          componentData: compData,
          discipline: p.discipline || compData.discipline
        };
        this.scene.add(mesh);
        this.meshes.push(mesh);
      }
    });

    // Update Disclaimer Banner
    const disclaimerBanner = document.getElementById('disclaimer-3d-text');
    if (disclaimerBanner && data.disclaimer_3d) {
      disclaimerBanner.textContent = data.disclaimer_3d;
    }

    this.setCameraView('iso_ne');
  }

  clearScene() {
    this.meshes.forEach(m => {
      this.scene.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) {
        if (Array.isArray(m.material)) m.material.forEach(mat => mat.dispose());
        else m.material.dispose();
      }
    });
    this.meshes = [];
    this.selectedMesh = null;
  }

  createDuctMesh(p) {
    const w = p.width || 600;
    const h = p.height || 350;
    const l = p.length || 1000;
    const pos = p.position || [0, 0, 2800];

    // Rectangular Duct with metallic edge outlines
    const geom = new THREE.BoxGeometry(l, h, w);
    const mat = new THREE.MeshStandardMaterial({
      color: p.color ? new THREE.Color(p.color) : 0x00b4d8,
      metalness: 0.6,
      roughness: 0.35,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.position.set(pos[0], pos[2], pos[1]);
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    // Outline edges
    const edges = new THREE.EdgesGeometry(geom);
    const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x00e5ff, linewidth: 1 }));
    mesh.add(line);

    return mesh;
  }

  createPipeMesh(p) {
    const r = (p.diameter || 80) / 2;
    const l = p.length || 800;
    const pos = p.position || [0, 0, 2750];

    const geom = new THREE.CylinderGeometry(r, r, l, 24);
    geom.rotateZ(Math.PI / 2); // align horizontal
    const mat = new THREE.MeshStandardMaterial({
      color: p.color ? new THREE.Color(p.color) : (p.discipline === 'Fire Protection' ? 0xe63946 : 0x0077b6),
      metalness: 0.5,
      roughness: 0.4,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.position.set(pos[0], pos[2], pos[1]);
    mesh.castShadow = true;

    return mesh;
  }

  createEquipmentMesh(p) {
    const subtype = (p.subtype || '').toLowerCase();
    const pos = p.position || [0, 0, 1000];
    const group = new THREE.Group();
    group.position.set(pos[0], pos[2], pos[1]);

    if (subtype.includes('ahu')) {
      // AHU Box with fan casing
      const bodyGeom = new THREE.BoxGeometry(2200, 1200, 1400);
      const bodyMat = new THREE.MeshStandardMaterial({ color: 0x3a506b, metalness: 0.4, roughness: 0.4 });
      const body = new THREE.Mesh(bodyGeom, bodyMat);
      body.position.y = 600;
      group.add(body);

      // Fan cylinder housing
      const fanGeom = new THREE.CylinderGeometry(350, 350, 400, 32);
      fanGeom.rotateX(Math.PI / 2);
      const fanMat = new THREE.MeshStandardMaterial({ color: 0x00e5ff, metalness: 0.8 });
      const fan = new THREE.Mesh(fanGeom, fanMat);
      fan.position.set(400, 600, 0);
      group.add(fan);

    } else if (subtype.includes('chiller')) {
      // Chiller Dual Shells
      const shellGeom = new THREE.CylinderGeometry(450, 450, 3000, 24);
      shellGeom.rotateZ(Math.PI / 2);
      const shellMat = new THREE.MeshStandardMaterial({ color: 0x023e8a, metalness: 0.7 });
      
      const evMesh = new THREE.Mesh(shellGeom, shellMat);
      evMesh.position.y = 500;
      group.add(evMesh);

      const cdMesh = new THREE.Mesh(shellGeom, shellMat);
      cdMesh.position.set(0, 1200, 0);
      group.add(cdMesh);

    } else if (subtype.includes('sprinkler') || subtype.includes('sp-')) {
      // Pendant Sprinkler Head
      const dropGeom = new THREE.CylinderGeometry(15, 15, 200, 16);
      const dropMat = new THREE.MeshStandardMaterial({ color: 0xe63946 });
      const drop = new THREE.Mesh(dropGeom, dropMat);
      drop.position.y = 100;
      group.add(drop);

      // Brass deflector disc
      const deflGeom = new THREE.CylinderGeometry(50, 50, 6, 16);
      const deflMat = new THREE.MeshStandardMaterial({ color: 0xffb703, metalness: 0.9, roughness: 0.2 });
      const defl = new THREE.Mesh(deflGeom, deflMat);
      defl.position.y = 0;
      group.add(defl);

    } else if (subtype.includes('pump')) {
      // Pump Base & Volute
      const baseGeom = new THREE.BoxGeometry(1100, 200, 600);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x2b2d42 });
      const base = new THREE.Mesh(baseGeom, baseMat);
      group.add(base);

      const motorGeom = new THREE.CylinderGeometry(250, 250, 600, 24);
      motorGeom.rotateZ(Math.PI / 2);
      const motorMat = new THREE.MeshStandardMaterial({ color: 0x06d6a0, metalness: 0.6 });
      const motor = new THREE.Mesh(motorGeom, motorMat);
      motor.position.set(-150, 400, 0);
      group.add(motor);

    } else {
      // Generic Equipment Enclosure
      const dims = p.dimensions || [600, 400, 400];
      const geom = new THREE.BoxGeometry(dims[0], dims[2] || 400, dims[1]);
      const mat = new THREE.MeshStandardMaterial({
        color: p.color ? new THREE.Color(p.color) : 0x4a5568,
        metalness: 0.5,
        roughness: 0.4
      });
      const box = new THREE.Mesh(geom, mat);
      box.position.y = (dims[2] || 400) / 2;
      group.add(box);
    }

    return group;
  }

  setCameraView(preset) {
    if (!this.camera || !this.controls) return;

    const target = new THREE.Vector3(7000, 1500, 5000);
    this.controls.target.copy(target);

    if (preset === 'iso_ne') {
      this.camera.position.set(16000, 14000, 16000);
    } else if (preset === 'iso_nw') {
      this.camera.position.set(-6000, 14000, 16000);
    } else if (preset === 'top') {
      this.camera.position.set(7000, 22000, 5001); // slight offset to prevent gimbal lock
    } else if (preset === 'front') {
      this.camera.position.set(7000, 2000, 22000);
    } else if (preset === 'side') {
      this.camera.position.set(22000, 2000, 5000);
    }

    this.controls.update();
  }

  filterDiscipline(discipline) {
    this.meshes.forEach(m => {
      if (discipline === 'All' || !discipline) {
        m.visible = true;
      } else {
        m.visible = m.userData.discipline === discipline;
      }
    });
  }

  onCanvasClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.meshes, true);

    if (intersects.length > 0) {
      let hitObj = intersects[0].object;
      while (hitObj.parent && !hitObj.userData.componentData && hitObj.parent !== this.scene) {
        hitObj = hitObj.parent;
      }

      if (hitObj && hitObj.userData.componentData) {
        this.selectMesh(hitObj);
        if (window.app) {
          window.app.displayComponentDetails(hitObj.userData.componentData);
        }
      }
    }
  }

  selectMesh(mesh) {
    if (this.selectedMesh) {
      this.resetMeshHighlight(this.selectedMesh);
    }
    this.selectedMesh = mesh;
    this.highlightMesh(mesh);
  }

  highlightMesh(mesh) {
    mesh.traverse(child => {
      if (child.isMesh && child.material) {
        if (!child.userData.origEmissive) {
          child.userData.origEmissive = child.material.emissive ? child.material.emissive.clone() : new THREE.Color(0);
        }
        if (child.material.emissive) {
          child.material.emissive.set(0x00e5ff);
        }
      }
    });
  }

  resetMeshHighlight(mesh) {
    mesh.traverse(child => {
      if (child.isMesh && child.material && child.userData.origEmissive) {
        child.material.emissive.copy(child.userData.origEmissive);
      }
    });
  }
}
