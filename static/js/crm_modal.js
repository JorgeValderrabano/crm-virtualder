/* =========================================================
   CRM — modales de nuevo / editar cliente + proyectos
   ========================================================= */

// HTML reutilizable para los campos del formulario
function camposFormularioCliente(datos = {}) {
  const d = {
    id: "", nombre: "", compania: "", puesto: "", sitio_web: "",
    telefono: "", email: "", venta_estimada: "", ultimo_contacto: "",
    proximo_contacto: "", accion: "", lead_status: "", lead_source: "",
    status_pago: "", requiere_contrato: false,
    fecha_entrega_preliminar: "", fecha_pago: "", fecha_info_entregada: "",
    contrato_tiene: false, notas: "",
    ...datos
  };

  const leadStatusOpts = window.LISTAS.lead_status || [];
  const leadSourceOpts = window.LISTAS.lead_source || [];
  const accionesOpts = window.LISTAS.acciones || [];
  const statusPagoOpts = window.LISTAS.status_pago || [];

  const opt = (val, cur) => `<option value="${val}" ${val === cur ? 'selected' : ''}>${val}</option>`;

  return `
    <div class="form-row">
      <div class="field">
        <label>Nombre *</label>
        <input name="nombre" value="${esc(d.nombre)}" required>
      </div>
      <div class="field">
        <label>Compañía</label>
        <input name="compania" value="${esc(d.compania)}">
      </div>
      <div class="field">
        <label>Puesto</label>
        <input name="puesto" value="${esc(d.puesto)}">
      </div>
      <div class="field">
        <label>Sitio web</label>
        <input name="sitio_web" value="${esc(d.sitio_web)}">
      </div>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Teléfono</label>
        <input name="telefono" value="${esc(d.telefono)}">
      </div>
      <div class="field">
        <label>Email</label>
        <input name="email" value="${esc(d.email)}">
      </div>
      <div class="field">
        <label>Venta estimada</label>
        <input name="venta_estimada" type="number" step="0.01" value="${esc(d.venta_estimada)}">
      </div>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Último contacto</label>
        <input name="ultimo_contacto" type="date" value="${fechaISO(d.ultimo_contacto)}">
      </div>
      <div class="field">
        <label>Próximo contacto</label>
        <input name="proximo_contacto" type="date" value="${fechaISO(d.proximo_contacto)}">
      </div>
      <div class="field">
        <label>Acción</label>
        <select name="accion">
          <option value="">—</option>
          ${accionesOpts.map(o => opt(o, d.accion)).join('')}
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Veces contactado</label>
        <input name="veces_contactado" type="number" min="0" step="1" value="${esc(d.veces_contactado)}">
      </div>
      <div class="field">
        <label>Lead status</label>
        <select name="lead_status">
          <option value="">—</option>
          ${leadStatusOpts.map(o => opt(o, d.lead_status)).join('')}
        </select>
      </div>
      <div class="field">
        <label>Fuente del lead</label>
        <select name="lead_source">
          <option value="">—</option>
          ${leadSourceOpts.map(o => opt(o, d.lead_source)).join('')}
        </select>
      </div>
      <div class="field">
        <label>Status de pago</label>
        <select name="status_pago">
          <option value="">—</option>
          ${statusPagoOpts.map(o => opt(o, d.status_pago)).join('')}
        </select>
      </div>
    </div>
    <div class="divider"></div>
    <div class="form-row">
      <div class="field">
        <label>Fecha entrega preliminar (borrador)</label>
        <input name="fecha_entrega_preliminar" type="date" value="${fechaISO(d.fecha_entrega_preliminar)}">
      </div>
      <div class="field">
        <label>Fecha de pago del cliente</label>
        <input name="fecha_pago" type="date" value="${fechaISO(d.fecha_pago)}">
      </div>
      <div class="field">
        <label>Fecha info. entregada</label>
        <input name="fecha_info_entregada" type="date" value="${fechaISO(d.fecha_info_entregada)}">
      </div>
    </div>
    <div class="form-row">
      <div class="field-check">
        <input type="checkbox" name="requiere_contrato" id="req_contrato" ${d.requiere_contrato ? 'checked' : ''}>
        <label for="req_contrato">Requiere contrato</label>
      </div>
      <div class="field">
        <label>${d.contrato_tiene ? 'Reemplazar contrato' : 'Adjuntar contrato'} (PDF, etc.)</label>
        <input name="contrato" type="file" accept=".pdf,.doc,.docx,.jpg,.png">
      </div>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Notas</label>
        <textarea name="notas" rows="2">${esc(d.notas)}</textarea>
      </div>
    </div>
    <div style="font-size:12.5px;color:var(--texto-suave);background:var(--crema);padding:10px 14px;border-radius:8px;">
      📦 La <strong>fecha de entrega final</strong> se calcula automáticamente:
      el más reciente entre pago e información entregada <strong>+ 30 días hábiles</strong>
      (sin sábados, domingos ni feriados mexicanos).
    </div>
  `;
}

