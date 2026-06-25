/* =========================================================
   CRM Virtualder — interacciones de la interfaz
   ========================================================= */

// ----- Utilidad de formato de moneda -----
function formatearMoneda(valor, simbolo = "$") {
  const n = Number(valor) || 0;
  return simbolo + n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ----- Helpers para abrir/cerrar modales -----
function abrirModal(html) {
  let overlay = document.getElementById("modal-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "modal-overlay";
    overlay.className = "modal-overlay";
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `<div class="modal">${html}</div>`;
  overlay.classList.add("open");
  // Cerrar al hacer clic fuera
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) cerrarModal();
  });
}

function cerrarModal() {
  const overlay = document.getElementById("modal-overlay");
  if (overlay) {
    overlay.classList.remove("open");
    overlay.innerHTML = "";
  }
}

// Cerrar con tecla Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") cerrarModal();
});

// ----- Envío de formularios dentro de modales vía fetch -----
function enviarFormModal(formId, actionUrl) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    try {
      const resp = await fetch(actionUrl, { method: "POST", body: formData });
      if (resp.ok) {
        window.location.reload();
      } else {
        alert("Hubo un problema al guardar. Revisa los campos.");
      }
    } catch (err) {
      alert("Error de conexión: " + err.message);
    }
  });
}

// ----- Confirmación de eliminación -----
function confirmarEliminar(formId, mensaje) {
  if (confirm(mensaje || "¿Eliminar este registro? Esta acción no se puede deshacer.")) {
    document.getElementById(formId).submit();
  }
  return false;
}

// ----- Badge de clase según estado de lead -----
function claseBadgeEstado(status) {
  if (!status) return "badge-default";
  const s = status.toLowerCase();
  if (s.includes("active")) return "badge-active";
  if (s.includes("won")) return "badge-won";
  if (s.includes("loss")) return "badge-loss";
  if (s.includes("cold")) return "badge-cold";
  if (s.includes("warm")) return "badge-warm";
  if (s.includes("hot")) return "badge-hot";
  if (s.includes("dev")) return "badge-dev";
  return "badge-default";
}

// Helper para leer el símbolo de moneda desde el body data
function simboloMoneda() {
  return document.body.getAttribute("data-moneda") || "$";
}
