// Reusa el estilo de chips/validación del QR y añade selección de baño
document.addEventListener('DOMContentLoaded', async ()=>{
  const grid = document.getElementById('banos_grid');
  const sinRes = document.getElementById('sin_resultados');
  const selZona = document.getElementById('f_zona');
  const selSexo = document.getElementById('f_sexo');
  const q = document.getElementById('q');
  const btnReset = document.getElementById('reset');

  const secForm = document.getElementById('sec_form');
  const idBano = document.getElementById('id_bano');
  const banoSel = document.getElementById('bano_sel');
  const btnCambiar = document.getElementById('cambiar');

  const chips = [];
  document.querySelectorAll('.chip').forEach(ch => chips.push(ch));
  const inCat = document.getElementById('categoria');
  const btnEnviar = document.getElementById('btnEnviar');

  // Estado
  let catBanos = [];   // catálogo
  let filtrados = [];  // lista visible

  // Carga catálogo
  async function cargarBanos(){
    const r = await fetch('/api/banos');
    catBanos = await r.json();      // [{id, nombre, zona, piso, sexo, ...}]
    // Zonas al selector
    const zonas = Array.from(new Set(catBanos.map(b=>b.zona).filter(Boolean))).sort();
    zonas.forEach(z=>{
      const o=document.createElement('option');
      o.value=z; o.textContent=z;
      selZona.appendChild(o);
    });
    render();
  }

  // Render grid
  function render(){
    const term = (q.value||'').toLowerCase().trim();
    const fz = selZona.value;
    const fs = selSexo.value;

    filtrados = catBanos.filter(b=>{
      if(fz && b.zona !== fz) return false;
      if(fs && b.sexo !== fs) return false;
      if(term){
        const hay = (b.nombre||'').toLowerCase().includes(term)
                 || (b.id||'').toLowerCase().includes(term)
                 || (b.piso||'').toLowerCase().includes(term)
                 || (b.zona||'').toLowerCase().includes(term);
        if(!hay) return false;
      }
      return true;
    });

    grid.innerHTML = '';
    filtrados.forEach(b=>{
      const div = document.createElement('button');
      div.type = 'button';
      div.className = 'kiosk-item';
      div.innerHTML = `
        <b>${b.nombre}</b>
        <small>${b.zona || '—'} · Piso ${b.piso || '—'} · ${b.sexo || '—'} · <code>${b.id}</code></small>
      `;
      div.addEventListener('click', ()=> seleccionarBano(b));
      grid.appendChild(div);
    });

    sinRes.classList.toggle('hidden', filtrados.length>0);
  }

  function seleccionarBano(b){
    idBano.value = b.id;
    banoSel.textContent = `${b.nombre} (${b.id})`;
    // mostrar form
    secForm.classList.remove('hidden');
    // scroll al form
    secForm.scrollIntoView({behavior:'smooth', block:'start'});
  }

  // Filtros
  q.addEventListener('input', render);
  selZona.addEventListener('change', render);
  selSexo.addEventListener('change', render);
  btnReset.addEventListener('click', ()=>{
    q.value=''; selZona.value=''; selSexo.value='';
    render();
  });

  // Cambiar baño
  btnCambiar.addEventListener('click', ()=>{
    idBano.value = '';
    banoSel.textContent = '—';
    secForm.classList.add('hidden');
    window.scrollTo({top:0, behavior:'smooth'});
  });

  // Chips de categoría (igual que QR)
  chips.forEach(ch=>{
    ch.addEventListener('click', ()=>{
      chips.forEach(x=>x.classList.remove('active'));
      ch.classList.add('active');
      inCat.value = ch.dataset.val;
      btnEnviar.disabled = false;
    });
  });

  // Envío
  document.getElementById('f').addEventListener('submit', async (e)=>{
    e.preventDefault();
    if(!idBano.value){ alert('Selecciona un baño'); return; }
    if(!inCat.value){ alert('Selecciona una categoría'); return; }
    const fd = new FormData(e.target);
    const r = await fetch('/api/reportes', { method:'POST', body:fd });
    const j = await r.json();
    const s = document.getElementById('status');
    if(j.ok){
      s.textContent = '¡Gracias! Ticket #' + j.reporte_id;
      s.style.color = '#2e7d32';
      // limpiar para siguiente persona
      e.target.reset();
      chips.forEach(x=>x.classList.remove('active'));
      inCat.value = '';
      btnEnviar.disabled = true;
      // mantenemos el baño seleccionado para agilizar múltiples reportes
      s.scrollIntoView({behavior:'smooth', block:'center'});
    }else{
      s.textContent = 'Error: ' + (j.error||'intenta de nuevo');
      s.style.color = 'crimson';
    }
  });

  // Go!
  cargarBanos();
});
