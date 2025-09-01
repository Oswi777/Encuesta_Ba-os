// static/reportes/assets/js/reportes.js
import { toSortedEntries, chartFactory } from './utils.js';

function $(id){ return document.getElementById(id); }

// ------------------ Persistencia de filtros ------------------
const STORAGE_KEY = 'reportes.filters.v1';
let H = { page:1, pages:1, per_page:10 }; // paginación

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "";

// Fechas utilitarias
function pad2(n){ return n < 10 ? '0'+n : ''+n; }
function toYMD(d){ return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`; }
function today(){ return new Date(); }
function daysAgo(n){ const d = new Date(); d.setDate(d.getDate()-n); return d; }

// Lee filtros guardados; si no hay, devuelve null
function loadSavedFilters(){
  try{
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  }catch{ return null; }
}

// Guarda los filtros actuales
function saveFilters(filters){
  try{
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  }catch{}
}

// Toma los valores del UI
function readFiltersFromUI(){
  return {
    desde: $('desde').value || '',
    hasta: $('hasta').value || '',
    zona:  $('f_zona').value || '',
    bano:  $('f_bano').value || ''
  };
}

// Aplica filtros al UI (si el option no existe aún, se quedará vacío y se ajustará tras initFiltros)
function applyFiltersToUI(f){
  if(f.desde) $('desde').value = f.desde;
  if(f.hasta) $('hasta').value = f.hasta;
  if(f.zona !== undefined) $('f_zona').value = f.zona;
  if(f.bano !== undefined) $('f_bano').value = f.bano;
}

// Asegura rango de fechas por defecto (hoy y hace 5 días) si no hay nada guardado
function ensureDefaultDatesIfEmpty(){
  const dInput = $('desde');
  const hInput = $('hasta');
  const noDesde = !dInput.value;
  const noHasta = !hInput.value;
  if(noDesde || noHasta){
    const h = toYMD(today());
    const d = toYMD(daysAgo(5));
    if(noDesde) dInput.value = d;
    if(noHasta) hInput.value = h;
  }
}

// Cuando cambie cualquier filtro, guardamos de inmediato
function wireAutoSaveFilters(){
  ['desde','hasta','f_zona','f_bano'].forEach(id=>{
    $(id).addEventListener('change', ()=>{
      saveFilters(readFiltersFromUI());
    });
  });
}

/* -------------------- Utilidades de render -------------------- */
function fmtFechaLocal(s){
  try{
    const d = new Date(String(s).replace(' ', 'T')); // tolera "YYYY-MM-DD HH:MM:SS"
    return isNaN(d) ? s : d.toLocaleString();
  }catch{ return s; }
}

/* -------------------- KPIs y Gráficas -------------------- */
async function cargarKPIsyGraficas(){
  const q = new URLSearchParams();
  const {desde, hasta, zona, bano} = readFiltersFromUI();
  if(desde) q.append('desde', desde);
  if(hasta) q.append('hasta', hasta);
  if(zona)  q.append('zona', zona);
  if(bano)  q.append('id_bano', bano);
  if(TZ)    q.append('tz', TZ);

  const r = await fetch(`/api/kpis?${q.toString()}`);
  const j = await r.json();

  // KPIs
  $('k_total').textContent = j.total_reportes || 0;
  const top = (j.top_banos||[])[0];
  $('k_top_bano').textContent = top ? `${top.nombre} (${top.total})` : '—';

  // Tendencia diaria
  const dLabels = Object.keys(j.por_dia||{}).sort();
  const dValues = dLabels.map(k=>j.por_dia[k]);
  chartFactory($('chartDia'), {
    type:'line',
    data:{ labels: dLabels, datasets: [{ label:'Reportes por día', data: dValues }]},
    options:{ responsive:true, maintainAspectRatio:false }
  });

  // Por categoría
  const catE = toSortedEntries(j.por_categoria);
  chartFactory($('chartCat'), {
    type:'bar',
    data:{ labels: catE.map(x=>x[0]), datasets: [{ label:'Total', data: catE.map(x=>x[1]) }]},
    options:{ responsive:true, maintainAspectRatio:false }
  });

  // Top baños
  const topB = j.top_banos||[];
  chartFactory($('chartBanos'), {
    type:'bar',
    data:{ labels: topB.map(x=>x.nombre), datasets: [{ label:'Total', data: topB.map(x=>x.total) }]},
    options:{ indexAxis:'y', responsive:true, maintainAspectRatio:false }
  });

  // Por zona
  const zE = toSortedEntries(j.por_zona);
  chartFactory($('chartZona'), {
    type:'doughnut',
    data:{ labels: zE.map(x=>x[0]), datasets:[{ data: zE.map(x=>x[1]) }]},
    options:{ responsive:true, maintainAspectRatio:false }
  });

  // Tabla rápida
  const cont = $('tbl_bano');
  cont.innerHTML = `<div><b>Baño</b></div><div><b>Total</b></div>`;
  Object.entries(j.por_bano||{}).sort((a,b)=>b[1]-a[1]).forEach(([idb, v])=>{
    const nombre = (j.banos_catalogo && j.banos_catalogo[idb] && j.banos_catalogo[idb].nombre) || idb;
    cont.innerHTML += `<div>${nombre}</div><div style="text-align:right">${v}</div>`;
  });
}

/* -------------------- Histórico paginado -------------------- */
async function cargarHist(){
  const q = new URLSearchParams();
  const {desde, hasta, zona, bano} = readFiltersFromUI();
  if(desde) q.append('desde', desde);
  if(hasta) q.append('hasta', hasta);
  if(zona)  q.append('zona', zona);
  if(bano)  q.append('id_bano', bano);
  if(TZ)    q.append('tz', TZ);
  q.append('page', H.page);
  q.append('per_page', H.per_page);

  const r = await fetch(`/api/reportes_list?${q.toString()}`);
  const j = await r.json();
  H.pages = j.pages || 1;

  $('hist_info').textContent =
    `Mostrando ${j.items.length ? ((H.page-1)*H.per_page+1) : 0}–${(H.page-1)*H.per_page + j.items.length} de ${j.total}`;

  const tb = $('hist_tbody');
  tb.innerHTML = '';
  (j.items || []).forEach(it=>{
    const fecha = it.creado_local || it.creado_en;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${fmtFechaLocal(fecha)}</td>
      <td>${it.categoria || '-'}</td>
      <td>${it.nombre_bano || it.id_bano}</td>
      <td>${it.zona || '-'}</td>
      <td>${it.piso || '-'}</td>
      <td>${it.sexo || '-'}</td>
      <td>${it.comentario ? it.comentario : '-'}</td>
    `;
    tb.appendChild(tr);
  });

  $('hist_prev').disabled = (H.page <= 1);
  $('hist_next').disabled = (H.page >= H.pages);
}

