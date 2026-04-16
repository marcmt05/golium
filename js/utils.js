'use strict';

function norm(s){
  return (s||'').toLowerCase()
    .replace(/\b(fc|af|sc|ac|cd|rc|ud|ca|cf|afc|fk|sk|bv|sv|ssc|as|ss|1\.)\b/g,'')
    .replace(/[^a-z0-9]/g,'').trim();
}


function cleanName(raw){
  if(!raw) return '?';
  let s = String(raw);
  // Cut at any of these patterns that indicate garbage from HTML stripping
  const cutAt = [
    /\s+[VDEWD]\s+[VDEWD]/,       // form letters like "V E D E"
    /\s+Clasificaci/i,              // "Clasificación"
    /\s+Análisis/i,                 // "Análisis"
    /\s+Estado\s+de/i,              // "Estado de Forma"
    /\s*\(\d{3,4}\.\d\)/,           // "(1627.0)" fuerza
    /\s+\d+\s+[VED]\s/,             // "15 V E"
  ];
  for(const re of cutAt){
    const m = s.search(re);
    if(m > 0) s = s.slice(0, m);
  }
  return s.trim().replace(/\s+/g,' ');
}


function clamp(v, lo, hi){ return Math.max(lo, Math.min(hi, v)); }


function avgOr(v, fallback){
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}


function fair(p){return p>0?(100/p).toFixed(2):'∞';}

function mktOdd(p,mg){const mp=p/(1+mg/100);return mp>0?(1/mp).toFixed(2):'∞';}

function edge(p,mg){return((p-p/(1+mg/100))*100).toFixed(1);}

function posC(pos){if(!pos) return '';if(pos===1) return 'p1';if(pos<=4) return 'p4';if(pos<=6) return 'p6';if(pos>=18) return 'p18';if(pos>=17) return 'p17';return '';}


function setStatus(st,txt){
  document.getElementById('pill').className='pill '+st;
  document.getElementById('dotEl').className='dot '+st;
  document.getElementById('pillTxt').textContent=txt;
}


function toast(msg,type='info',dur=3500){
  const el=document.createElement('div');
  el.className=`toast ${type}`;
  el.innerHTML=`<span>${{success:'✅',error:'❌',warning:'⚠️',info:'ℹ️'}[type]}</span><span>${msg}</span>`;
  document.getElementById('toastC').appendChild(el);
  setTimeout(()=>{el.style.animation='ti .3s ease reverse';setTimeout(()=>el.remove(),300);},dur);
}


Object.assign(window,{norm,cleanName,clamp,avgOr,fair,mktOdd,edge,posC,setStatus,toast});