function abrirModalNuevo() {
  const html = `
    <h2>＋ Nuevo cliente</h2>
    <form id="form-cliente" method="post" action="${window.ROUTES.crear}" enctype="multipart/form-data">
      ${camposFormularioCliente()}
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="cerrarModal()">Cancelar</button>
        <button type="submit" class="btn btn-primary">Guardar cliente</button>
      </div>
    </form>`;
  abrirModal(html);
}

function abrirModalEditar(cid) {
  // Capturar filtros actuales para preservarlos al guardar
  const filtros = window.location.search;
  const apiUrl = `/api/cliente/${cid}`;
  fetch(apiUrl)
    .then(r => r.json())
    .then(d => {
      if (d.error) { alert(d.error); return; }
      d.contrato_tiene = !!d.contrato_path;
      const formAction = `/crm/${cid}/editar`;
      // Cargar proyectos del cliente
      fetch(`/api/cliente/${cid}/proyectos`)
        .then(r => r.json())
        .then(proyectos => {
          d.proyectos = proyectos;
          const html = `
            <h2>Editar cliente</h2>
            ${d.contrato_path ? `<div class="tag-attach" style="margin-bottom:12px;">📎 Contrato actual: <a href="${window.ROUTES.uploads}/${d.contrato_path}" target="_blank">ver</a></div>` : ''}
            <form id="form-cliente" method="post" action="${formAction}" enctype="multipart/form-data">
              <input type="hidden" name="_filtros" value="${esc(filtros.replace(/^\?/, ''))}">
              ${camposFormularioCliente(d)}
              <div class="divider"></div>
              <h3 style="margin:20px 0 10px">Proyectos</h3>
              <div id="proyectos-lista" style="margin-bottom:12px;">
                ${proyectos.length === 0 ? '<p style="color:var(--texto-suave);font-size:14px;">Sin proyectos registrados.</p>' : ''}
                ${proyectos.map(p => `
                  <div class="proyecto-item" data-pid="${p.id}" style="background:var(--crema);padding:10px 14px;border-radius:8px;margin-bottom:8px;border:1px solid var(--borde);">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                      <strong>${esc(p.nombre)}</strong>
                      <button type="button" class="btn btn-danger btn-sm" onclick="eliminarProyecto(${p.id}, ${cid})" style="padding:2px 8px;font-size:12px;">✕</button>
                    </div>
                    <div style="font-size:13px;color:var(--texto-suave);display:flex;gap:16px;flex-wrap:wrap;margin-top:4px;">
                      <span>💰 ${esc(p.monto || '—')}</span>
                      <span>📅 Entrega: ${p.fecha_entrega_final || '—'}</span>
                      <span>🏷 ${esc(p.servicio || '—')}</span>
                    </div>
                  </div>
                `).join('')}
              </div>
              <button type="button" class="btn btn-ghost btn-sm" onclick="mostrarFormProyecto(${cid})" style="margin-bottom:16px;">＋ Agregar proyecto</button>
              <div id="proyecto-nuevo-form" style="display:none;background:var(--fondo);padding:12px 16px;border-radius:8px;border:1px solid var(--borde);margin-bottom:16px;">
                <h4 style="margin:0 0 8px;font-size:14px;">Nuevo proyecto</h4>
                <div class="form-row">
                  <div class="field">
                    <label>Nombre del proyecto *</label>
                    <input name="proyecto_nombre" id="proyecto_nombre" placeholder="Ej: Landing Page Rediseño">
                  </div>
                  <div class="field">
                    <label>Servicio</label>
                    <input name="proyecto_servicio" id="proyecto_servicio" placeholder="Ej: Diseño Web">
                  </div>
                </div>
                <div class="form-row">
                  <div class="field">
                    <label>Monto</label>
                    <input name="proyecto_monto" id="proyecto_monto" type="number" step="0.01">
                  </div>
                  <div class="field">
                    <label>Fecha entrega final</label>
                    <input name="proyecto_fecha_entrega" id="proyecto_fecha_entrega" type="date">
                  </div>
                  <div class="field">
                    <label>Status</label>
                    <select name="proyecto_status" id="proyecto_status">
                      <option value="">—</option>
                      <option value="En progreso">En progreso</option>
                      <option value="Entregado">Entregado</option>
                      <option value="Pendiente">Pendiente</option>
                      <option value="Cancelado">Cancelado</option>
                    </select>
                  </div>
                </div>
                <div style="display:flex;gap:8px;margin-top:8px;">
                  <button type="button" class="btn btn-primary btn-sm" onclick="guardarProyecto(${cid})">Guardar proyecto</button>
                  <button type="button" class="btn btn-ghost btn-sm" onclick="ocultarFormProyecto()">Cancelar</button>
                </div>
              </div>
              <div class="modal-actions">
                <button type="button" class="btn btn-ghost" onclick="cerrarModal()">Cancelar</button>
                <button type="submit" class="btn btn-primary">Guardar cambios</button>
              </div>
            </form>`;
          abrirModal(html);
        })
        .catch(() => {
          // Si falla proyectos, mostrar el modal sin esa sección
          const html = `
            <h2>Editar cliente</h2>
            ${d.contrato_path ? `<div class="tag-attach" style="margin-bottom:12px;">📎 Contrato actual: <a href="${window.ROUTES.uploads}/${d.contrato_path}" target="_blank">ver</a></div>` : ''}
            <form id="form-cliente" method="post" action="${formAction}" enctype="multipart/form-data">
              <input type="hidden" name="_filtros" value="${esc(filtros.replace(/^\?/, ''))}">
              ${camposFormularioCliente(d)}
              <div class="modal-actions">
                <button type="button" class="btn btn-ghost" onclick="cerrarModal()">Cancelar</button>
                <button type="submit" class="btn btn-primary">Guardar cambios</button>
              </div>
            </form>`;
          abrirModal(html);
        });
    })
    .catch(err => alert("Error al cargar: " + err.message));
}

