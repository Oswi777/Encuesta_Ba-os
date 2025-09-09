// static/reportes/assets/js/utils.js

export function toSortedEntries(obj){
  return Object.entries(obj||{}).sort((a,b)=>b[1]-a[1]);
}

// chartFactory a prueba de fallos: si Chart no existe o hay error, no detiene el flujo
export function chartFactory(canvasEl, cfg){
  try{
    if(!canvasEl) return null;
    // Evita re-crear encima
    if(canvasEl.__chart && typeof canvasEl.__chart.destroy === 'function'){
      canvasEl.__chart.destroy();
    }
    // Chart puede no estar en window si CDN falló
    if(typeof window === 'undefined' || typeof window.Chart === 'undefined'){
      return null;
    }
    canvasEl.__chart = new window.Chart(canvasEl, cfg);
    return canvasEl.__chart;
  }catch(e){
    // No romper la app por una gráfica
    console.error('chartFactory error:', e);
    return null;
  }
}

// Mini helper por si se requiere
function $(id){ return document.getElementById(id); }
export { $ };