/* -------------------- Filtros (catálogo) -------------------- */
async function initFiltros(){
  // 1) Carga filtros guardados o establece por defecto (fechas)
  const saved = loadSavedFilters();
  if(saved){
    applyFiltersToUI(saved);
  }
  // Siempre garantizar default de fechas si están vacías
  ensureDefaultDatesIfEmpty();

  // 2) Carga catálogo de baños y zonas y aplica valores guardados si existen
  const r = await fetch('/api/banos');
  const banos = await r.json();
  const zonas = Array.from(new Set(banos.map(b=>b.zona).filter(Boolean))).sort();

  const selZ = $('f_zona');
  zonas.forEach(z=>{
    const o = document.createElement('option');
    o.value = z; o.textContent = z;
    selZ.appendChild(o);
  });

  const selB = $('f_bano');
  banos.forEach(b=>{
    const o = document.createElement('option');
    o.value = b.id; o.textContent = b.nombre;
    selB.appendChild(o);
  });

  // Re-aplicar (por si las opciones aún no existían al principio)
  if(saved){
    if(saved.zona) selZ.value = saved.zona;
    if(saved.bano) selB.value = saved.bano;
  }

  // 3) Ya con opciones en DOM, guarda el estado “actual” para persistir
  saveFilters(readFiltersFromUI());
}

/* -------------------- Init -------------------- */
document.addEventListener('DOMContentLoaded', ()=>{
  // Botones Prev/Next del histórico
  $('hist_prev')?.addEventListener('click', async ()=>{
    if(H.page > 1){ H.page--; await cargarHist(); }
  });
  $('hist_next')?.addEventListener('click', async ()=>{
    if(H.page < H.pages){ H.page++; await cargarHist(); }
  });

  // Botón Actualizar: guarda y recarga con filtros actuales
  $('refrescar').addEventListener('click', async ()=>{
    saveFilters(readFiltersFromUI());
    await cargarKPIsyGraficas();
    H.page = 1;
    await cargarHist();
  });

  // Guardado automático al cambiar filtros
  wireAutoSaveFilters();

  // Primer render
  initFiltros().then(async ()=>{
    await cargarKPIsyGraficas();
    await cargarHist();
  });
});