function limpiarFiltros() {
  window.location.href = window.location.pathname;
}

function mostrarFormProyecto(cid) {
  document.getElementById('proyecto-nuevo-form').style.display = 'block';
}

function ocultarFormProyecto() {
  document.getElementById('proyecto-nuevo-form').style.display = 'none';
}

function guardarProyecto(cid) {
  const nombre = document.getElementById('proyecto_nombre').value.trim();
  if (!nombre) { alert('El nombre del proyecto es obligatorio.'); return; }
  const data = new FormData();
  data.append('nombre', nombre);
  data.append('servicio', document.getElementById('proyecto_servicio').value.trim());
  data.append('monto', document.getElementById('proyecto_monto').value);
  data.append('fecha_entrega_final', document.getElementById('proyecto_fecha_entrega').value);
  data.append('status', document.getElementById('proyecto_status').value);

  fetch(`/crm/${cid}/proyecto/nuevo`, { method: 'POST', body: data })
    .then(r => {
      if (!r.ok) throw new Error('Error al guardar');
      return r.json();
    })
    .then(p => {
      // Agregar el proyecto visualmente
      const cont = document.getElementById('proyectos-lista');
      const empty = cont.querySelector('p');
      if (empty) cont.innerHTML = '';
      const div = document.createElement('div');
      div.className = 'proyecto-item';
      div.style.cssText = 'background:var(--crema);padding:10px 14px;border-radius:8px;margin-bottom:8px;border:1px solid var(--borde);';
      div.dataset.pid = p.id;
      div.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <strong>${esc(p.nombre)}</strong>
          <button type="button" class="btn btn-danger btn-sm" onclick="eliminarProyecto(${p.id}, ${cid})" style="padding:2px 8px;font-size:12px;">✕</button>
        </div>
        <div style="font-size:13px;color:var(--texto-suave);display:flex;gap:16px;flex-wrap:wrap;margin-top:4px;">
          <span>💰 ${esc(p.monto || '—')}</span>
          <span>📅 Entrega: ${p.fecha_entrega_final || '—'}</span>
          <span>🏷 ${esc(p.servicio || '—')}</span>
        </div>`;
      cont.appendChild(div);
      ocultarFormProyecto();
      document.getElementById('proyecto_nombre').value = '';
      document.getElementById('proyecto_servicio').value = '';
      document.getElementById('proyecto_monto').value = '';
      document.getElementById('proyecto_fecha_entrega').value = '';
      document.getElementById('proyecto_status').value = '';
    })
    .catch(err => alert('Error al guardar proyecto: ' + err.message));
}

function eliminarProyecto(pid, cid) {
  if (!confirm('¿Eliminar este proyecto?')) return;
  fetch(`/crm/proyecto/${pid}/eliminar`, { method: 'POST' })
    .then(r => {
      if (!r.ok) throw new Error('Error al eliminar');
      const item = document.querySelector(`.proyecto-item[data-pid="${pid}"]`);
      if (item) item.remove();
      const cont = document.getElementById('proyectos-lista');
      if (cont && cont.children.length === 0) {
        cont.innerHTML = '<p style="color:var(--texto-suave);font-size:14px;">Sin proyectos registrados.</p>';
      }
    })
    .catch(err => alert('Error al eliminar proyecto: ' + err.message));
}

// ----- utilidades locales -----
function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/"/g, '"').replace(/</g, '<');
}
function fechaISO(f) {
  if (!f) return "";
  // Acepta dd/mm/yyyy o yyyy-mm-dd
  const m = String(f).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (m) return `${m[3]}-${m[2]}-${m[1]}`;
  if (/^\d{4}-\d{2}-\d{2}/.test(f)) return f.slice(0, 10);
  return "";
}

// Exponer variables desde la plantilla
window.ROUTES = window.ROUTES || {};
window.LISTAS = window.LISTAS || {};