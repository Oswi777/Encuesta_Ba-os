export function toSortedEntries(obj){
  return Object.entries(obj||{}).sort((a,b)=>b[1]-a[1]);
}
export function chartFactory(ctx, cfg){
  if(ctx.__chart){ ctx.__chart.destroy(); }
  ctx.__chart = new Chart(ctx, cfg);
  return ctx.__chart;
}
function $(id){ return document.getElementById(id); }
export { $ };
