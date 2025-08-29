// static/reportes/assets/js/reportes.js
import { toSortedEntries, chartFactory } from './utils.js';

function $(id){ return document.getElementById(id); }

// Estado de paginación para el histórico
let H = { page:1, pages:1, per_page:10 };

// Detecta zona horaria del cliente (e.g., "America/Monterrey")
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "";

/* -------------------- Utilidades -------------------- */
function fmtFechaLocal(s){
  // Preferimos un ISO con offset (creado_local) para que el browser formatee bien.
  try{
    const d = new Date(s.replace(' ', 'T')); // tolera "YYYY-MM-DD HH:MM:SS" si viene así
    return isNaN(d) ? s : d.toLocaleString();
  }catch{ return s; }
}

/* -------------------- KPIs y Gráficas -------------------- */
async function cargarKPIsyGraficas(){
  const q = new URLSearchParams();
  const desde = $('desde').value;
  const hasta = $('hasta').value;
  const zona  = $('f_zona').value;
  const bano  = $('f_bano').value;
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

  // Tendencia diaria (por fecha local ya calculada en backend)
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

  // Top baños (barras horizontales)
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
  const desde = $('desde').value;
  const hasta = $('hasta').value;
  const zona  = $('f_zona').value;
  const bano  = $('f_bano').value;
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
    const fecha = it.creado_local || it.creado_en; // backend debe mandar creado_local (ISO con offset)
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

  // Botón Actualizar
  $('refrescar').addEventListener('click', async ()=>{
    await cargarKPIsyGraficas();
    H.page = 1;
    await cargarHist();
  });

  // Primer render
  initFiltros().then(async ()=>{
    await cargarKPIsyGraficas();
    await cargarHist();
  });
});
