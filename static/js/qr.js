document.addEventListener('DOMContentLoaded', ()=>{
  const chips = document.querySelectorAll('.chip');
  const inCat = document.getElementById('categoria');
  const btn = document.getElementById('btnEnviar');

  chips.forEach(ch=>{
    ch.addEventListener('click', ()=>{
      chips.forEach(x=>x.classList.remove('active'));
      ch.classList.add('active');
      inCat.value = ch.dataset.val;
      btn.disabled = false;
    });
  });

  document.getElementById('f').addEventListener('submit', async (e)=>{
    e.preventDefault();
    if(!inCat.value){
      alert('Selecciona una categoría antes de enviar.');
      return;
    }
    const fd = new FormData(e.target);
    const r = await fetch('/api/reportes', { method:'POST', body:fd });
    const j = await r.json();
    const s = document.getElementById('status');
    if(j.ok){
      s.textContent = '¡Gracias! Ticket #' + j.reporte_id;
      s.style.color = '#2e7d32';
      e.target.reset();
      chips.forEach(x=>x.classList.remove('active'));
      inCat.value = '';
      btn.disabled = true;
    }else{
      s.textContent = 'Error: ' + (j.error||'intenta de nuevo');
      s.style.color = 'crimson';
    }
  });
});
