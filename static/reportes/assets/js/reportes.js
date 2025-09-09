// static/reportes/assets/js/reportes.js
import { toSortedEntries, chartFactory } from './utils.js';

function $(id){ return document.getElementById(id); }

// ------------------ Persistencia y estado ------------------
const STORAGE_KEY = 'reportes.filters.v1';
const AR_KEY = 'reportes.autorefresh.v1';
let H = { page:1, pages:1, per_page:10 };     // paginación
let AUTO = { enabled:false, interval:10 };    // autorefresh
let autoTimer = null;
let isRefreshing = false;

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "";

// ------------------ Utilidades de fecha ------------------
function pad2(n){ return n < 10 ? '0'+n : ''+n; }
function toYMD(d){ return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`; }
function today(){ return new Date(); }
function daysAgo(n){ const d = new Date(); d.setDate(d.getDate()-n); return d; }

// ------------------ Persistencia filtros ------------------
function loadSavedFilters(){
  try{ const raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : null; }catch{ return null; }
}
function saveFilters(filters){
  try{ localStorage.setItem(STORAGE_KEY, JSON.stringify(filters)); }catch{}
}
function readFiltersFromUI(){
  return {
    desde: $('desde')?.value || '',
    hasta: $('hasta')?.value || '',
    zona:  $('f_zona')?.value || '',
    bano:  $('f_bano')?.value || ''
  };
}
function anyFiltersActive(f){
  const x = f || readFiltersFromUI();
  return !!(x.desde || x.hasta || x.zona || x.bano);
}
function applyFiltersToUI(f){
  if(f.desde && $('desde')) $('desde').value = f.desde;
  if(f.hasta && $('hasta')) $('hasta').value = f.hasta;
  if(f.zona !== undefined && $('f_zona')) $('f_zona').value = f.zona;
  if(f.bano !== undefined && $('f_bano')) $('f_bano').value = f.bano;
}
function ensureDefaultDatesIfEmpty(){
  const dInput = $('desde'), hInput = $('hasta');
  const noDesde = dInput && !dInput.value, noHasta = hInput && !hInput.value;
  if(noDesde || noHasta){
    const h = toYMD(today()), d = toYMD(daysAgo(5));
    if(noDesde) dInput.value = d;
    if(noHasta) hInput.value = h;
  }
}
function normalizeDateRange(){
  const dInput = $('desde'), hInput = $('hasta');
  if(dInput && hInput && dInput.value && hInput.value && dInput.value > hInput.value){
    const tmp = dInput.value; dInput.value = hInput.value; hInput.value = tmp;
  }
}
function wireAutoSaveFilters(){
  ['desde','hasta','f_zona','f_bano'].forEach(id=>{
    const el = $(id); if(!el) return;
    el.addEventListener('change', ()=> saveFilters(readFiltersFromUI()));
  });
}

// ------------------ Auto-refresh (persistencia + UI) ------------------
function loadAR(){
  try{
    const raw = localStorage.getItem(AR_KEY);
    if(raw){ const j = JSON.parse(raw); AUTO.enabled=!!j.enabled; AUTO.interval=clampInt(j.interval??10,5,300); }
  }catch{}
}
function saveAR(){ try{ localStorage.setItem(AR_KEY, JSON.stringify(AUTO)); }catch{} }
function clampInt(v,min,max){ v=parseInt(v||0,10); if(isNaN(v)) v=min; return Math.max(min, Math.min(max, v)); }
function applyARtoUI(){
  if($('auto_toggle')) $('auto_toggle').checked = !!AUTO.enabled;
  if($('auto_interval')) $('auto_interval').value = AUTO.interval;
}
function readARfromUI(){
  const en = $('auto_toggle')?.checked || false;
  const it = clampInt($('auto_interval')?.value ?? AUTO.interval, 5, 300);
  AUTO = { enabled: en, interval: it };
  saveAR();
}
function stopAuto(){
  if(autoTimer){ clearInterval(autoTimer); autoTimer=null; }
}
function startAuto(){
  stopAuto();
  if(!AUTO.enabled) return;
  autoTimer = setInterval(()=>{
    if(document.hidden) return; // pausa si pestaña oculta
    refreshAll();               // evita solapamiento interno
  }, AUTO.interval * 1000);
}

// ------------------ Render helpers ------------------
function fmtFechaLocal(s){
  try{
    const iso = String(s).includes('T') ? String(s) : String(s).replace(' ', 'T');
    const d = new Date(iso);
    return isNaN(d) ? s : d.toLocaleString();
  }catch{ return s; }
}
function setHint(msg){ const el=$('filters_hint'); if(el) el.textContent = msg || ''; }

// ------------------ Carga de datos ------------------
async function cargarKPIsyGraficas(){
  try{
    normalizeDateRange();
    const q = new URLSearchParams();
    const {desde, hasta, zona, bano} = readFiltersFromUI();
    if(desde) q.append('desde', desde);
    if(hasta) q.append('hasta', hasta);
    if(zona)  q.append('zona', zona);
    if(bano)  q.append('id_bano', bano);
    if(TZ)    q.append('tz', TZ);

    const r = await fetch(`/api/kpis?${q.toString()}`);
    const j = await r.json();

    $('k_total').textContent = j.total_reportes || 0;
    const top = (j.top_banos||[])[0];
    $('k_top_bano').textContent = top ? `${top.nombre} (${top.total})` : '—';

    const dLabels = Object.keys(j.por_dia||{}).sort();
    const dValues = dLabels.map(k=>j.por_dia[k]);
    chartFactory($('chartDia'), {
      type:'line',
      data:{ labels: dLabels, datasets: [{ label:'Reportes por día', data: dValues }]},
      options:{ responsive:true, maintainAspectRatio:false }
    });

    const catE = toSortedEntries(j.por_categoria);
    chartFactory($('chartCat'), {
      type:'bar',
      data:{ labels: catE.map(x=>x[0]), datasets: [{ label:'Total', data: catE.map(x=>x[1]) }]},
      options:{ responsive:true, maintainAspectRatio:false }
    });

    const topB = j.top_banos||[];
    chartFactory($('chartBanos'), {
      type:'bar',
      data:{ labels: topB.map(x=>x.nombre), datasets: [{ label:'Total', data: topB.map(x=>x.total) }]},
      options:{ indexAxis:'y', responsive:true, maintainAspectRatio:false }
    });

    const zE = toSortedEntries(j.por_zona);
    chartFactory($('chartZona'), {
      type:'doughnut',
      data:{ labels: zE.map(x=>x[0]), datasets:[{ data: zE.map(x=>x[1]) }]},
      options:{ responsive:true, maintainAspectRatio:false }
    });

    if((j.total_reportes||0) === 0 && anyFiltersActive()){
      setHint('Sin resultados con los filtros actuales. Prueba “Limpiar filtros”.');
    }else{
      setHint('');
    }
    return j;
  }catch(err){
    console.error('KPIs error:', err);
    setHint('Hubo un error al cargar gráficas, pero el historial seguirá funcionando.');
    return null;
  }
}

async function cargarHist(){
  try{
    normalizeDateRange();
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

    const info = $('hist_info');
    if(info){
      info.textContent =
        `Mostrando ${j.items.length ? ((H.page-1)*H.per_page+1) : 0}–${(H.page-1)*H.per_page + j.items.length} de ${j.total}`;
    }

    const tb = $('hist_tbody');
    if(tb){
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
    }

    const prev = $('hist_prev'), next = $('hist_next');
    if(prev) prev.disabled = (H.page <= 1);
    if(next) next.disabled = (H.page >= H.pages);

    const f = readFiltersFromUI();
    if((j.total||0) === 0 && anyFiltersActive(f)){
      setHint('Sin resultados con los filtros actuales. Prueba “Limpiar filtros”.');
    }else if((j.total||0) === 0){
      setHint('Aún no hay respuestas registradas.');
    }else{
      setHint('');
    }
  }catch(err){
    console.error('Hist error:', err);
    setHint('No se pudo cargar el historial.');
  }
}

// ------------------ Ciclo de actualización ------------------
async function refreshAll(){
  if(isRefreshing) return;       // evita solapamiento
  isRefreshing = true;
  try{
    await Promise.allSettled([cargarKPIsyGraficas()]);
    await cargarHist();
  }finally{
    isRefreshing = false;
  }
}

// ------------------ Inicialización ------------------
async function initFiltros(){
  const saved = loadSavedFilters();
  if(saved){ applyFiltersToUI(saved); }
  ensureDefaultDatesIfEmpty();
  normalizeDateRange();

  const r = await fetch('/api/banos');
  const banos = await r.json();
  const zonas = Array.from(new Set(banos.map(b=>b.zona).filter(Boolean))).sort();

  const selZ = $('f_zona');
  if(selZ){
    zonas.forEach(z=>{
      const o = document.createElement('option');
      o.value = z; o.textContent = z;
      selZ.appendChild(o);
    });
    if(saved && saved.zona) selZ.value = saved.zona;
  }

  const selB = $('f_bano');
  if(selB){
    banos.forEach(b=>{
      const o = document.createElement('option');
      o.value = b.id; o.textContent = b.nombre;
      selB.appendChild(o);
    });
    if(saved && saved.bano) selB.value = saved.bano;
  }

  saveFilters(readFiltersFromUI());
}

function clearFilters(){
  try{ localStorage.removeItem(STORAGE_KEY); }catch{}
  if($('f_zona')) $('f_zona').value = '';
  if($('f_bano')) $('f_bano').value = '';
  if($('desde')) $('desde').value = toYMD(daysAgo(5));
  if($('hasta')) $('hasta').value = toYMD(today());
  saveFilters(readFiltersFromUI());
}

document.addEventListener('visibilitychange', ()=>{
  // no reiniciamos timers aquí; usamos la guarda document.hidden en el tick
});

document.addEventListener('DOMContentLoaded', ()=>{
  // Botones Prev/Next
  $('hist_prev')?.addEventListener('click', async ()=>{
    if(H.page > 1){ H.page--; await cargarHist(); }
  });
  $('hist_next')?.addEventListener('click', async ()=>{
    if(H.page < H.pages){ H.page++; await cargarHist(); }
  });

  // Botón Actualizar
  $('refrescar')?.addEventListener('click', async ()=>{
    normalizeDateRange();
    saveFilters(readFiltersFromUI());
    await refreshAll();
  });

  // Botón Limpiar filtros
  $('limpiar')?.addEventListener('click', async ()=>{
    clearFilters();
    await refreshAll();
  });

  // Auto-save filtros
  wireAutoSaveFilters();

  // Auto-refresh UI & eventos
  loadAR();
  applyARtoUI();

  $('auto_toggle')?.addEventListener('change', ()=>{
    readARfromUI();
    if(AUTO.enabled){ startAuto(); refreshAll(); } else { stopAuto(); }
  });
  $('auto_interval')?.addEventListener('change', ()=>{
    readARfromUI();
    if(AUTO.enabled){ startAuto(); } // reinicia con nuevo intervalo
  });

  // Primer render + arranque auto si aplica
  initFiltros().then(async ()=>{
    await refreshAll();
    if(AUTO.enabled){ startAuto(); }
  });
});
