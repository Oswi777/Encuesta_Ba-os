import { toSortedEntries, chartFactory, $ } from './utils.js';

async function cargar(){
  const q = new URLSearchParams();
  const desde = $('desde').value;
  const hasta = $('hasta').value;
  const zona  = $('f_zona').value;
  const bano  = $('f_bano').value;
  if(desde) q.append('desde', desde);
  if(hasta) q.append('hasta', hasta);
  if(zona)  q.append('zona', zona);
  if(bano)  q.append('id_bano', bano);

  const r = await fetch(`${window.REPORTES_CFG.apiKpis}?${q.toString()}`);
  const j = await r.json();

  // KPIs
  $('k_total').textContent = j.total_reportes || 0;
  $('k_abiertos').textContent = j.abiertos || 0;
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

  // Tabla por baño
  const cont = $('tbl_bano');
  cont.innerHTML = `<div><b>Baño</b></div><div><b>Total</b></div>`;
  Object.entries(j.por_bano||{}).sort((a,b)=>b[1]-a[1]).forEach(([idb, v])=>{
    const nombre = (j.banos_catalogo && j.banos_catalogo[idb] && j.banos_catalogo[idb].nombre) || idb;
    cont.innerHTML += `<div>${nombre}</div><div style="text-align:right">${v}</div>`;
  });
}

async function initFiltros(){
  const r = await fetch(window.REPORTES_CFG.apiBanos);
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

document.addEventListener('DOMContentLoaded', ()=>{
  $('refrescar').addEventListener('click', cargar);
  initFiltros().then(cargar);
});
