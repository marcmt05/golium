'use strict';

const S = {
  raw:null, fixtures:[], byId:{}, byNorm:{}, byIdH:{}, byNormH:{},
  formById:{}, formByNorm:{},
  lgH:1.45, lgA:1.15, lgHH:1.35, lgAH:1.10,
  vt:55, mg:7, tab:'f', dbg:[],
  allLeagues: {},      // { key → leagueData } cuando hay multiple ligas
  currentKey: null,    // liga activa actualmente
  cardModel: {teams:{}, fixtures:{}, referees:{}, leagueAvgTotal:3.8},
};
window.S = S;


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


'use strict';

function findStand(id, name, hyper=false){
  const [byId, byNorm_] = hyper ? [S.byIdH, S.byNormH] : [S.byId, S.byNorm];
  const sid = String(id||'');
  if(sid && byId[sid]) return byId[sid];
  if(!name) return null;
  if(byId[name]) return byId[name];
  const n = norm(name);
  if(n && byNorm_[n]) return byNorm_[n];
  let best=null, bestLen=3;
  for(const [k,v] of Object.entries(byNorm_)){
    if(k.length>=4 && n.length>=4 && (k.includes(n)||n.includes(k))){
      const l=Math.min(k.length,n.length);
      if(l>bestLen){best=v;bestLen=l;}
    }
  }
  return best;
}


function findForm(id, rawId, name){
  for(const k of [String(id||''),String(rawId||'')].filter(x=>x&&x!='undefined')){
    if(S.formById[k]?.length) return S.formById[k];
  }
  if(name){
    const n=norm(name);
    for(const [k,v] of Object.entries(S.formByNorm)){
      if(k.length>=4&&n.length>=4&&(k.includes(n)||n.includes(k))&&v?.length) return v;
    }
  }
  return [];
}


function buildLookup(standings, byId, byNorm_){
  for(const r of standings){
    const sid=String(r.teamId||''), n=norm(r.teamName||'');
    if(sid) byId[sid]=r;
    if(n) byNorm_[n]=r;
    if(r.teamName) byId[r.teamName]=r;
  }
}


function process(json, forceKey=null){
  // Guardar todas las ligas disponibles
  if(json.leagues){
    S.allLeagues = json.leagues;
    // Seleccionar liga: forced key, o la guardada, o laliga, o la primera
    const keys = Object.keys(json.leagues);
    const preferred = forceKey || S.currentKey || 'laliga';
    S.currentKey = keys.includes(preferred) ? preferred : keys[0];
  } else {
    // Fichero de una sola liga
    S.allLeagues = { [json.leagueKey||'liga']: json };
    S.currentKey = json.leagueKey || 'liga';
  }

  const d = S.allLeagues[S.currentKey];
  S.raw=d; S.fixtures=d.fixtures||[];
  S.cardModel = d.cardModel || {teams:{}, fixtures:{}, referees:{}, leagueAvgTotal:3.8};
  S.formById={}; S.formByNorm={};
  for(const [k,v] of Object.entries(d.teamForm||{})) S.formById[String(k)]=Array.isArray(v)?v:[];
  S.byId={}; S.byNorm={}; S.byIdH={}; S.byNormH={};
  buildLookup(d.standings||[], S.byId, S.byNorm);
  buildLookup(d.standingsHyper||[], S.byIdH, S.byNormH);

  // Build formByNorm index
  for(const f of S.fixtures){
    for(const side of [f.homeTeam,f.awayTeam]){
      if(!side) continue;
      const form=findForm(side.id,side.rawId,null);
      if(form.length){const n=norm(side.name||'');if(n) S.formByNorm[n]=form;}
    }
  }

  // League averages
  calcAvg(d.standings||[], 'lgH', 'lgA');
  if((d.standingsHyper||[]).length) calcAvg(d.standingsHyper, 'lgHH', 'lgAH');

  const stands=(d.standings||[]).length+(d.standingsHyper||[]).length;
  const withForm=S.fixtures.filter(f=>
    findForm(f.homeTeam?.id,f.homeTeam?.rawId,f.homeTeam?.name).length+
    findForm(f.awayTeam?.id,f.awayTeam?.rawId,f.awayTeam?.name).length>0
  ).length;

  S.dbg=[`=== DATA ===`,
    `Liga: ${d.league}  Source: ${d.source}  ScrapedAt: ${d.scrapedAt}`,
    `Fixtures: ${S.fixtures.length}  Standings: ${stands}  FormKeys: ${Object.keys(S.formById).length}`,
    `LgAvg: home=${S.lgH.toFixed(3)} away=${S.lgA.toFixed(3)}`,
    `LgAvgH2: home=${S.lgHH.toFixed(3)} away=${S.lgAH.toFixed(3)}`,
    `Fixtures with form: ${withForm}/${S.fixtures.length}`,
    `CardModel: teams=${Object.keys(S.cardModel?.teams||{}).length} refs=${Object.keys(S.cardModel?.referees||{}).length} fixtures=${Object.keys(S.cardModel?.fixtures||{}).length}`,
    ``,`=== MATCHING ===`,
    ...S.fixtures.map(f=>{
      const hs=findStand(f.homeTeam?.id,f.homeTeam?.name)||findStand(f.homeTeam?.id,f.homeTeam?.name,true);
      const as=findStand(f.awayTeam?.id,f.awayTeam?.name)||findStand(f.awayTeam?.id,f.awayTeam?.name,true);
      const hf=findForm(f.homeTeam?.id,f.homeTeam?.rawId,f.homeTeam?.name);
      const af=findForm(f.awayTeam?.id,f.awayTeam?.rawId,f.awayTeam?.name);
      return `${f.homeTeam?.name} vs ${f.awayTeam?.name}\n  H:${hs?`pos=${hs.position} pts=${hs.points}`:'NOT FOUND'} form=${hf.length}\n  A:${as?`pos=${as.position} pts=${as.points}`:'NOT FOUND'} form=${af.length}`;
    })
  ];

  const sc=d.scrapedAt?new Date(d.scrapedAt):null;
  const am=sc?Math.round((Date.now()-sc.getTime())/60000):null;
  const ags=am!=null?(am<60?`${am}min`:`${Math.round(am/60)}h`):'?';
  const agc=am!=null?(am<60?'fresh':am<360?'':'stale'):'';

  document.getElementById('guide').style.display='none';
  document.getElementById('dbanner').style.display='flex';
  document.getElementById('dSrc').textContent=sc?sc.toLocaleString('es-ES'):'?';
  document.getElementById('dLg').textContent=d.league||'—';
  document.getElementById('dFix').textContent=S.fixtures.length;
  document.getElementById('dTeams').textContent=stands;
  document.getElementById('dForm').textContent=`${withForm}/${S.fixtures.length}`;
  document.getElementById('dAge').textContent=`⏱ Hace ${ags}`;
  document.getElementById('dAge').className='age '+agc;
  document.getElementById('lgName').textContent=d.league||'—';
  document.getElementById('lastUpd').textContent=sc?`Actualizado: ${sc.toLocaleTimeString('es-ES')}`:'';

  if(am!=null&&am>360) toast(`Datos con ${ags} — re-ejecuta el scraper`,'warning',5000);
  setStatus('ok',`${d.league||'?'} · ${S.fixtures.length} partidos`);
  updateLeagueSelector();
  // Hide the static "Liga" label when selector is shown
  const keys = Object.keys(S.allLeagues);
  document.getElementById('lgLabel').style.display = keys.length>1 ? 'none' : '';
  render();
}


function switchLeague(key){
  if(!S.allLeagues[key]) return;
  S.currentKey = key;
  const d = S.allLeagues[key];
  S.raw=d; S.fixtures=d.fixtures||[];
  S.cardModel = d.cardModel || {teams:{}, fixtures:{}, referees:{}, leagueAvgTotal:3.8};
  S.formById={}; S.formByNorm={};
  for(const [k,v] of Object.entries(d.teamForm||{})) S.formById[String(k)]=Array.isArray(v)?v:[];
  S.byId={}; S.byNorm={}; S.byIdH={}; S.byNormH={};
  buildLookup(d.standings||[], S.byId, S.byNorm);
  buildLookup(d.standingsHyper||[], S.byIdH, S.byNormH);
  for(const f of S.fixtures){
    for(const side of [f.homeTeam,f.awayTeam]){
      if(!side) continue;
      const form=findForm(side.id,side.rawId,null);
      if(form.length){const n=norm(side.name||'');if(n) S.formByNorm[n]=form;}
    }
  }
  calcAvg(d.standings||[], 'lgH', 'lgA');
  document.getElementById('lgName').textContent = d.league||'—';
  updateLeagueSelector();
  render();
}


function updateLeagueSelector(){
  const sel = document.getElementById('lgSelector');
  if(!sel) return;
  const keys = Object.keys(S.allLeagues);
  if(keys.length <= 1){
    sel.style.display='none';
    return;
  }
  sel.style.display='inline-flex';
  sel.innerHTML = keys.map(k=>{
    const name = S.allLeagues[k].league||k;
    const flag = {laliga:'🇪🇸',premier:'🏴󠁧󠁢󠁥󠁮󠁧󠁿',bundesliga:'🇩🇪',seriea:'🇮🇹',ligue1:'🇫🇷',champions:'🏆',hypermotion:'🇪🇸2'}[k]||'⚽';
    return `<button onclick="switchLeague('${k}')"
      style="background:${k===S.currentKey?'var(--green)':'transparent'};
             color:${k===S.currentKey?'#000':'var(--text3)'};
             border:1px solid ${k===S.currentKey?'var(--green)':'var(--b2)'};
             font-family:var(--mono);font-size:9px;padding:4px 9px;border-radius:4px;
             cursor:pointer;letter-spacing:.5px;transition:all .15s;white-space:nowrap">
      ${flag} ${name}
    </button>`;
  }).join('');
}


function calcAvg(st, hKey, aKey){
  if(!st.length) return;
  const games=st.reduce((s,r)=>s+(r.played||0),0)/2;
  const goals=st.reduce((s,r)=>s+(r.gf||0),0)/2;
  if(games>0){
    const avg=goals/games;
    S[hKey]=Math.max(0.8,Math.min(2.2,avg*1.12));
    S[aKey]=Math.max(0.6,Math.min(1.8,avg*0.88));
  }
}


async function load(manual=false){
  if(manual){
    setStatus('load','Cargando…');
    document.getElementById('grid').innerHTML=`<div class="loader"><div class="spin"></div><div style="font-size:11px;color:var(--text3)">Cargando data.json…</div></div>`;
  } else {
    setStatus('load','Buscando datos…');
  }

  // ── Fase 1: fetch ─────────────────────────────────────────
  let json;
  try{
    const res = await fetch('data.json?_='+Date.now());
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    json = await res.json();
  }catch(fetchErr){
    // Solo mostrar error si no teníamos datos previos
    if(!S.raw){
      setStatus('err','Sin data.json');
      document.getElementById('guide').style.display='block';
      document.getElementById('dbanner').style.display='none';
      document.getElementById('jbar').style.display='none';
      document.getElementById('grid').innerHTML='';
    } else {
      setStatus('err','Error al recargar');
    }
    if(manual) toast('No se encontró data.json — ejecuta el scraper primero','error');
    return;
  }

  // ── Fase 2: procesar datos ────────────────────────────────
  try{
    process(json);
    if(manual) toast('Datos recargados ✓','success');
  }catch(processErr){
    console.error('Error en process():', processErr);
    setStatus('err','Error interno');
    toast(`Error procesando datos: ${processErr.message}`,'error',6000);
  }
}


Object.assign(window,{findStand,findForm,buildLookup,process,switchLeague,updateLeagueSelector,calcAvg,load});


'use strict';

function cardTeamKeyCandidates(team){
  const out = [];
  for(const v of [team?.id, team?.rawId, team?.name]){
    const s = String(v||'').trim();
    if(s && s !== 'undefined' && s !== 'null') out.push(s);
    const n = norm(s);
    if(n) out.push(n);
  }
  return [...new Set(out)];
}


function findCardTeam(team){
  const teams = S.cardModel?.teams || {};
  for(const k of cardTeamKeyCandidates(team)){
    if(teams[k]) return teams[k];
  }
  return null;
}


function deriveCardTeamFallback(team){
  const st = findStand(team?.id, team?.name) || findStand(team?.id, team?.name, true) || {};
  const form = findForm(team?.id, team?.rawId, team?.name).map(x => x.r || x);
  const played = Math.max(Number(st.played || form.length || 8), 5);
  const gaRate = Number(st.ga || 0) / played;
  const gfRate = Number(st.gf || 0) / played;
  const pos = Number(st.position || 10);

  const base = 1.7
    + clamp((pos - 10) / 20, -0.18, 0.22)
    + clamp((gaRate - 1.1) * 0.22, -0.14, 0.18)
    + clamp((gfRate - 1.2) * 0.08, -0.06, 0.08);

  const pts = x => x==='W' ? 3 : x==='D' ? 1 : 0;
  const recent = (form || []).slice(-6);
  const half = Math.max(2, Math.floor(recent.length / 2));
  const oldPts = recent.slice(0, half).reduce((s, x) => s + pts(x), 0);
  const newPts = recent.slice(-half).reduce((s, x) => s + pts(x), 0);
  const trend = recent.length >= 4 ? clamp((oldPts - newPts) / (half * 3) * 0.12, -0.12, 0.12) : 0;

  return {
    avgFor: clamp(base, 1.1, 2.7),
    avgAgainst: clamp(base * 0.96 + 0.08, 1.1, 2.7),
    recentFor: clamp(base * (1 + trend * 1.4), 1.0, 2.9),
    recentAgainst: clamp(base * (0.98 + trend), 1.0, 2.9),
    formTrend: trend,
    synthetic: true,
  };
}


function calcCardMarkets(fix){
  const cm = S.cardModel || {};
  const leagueAvgTotal = avgOr(cm.leagueAvgTotal, 3.8);
  const leagueAvgTeam = leagueAvgTotal / 2;
  const home = findCardTeam(fix.homeTeam) || deriveCardTeamFallback(fix.homeTeam);
  const away = findCardTeam(fix.awayTeam) || deriveCardTeamFallback(fix.awayTeam);
  const fx = (cm.fixtures||{})[String(fix.id||'')] || {};
  const refAvg = avgOr(fx.refAvgTotal, avgOr((cm.referees||{})[fx.refName]?.avgTotal, leagueAvgTotal));
  const refMult = clamp(refAvg / Math.max(leagueAvgTotal, 0.1), 0.88, 1.12);

  const homeBase = (avgOr(home.avgFor, leagueAvgTeam) + avgOr(away.avgAgainst, leagueAvgTeam)) / 2;
  const awayBase = (avgOr(away.avgFor, leagueAvgTeam) + avgOr(home.avgAgainst, leagueAvgTeam)) / 2;
  const homeRecent = (avgOr(home.recentFor, homeBase) + avgOr(away.recentAgainst, awayBase)) / 2;
  const awayRecent = (avgOr(away.recentFor, awayBase) + avgOr(home.recentAgainst, homeBase)) / 2;

  const homeTrend = clamp(Number(home.formTrend || 0), -0.18, 0.18);
  const awayTrend = clamp(Number(away.formTrend || 0), -0.18, 0.18);

  let lambdaHome = (homeBase * 0.65 + homeRecent * 0.35) * (1 + homeTrend) * refMult;
  let lambdaAway = (awayBase * 0.65 + awayRecent * 0.35) * (1 + awayTrend) * refMult;

  lambdaHome = clamp(lambdaHome, 0.18, 4.5);
  lambdaAway = clamp(lambdaAway, 0.18, 4.5);

  const pHome = 1 - Math.exp(-lambdaHome);
  const pAway = 1 - Math.exp(-lambdaAway);
  const yes = clamp(pHome * pAway, 0.02, 0.98);
  const no = clamp(1 - yes, 0.02, 0.98);

  return {
    yes, no,
    yesPct: Math.round(yes * 1000) / 10,
    noPct: Math.round(no * 1000) / 10,
    lambdaHome, lambdaAway,
    refName: fx.refName || '',
    refAvgTotal: refAvg,
  };
}



function pmf(k,λ){
  if(λ<=0) return k===0?1:0;
  let lp=-λ+k*Math.log(λ); for(let i=1;i<=k;i++) lp-=Math.log(i); return Math.exp(lp);
}

function dcTau(i,j,λ,μ,ρ=0.13){
  if(i===0&&j===0) return 1-λ*μ*ρ;
  if(i===1&&j===0) return 1+μ*ρ;
  if(i===0&&j===1) return 1+λ*ρ;
  if(i===1&&j===1) return 1-ρ; return 1;
}

function matrix(λ,μ,N=7){
  const m=[];
  for(let i=0;i<N;i++){const row=[];for(let j=0;j<N;j++){
    let p=pmf(i,λ)*pmf(j,μ);if(i<=1&&j<=1) p*=dcTau(i,j,λ,μ);row.push(p);
  }m.push(row);}
  const tot=m.flat().reduce((s,v)=>s+v,0);
  for(let i=0;i<N;i++) for(let j=0;j<N;j++) m[i][j]/=tot;
  return m;
}


function mkts(m){
  const N=m.length;
  let h=0,d=0,a=0,ov25=0,un25=0,ov35=0,un35=0,bt=0,c00=0,c10=0,c01=0,c11=0;
  let ahHomeMinus05=0, ahAwayPlus05=0, ahAwayMinus05=0, ahHomePlus05=0;
  for(let i=0;i<N;i++) for(let j=0;j<N;j++){
    const p=m[i][j];
    if(i>j) h+=p; else if(i===j) d+=p; else a+=p;
    if(i+j>2) ov25+=p; else un25+=p;
    if(i+j>3) ov35+=p; else un35+=p;
    if(i>0&&j>0) bt+=p;
    if(i===0&&j===0) c00+=p;
    if(i===1&&j===0) c10+=p;
    if(i===0&&j===1) c01+=p;
    if(i===1&&j===1) c11+=p;
    if(i>j) ahHomeMinus05+=p;
    if(j>=i) ahAwayPlus05+=p;
    if(j>i) ahAwayMinus05+=p;
    if(i>=j) ahHomePlus05+=p;
  }
  return{
    h,d,a,
    ov25,un25,ov35,un35,
    bt,c00,c10,c01,c11,
    ahHomeMinus05,ahAwayPlus05,ahAwayMinus05,ahHomePlus05,
  };
}


function formMult(form){
  const r=(form||[]).slice(-6).reverse(); // [más reciente → más antiguo]
  if(!r.length) return 1.0;
  let pts=0, maxW=0;
  r.forEach((x,i)=>{
    const w = Math.exp(-0.22*i); // decay: w0=1.0, w5≈0.33
    pts  += (x==='W'?3:x==='D'?1:0)*w;
    maxW += 3*w;
  });
  return 0.93 + (pts/maxW)*0.14; // [0.93, 1.07]
}


function calcMomentum(form){
  const r = (form||[]).slice(-6); // [más antiguo → más reciente]
  if(r.length < 4) return {value:0, label:'', mult:1.0};

  const pts = x => x==='W'?3:x==='D'?1:0;
  const half   = Math.floor(r.length/2);
  const ptsOld = r.slice(0, half).reduce((s,x)=>s+pts(x), 0); // 3 más antiguos
  const ptsNew = r.slice(-half).reduce((s,x)=>s+pts(x), 0);   // 3 más recientes
  const maxPts = half * 3; // máximo teórico (9 pts)

  // delta: -1 (caída libre) → 0 (estable) → +1 (remontada)
  const delta = (ptsNew - ptsOld) / maxPts;

  // Mult reducido [0.96, 1.04] para no solapar con formMult
  const mult = Math.max(0.96, Math.min(1.04, 1.0 + delta*0.04));

  // Umbral de label: solo mostrar si la tendencia es clara (|delta|≥0.33)
  // i.e. diferencia de al menos 3 puntos sobre 9 posibles
  let label = '';
  if     (delta >=  0.44) label = '🚀 En racha';
  else if(delta >=  0.22) label = '📈 Mejorando';
  else if(delta <= -0.44) label = '📉 En caída';
  else if(delta <= -0.22) label = '⬇ Bajando';

  return {value:delta, label, mult};
}


function lambdas(hd,ad,lgH,lgA){
  const hn=Math.max(hd.n,5), an=Math.max(ad.n,5);

  // Si tenemos split home/away, usarlos — son más precisos
  // hd.gfH = goles marcados EN CASA; ad.gaA = goles encajados FUERA
  const hAttH = hd.gfH>0 ? (hd.gfH/Math.max(hd.nH,3)/lgH) : (hd.gf/hn/lgH);
  const hDefH = hd.gaH>0 ? (hd.gaH/Math.max(hd.nH,3)/lgA) : (hd.ga/hn/lgA);
  const aAttA = ad.gfA>0 ? (ad.gfA/Math.max(ad.nA,3)/lgA) : (ad.gf/an/lgA);
  const aDefA = ad.gaA>0 ? (ad.gaA/Math.max(ad.nA,3)/lgH) : (ad.ga/an/lgH);

  let λ = lgH * hAttH * aDefA * formMult(hd.form) * hd.momentum.mult;
  let μ = lgA * aAttA * hDefH * formMult(ad.form) * ad.momentum.mult;

  // Posición: corrección suave tanh
  const pd=(hd.pos||10)-(ad.pos||10);
  λ*=1+Math.tanh(-pd/15)*0.07;
  μ*=1+Math.tanh( pd/15)*0.07;

  return{λ:Math.max(0.2,Math.min(4.5,λ)), μ:Math.max(0.2,Math.min(4.5,μ))};
}


function kelly(prob, oddDecimal){
  const p = prob/100;
  const q = 1-p;
  const b = oddDecimal - 1;
  if(b <= 0) return 0;
  const f = (b*p - q) / b;
  return Math.max(0, Math.round(f/4*1000)/10); // fraccional 25%, en %
}


function matchData(fix, isHyper=false){
  const hs =findStand(fix.homeTeam?.id,fix.homeTeam?.name,isHyper)||
             findStand(fix.homeTeam?.id,fix.homeTeam?.name,!isHyper)||{};
  const as_=findStand(fix.awayTeam?.id,fix.awayTeam?.name,isHyper)||
             findStand(fix.awayTeam?.id,fix.awayTeam?.name,!isHyper)||{};
  const hfr=findForm(fix.homeTeam?.id,fix.homeTeam?.rawId,fix.homeTeam?.name);
  const afr=findForm(fix.awayTeam?.id,fix.awayTeam?.rawId,fix.awayTeam?.name);
  const hForm=hfr.length?hfr.map(x=>x.r):deriveForm(hs);
  const aForm=afr.length?afr.map(x=>x.r):deriveForm(as_);

  // Momentum individual
  const hMom = calcMomentum(hForm);
  const aMom = calcMomentum(aForm);

  // Goles: intentar usar split home/away si disponible en standings
  const lgH=isHyper?S.lgHH:S.lgH, lgA=isHyper?S.lgAH:S.lgA;
  const played = hs.played||10;
  const aPlayed = as_.played||10;
  const halfH = Math.round(played/2); // aprox partidos en casa
  const halfA = Math.round(aPlayed/2);

  // home/away split desde standings (si ESPN los devolvió)
  const hGFH = hs.gfHome>0 ? hs.gfHome : (hs.gf>0 ? Math.round(hs.gf*0.58) : lgH*halfH);
  const hGAH = hs.gaHome>0 ? hs.gaHome : (hs.ga>0 ? Math.round(hs.ga*0.45) : lgA*halfH);
  const aGFA = as_.gfAway>0 ? as_.gfAway : (as_.gf>0 ? Math.round(as_.gf*0.42) : lgA*halfA);
  const aGAA = as_.gaAway>0 ? as_.gaAway : (as_.ga>0 ? Math.round(as_.ga*0.55) : lgH*halfA);

  // Fallback form-based cuando hay suficientes partidos
  const hGF=hfr.length>=4?hfr.reduce((s,m)=>s+m.gf,0):(hs.gf||(isHyper?S.lgHH:S.lgH)*(played));
  const hGA=hfr.length>=4?hfr.reduce((s,m)=>s+m.ga,0):(hs.ga||(isHyper?S.lgAH:S.lgA)*(played));
  const aGF=afr.length>=4?afr.reduce((s,m)=>s+m.gf,0):(as_.gf||(isHyper?S.lgAH:S.lgA)*(aPlayed));
  const aGA=afr.length>=4?afr.reduce((s,m)=>s+m.ga,0):(as_.ga||(isHyper?S.lgHH:S.lgH)*(aPlayed));
  const hN=Math.max(hfr.length||played,5);
  const aN=Math.max(afr.length||aPlayed,5);

  const{λ,μ}=lambdas(
    {gf:hGF,ga:hGA,n:hN,form:hForm,pos:hs.position||10,momentum:hMom,
     gfH:hGFH,gaH:hGAH,nH:halfH},
    {gf:aGF,ga:aGA,n:aN,form:aForm,pos:as_.position||10,momentum:aMom,
     gfA:aGFA,gaA:aGAA,nA:halfA},
    lgH,lgA
  );
  const m=mkts(matrix(λ,μ));
  const p=v=>Math.round(v*1000)/10;
  return{hs,as_,hForm,aForm,real:hfr.length>0||afr.length>0,λ,μ,
    hMom, aMom,
    p:{
      h:p(m.h),d:p(m.d),a:p(m.a),
      ov:p(m.ov25),un:p(m.un25),
      ov35:p(m.ov35),un35:p(m.un35),
      bt:p(m.bt),
      c00:p(m.c00),c10:p(m.c10),c01:p(m.c01),c11:p(m.c11),
      ahHomeMinus05:p(m.ahHomeMinus05),
      ahAwayPlus05:p(m.ahAwayPlus05),
      ahAwayMinus05:p(m.ahAwayMinus05),
      ahHomePlus05:p(m.ahHomePlus05),
    }};
}

function deriveForm(s){
  if(!s||!s.played) return [];
  const n=Math.min(s.played,6),pW=(s.wins||0)/Math.max(s.played,1),pD=(s.draws||0)/Math.max(s.played,1);
  return Array.from({length:n},()=>{const r=Math.random();return r<pW?'W':r<pW+pD?'D':'L';}).reverse();
}

Object.assign(window,{cardTeamKeyCandidates,findCardTeam,deriveCardTeamFallback,calcCardMarkets,pmf,dcTau,matrix,mkts,formMult,calcMomentum,lambdas,kelly,matchData,deriveForm});


'use strict';

function buildCard(fix){
  const isHyper=!!(findStand(fix.homeTeam?.id,fix.homeTeam?.name,true)&&(S.raw?.standingsHyper||[]).length>0);
  const{hs,as_,hForm,aForm,real,λ,μ,hMom,aMom,p}=matchData(fix,isHyper);
  const vt=S.vt, mg=S.mg;

  const markets=[
    {key:'1',         name:'Victoria local',   v:p.h},
    {key:'X',         name:'Empate',           v:p.d},
    {key:'2',         name:'Victoria visita',  v:p.a},
    {key:'O2.5',      name:'Over 2.5 goles',   v:p.ov},
    {key:'U2.5',      name:'Under 2.5 goles',  v:p.un},
    {key:'O3.5',      name:'Over 3.5 goles',   v:p.ov35},
    {key:'U3.5',      name:'Under 3.5 goles',  v:p.un35},
    {key:'BTTS',      name:'Ambos marcan',     v:p.bt},
    {key:'AHH-0.5',   name:'AH Local -0.5',    v:p.ahHomeMinus05},
    {key:'AHA+0.5',   name:'AH Visita +0.5',   v:p.ahAwayPlus05},
    {key:'AHA-0.5',   name:'AH Visita -0.5',   v:p.ahAwayMinus05},
    {key:'AHH+0.5',   name:'AH Local +0.5',    v:p.ahHomePlus05},
  ];

  const vals=markets.filter(m=>m.v>=vt);
  const fin=(fix.status||'').includes('FINAL')||(fix.status||'').includes('FULL');
  const ds=fix.date?new Date(fix.date).toLocaleString('es-ES',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'?';

  const tags=[];
  if(vals.length>=2) tags.push({l:'⚡ VALUE BET',c:'v'});
  if(isHyper) tags.push({l:'2ª DIV',c:'rel'});
  if((hs.position||10)<=4) tags.push({l:'Champions(L)',c:'eur'});
  if((as_.position||10)<=4) tags.push({l:'Champions(V)',c:'eur'});
  if((hs.position||10)>=17) tags.push({l:'Descenso(L)',c:'rel'});
  if((as_.position||10)>=17) tags.push({l:'Descenso(V)',c:'rel'});
  tags.push({l:real?'● Forma real':'○ Estimada',c:'data'});

  const hName=cleanName(fix.homeTeam?.name);
  const aName=cleanName(fix.awayTeam?.name);
  const fh=arr=>(arr||[]).slice(-6).map(r=>`<div class="fp ${r}">${r}</div>`).join('');
  const momBadge=mom=>mom.label?`<span style="font-size:9px;color:${mom.value>0?'var(--green)':'var(--red)'}"> ${mom.label}</span>`:'';

  const el=document.createElement('div');
  el.className='mc';
  el.innerHTML=`
    <div class="ch">
      <span class="cdt">${ds} · <strong>J${fix.matchday||'?'}</strong></span>
      <div class="tagrow">${tags.map(t=>`<span class="tag t${t.c}">${t.l}</span>`).join('')}</div>
    </div>
    <div class="cb">
      <div class="team">
        <div class="tn">${hName}${momBadge(hMom)}</div>
        <div class="ti"><span class="tpos ${posC(hs.position)}">${hs.position||'?'}</span><span>${hs.points??'?'} pts</span><span style="color:var(--text4)">·</span><span>${hs.gf??'?'}GF ${hs.ga??'?'}GA</span></div>
        <div class="fstrip">${fh(hForm)}</div>
      </div>
      <div class="vsb">
        ${fin&&fix.homeScore!=null?`<div class="score-d">${fix.homeScore}–${fix.awayScore}</div>`:`<div class="vs">VS</div>`}
        <div class="mid">#${fix.id}</div>
      </div>
      <div class="team aw">
        <div class="tn">${momBadge(aMom)}${aName}</div>
        <div class="ti"><span>${as_.gf??'?'}GF ${as_.ga??'?'}GA</span><span style="color:var(--text4)">·</span><span>${as_.points??'?'} pts</span><span class="tpos ${posC(as_.position)}">${as_.position||'?'}</span></div>
        <div class="fstrip">${fh(aForm)}</div>
      </div>
    </div>
    <div class="xgrow">
      <span class="xgh">xG local: ${λ.toFixed(2)}</span>
      <span style="font-size:9px;color:var(--text4)">GOLES ESPERADOS</span>
      <span class="xgtot">${(λ+μ).toFixed(2)}</span>
      <span style="font-size:9px;color:var(--text4)">TOTAL</span>
      <span class="xga">xG visita: ${μ.toFixed(2)}</span>
    </div>
    <div class="psec">
      <div class="prow"><span class="pk">1 X 2</span><div class="pt">
        <div class="pb h${p.h>p.a?' dom':''}" style="width:${p.h}%">${p.h}%</div>
        <div class="pb d" style="width:${p.d}%">${p.d}%</div>
        <div class="pb a${p.a>p.h?' dom':''}" style="width:${p.a}%">${p.a}%</div>
      </div></div>
      <div class="prow"><span class="pk">O/U 2.5</span><div class="pt">
        <div class="pb ov" style="width:${p.ov}%">Over ${p.ov}%</div>
        <div class="pb un" style="width:${p.un}%">Under ${p.un}%</div>
      </div></div>
      <div class="prow"><span class="pk">O/U 3.5</span><div class="pt">
        <div class="pb ov" style="width:${p.ov35}%">Over ${p.ov35}%</div>
        <div class="pb un" style="width:${p.un35}%">Under ${p.un35}%</div>
      </div></div>
    </div>
    <div class="mktgrid">${markets.map(m=>{
      const isVal=m.v>=vt, isMod=m.v>=vt-8&&!isVal;
      const f=fair(m.v), mk=mktOdd(m.v,mg), eg=edge(m.v/100,mg);
      const k=kelly(m.v,parseFloat(mk));
      return `<div class="mkt ${isVal?'val':isMod?'mod':''}">
        <div class="mkt-key">${m.key} · ${m.name}</div>
        <div class="mkt-p">${m.v}%</div>
        <div class="mkt-odds"><span class="mkt-fair">${f}</span><span class="mkt-mkt">≈ ${mk}</span></div>
        ${isVal?`<div class="mkt-edge">edge +${eg}% · Kelly ${k}%</div>`:''}
      </div>`;
    }).join('')}</div>
    ${vals.length?`<div class="vbanner"><div class="vlbl">⚡ Value bets</div>${vals.slice(0,4).map(v=>{
      const k=kelly(v.v,parseFloat(mktOdd(v.v,mg)));
      return `<div class="vc">${v.key}: ${v.v}% → ${fair(v.v)}<span class="ve"> edge +${edge(v.v/100,mg)}%${k>0?' · Kelly '+k+'%':''}</span></div>`;
    }).join('')}</div>`:''}
  `;
  return el;
}


function renderFixtures(){
  const g=document.getElementById('grid');
  if(!S.fixtures.length){
    g.innerHTML=`<div class="estate"><div class="eico">📅</div><div class="etitle">Sin fixtures</div><div class="esub">Ejecuta: <code>python scraper.py laliga</code> o <code>python scraper.py worldcup</code></div></div>`;
    return;
  }
  g.innerHTML='';
  S.fixtures.forEach((f,i)=>{const c=buildCard(f);c.style.animationDelay=`${i*.06}s`;g.appendChild(c);});
}


function renderStandings(){
  const c=document.getElementById('standC');
  const rows=(S.raw?.standings||[]).sort((a,b)=>a.position-b.position);
  const rowsH=(S.raw?.standingsHyper||[]).sort((a,b)=>a.position-b.position);
  if(!rows.length&&!rowsH.length){c.innerHTML=`<div class="estate"><div class="eico">🏆</div><div class="etitle">Sin clasificación</div></div>`;return;}

  const bc=p=>p===1?'c1':p<=4?'ucl':p<=6?'uel':p>=18?'dn':p>=16?'rel':'';
  const fmH=(id,name)=>{const f=findForm(id,null,name);if(!f.length) return '<span style="color:var(--text4);font-size:9px">—</span>';return `<div class="fm2">${f.slice(-5).map(x=>`<div class="fm ${x.r||x}">${x.r||x}</div>`).join('')}</div>`;};
  const tblHtml=(rows,title)=>{
    if(!rows.length) return '';
    return `<div style="margin-bottom:14px;font-family:var(--head);font-size:26px;letter-spacing:2px">${title}</div>
    <div style="overflow-x:auto;margin-bottom:24px">
    <table class="stbl"><thead><tr>
      <th>#</th><th>Equipo</th><th class="n">PJ</th><th class="n">G</th><th class="n">E</th><th class="n">P</th>
      <th class="n">GF</th><th class="n">GC</th><th class="n">DG</th><th class="n">GF/p</th><th class="n">Forma</th><th class="n">Pts</th>
    </tr></thead><tbody>
    ${rows.map(r=>`<tr>
      <td><span class="pbadge ${bc(r.position)}">${r.position}</span></td>
      <td style="font-weight:500;color:var(--text)">${r.teamName}</td>
      <td class="n">${r.played}</td><td class="n">${r.wins}</td><td class="n">${r.draws}</td><td class="n">${r.losses}</td>
      <td class="n">${r.gf}</td><td class="n">${r.ga}</td>
      <td class="n" style="color:${r.gf-r.ga>0?'var(--green)':r.gf-r.ga<0?'var(--red)':'var(--text3)'}">${r.gf-r.ga>0?'+':''}${r.gf-r.ga}</td>
      <td class="n" style="color:var(--blue)">${r.played?(r.gf/r.played).toFixed(2):'—'}</td>
      <td>${fmH(r.teamId,r.teamName)}</td>
      <td class="n"><span class="pts">${r.points}</span></td>
    </tr>`).join('')}
    </tbody></table></div>`;
  };

  c.innerHTML=tblHtml(rows,`CLASIFICACIÓN <span style="color:var(--green)">${S.raw?.league||'?'}</span>`)
            +(rowsH.length?tblHtml(rowsH,`CLASIFICACIÓN <span style="color:var(--amber)">LaLiga Hypermotion</span>`):'')
            +`<div style="margin-top:12px;font-size:9px;color:var(--text4);display:flex;gap:14px;flex-wrap:wrap">
              <span><span style="color:#ffd700">■</span> Campeón</span><span><span style="color:var(--purple)">■</span> UCL</span>
              <span><span style="color:var(--blue)">■</span> UEL</span><span><span style="color:var(--amber)">■</span> Playoff</span><span><span style="color:var(--red)">■</span> Descenso</span>
             </div>`;
}


function renderDebug(){const c=document.getElementById('debugContent');if(c) c.textContent=S.dbg.join('\n');}


function render(){renderFixtures();renderStandings();renderDebug();updateJBar();buildCombinada();}

function rerender(){if(S.raw) render();}


function updateJBar(){
  const jb=document.getElementById('jbar');
  if(!S.fixtures.length){jb.style.display='none';return;}
  jb.style.display='flex';
  document.getElementById('jnum').textContent=S.fixtures[0]?.matchday||'?';
  document.getElementById('jlg').textContent=S.raw?.league||'?';
  document.getElementById('jcnt').textContent=S.fixtures.length;
}


function go(t){
  document.querySelectorAll('.ntab').forEach(el=>el.classList.remove('on'));
  document.getElementById('tab-'+t).classList.add('on');
  ['f','s','d'].forEach(id=>{document.getElementById('t'+id).style.display=id===t?'block':'none';});
}


Object.assign(window,{buildCard,renderFixtures,renderStandings,renderDebug,render,rerender,updateJBar,go});


'use strict';

let combOpen = true;

function toggleComb(){
  combOpen = !combOpen;
  document.getElementById('combBody').style.display = combOpen ? '' : 'none';
  document.getElementById('combToggleBtn').textContent = combOpen ? '▼' : '▶';
}


function renderCombBody(legs, totalOdd, probConj, evComb, kellyComb, alts, mg, isFallback){
  const hName = f => cleanName(f.homeTeam?.name||'').split(' ').slice(0,2).join(' ');
  const aName = f => cleanName(f.awayTeam?.name||'').split(' ').slice(0,2).join(' ');
  const signColor = k => k==='1'?'var(--blue)':k==='X'?'var(--amber)':k==='2'?'var(--red)':k.startsWith('O')||k==='BTTS'?'var(--green)':'var(--text2)';

  return `
    ${isFallback?`<div style="font-size:9px;color:var(--amber);padding:6px 0 10px;border-bottom:1px solid var(--b1);margin-bottom:10px">⚠ Sin EV positivo con margen ${mg}% — mostrando selecciones por mayor probabilidad. Prueba a bajar el margen.</div>`:''}
    <div class="comb-legs">
      ${legs.map((l,i)=>`
      <div class="comb-leg ${!isFallback&&i===0?'best-leg':''}">
        <div>
          <div class="comb-match">${hName(l.fix)} vs ${aName(l.fix)}</div>
          <div style="font-size:9px;color:var(--text4);margin-top:1px">
            ${l.fix.date?new Date(l.fix.date).toLocaleDateString('es-ES',{weekday:'short',day:'numeric',month:'short'}):''}
          </div>
        </div>
        <div style="text-align:center">
          <div style="font-family:var(--head);font-size:16px;color:${signColor(l.key)}">${l.key}</div>
          <div style="font-size:9px;color:var(--text3)">${l.label}</div>
        </div>
        <div style="text-align:center">
          <div class="comb-prob">${l.prob.toFixed(1)}%</div>
          <div class="comb-odd">${l.oddMkt.toFixed(2)}</div>
        </div>
        <div class="comb-ev ${l.ev>0?'pos':'neg'}">
          EV ${l.ev>0?'+':''}${(l.ev*100).toFixed(1)}%
          <span style="display:block;font-size:7px;opacity:.7">${l.edgePct>0?'+':''}${l.edgePct}% edge</span>
        </div>
      </div>`).join('')}
    </div>

    <div class="comb-summary">
      <div class="comb-stat">
        <div class="comb-stat-lbl">Cuota total</div>
        <div class="comb-stat-val" style="color:var(--amber)">${totalOdd.toFixed(2)}</div>
        <div style="font-size:9px;color:var(--text3)">${legs.length} selecciones</div>
      </div>
      <div class="comb-stat">
        <div class="comb-stat-lbl">Probabilidad</div>
        <div class="comb-stat-val" style="color:var(--blue)">${probConj.toFixed(1)}%</div>
        <div style="font-size:9px;color:var(--text3)">prob. conjunta</div>
      </div>
      <div class="comb-stat">
        <div class="comb-stat-lbl">EV combinada</div>
        <div class="comb-stat-val" style="color:${evComb>0?'var(--green)':'var(--red)'}">
          ${evComb>0?'+':''}${(evComb*100).toFixed(1)}%
        </div>
        <div style="font-size:9px;color:var(--text3)">ganancia esperada/€</div>
      </div>
      <div class="comb-stat">
        <div class="comb-stat-lbl">Kelly ¼</div>
        <div class="comb-stat-val" style="color:${kellyComb>0?'var(--green)':'var(--text4)'}">
          ${kellyComb>0?kellyComb+'%':'—'}
        </div>
        <div style="font-size:9px;color:var(--text3)">del bankroll</div>
      </div>
      <div class="comb-stat">
        <div class="comb-stat-lbl">Retorno x100€</div>
        <div class="comb-stat-val" style="color:var(--text)">${(totalOdd*100).toFixed(0)}€</div>
        <div style="font-size:9px;color:var(--text3)">si aciertas</div>
      </div>
    </div>

    ${alts&&alts.length ? `
    <div class="comb-alts">
      <div class="comb-alts-title">💡 Alternativas</div>
      ${alts.map((alt,i)=>`
      <div class="comb-alt-row" onclick="applyCombAlt(${i})">
        <span style="font-size:9px;color:var(--text4)">Alt ${i+1}</span>
        ${alt.legs.map(l=>`
          <span style="background:var(--s2);border:1px solid var(--b1);border-radius:3px;padding:2px 7px;font-size:9px">
            <span style="color:${signColor(l.key)}">${l.key}</span>
            <span style="color:var(--text4);font-size:8px"> ${hName(l.fix).split(' ')[0]}</span>
          </span>`).join('')}
        <span style="margin-left:auto;font-family:var(--head);font-size:16px;color:var(--amber)">${alt.totalOdd.toFixed(2)}</span>
        <span style="font-size:9px;color:${alt.evComb>0?'var(--green)':'var(--red)'}">EV ${alt.evComb>0?'+':''}${(alt.evComb*100).toFixed(1)}%</span>
      </div>`).join('')}
    </div>` : ''}

    <div style="font-size:9px;color:var(--text4);margin-top:10px;border-top:1px solid var(--b1);padding-top:8px;line-height:1.7">
      ⚠ Modelo Poisson + Dixon-Coles · Margen ${mg}% · EV = ganancia esperada por €1 apostado · Combinar multiplica el riesgo.
    </div>
  `;
}


function buildCombinada(){
  const section = document.getElementById('combSection');
  const body    = document.getElementById('combBody');
  if(!S.fixtures.length){ section.style.display='none'; return; }

  const N   = parseInt(document.getElementById('combN')?.value || 3);
  const mg  = S.mg;
  const fixtures = S.fixtures.filter(f=>
    !(f.status||'').includes('FINAL') && !(f.status||'').includes('FULL')
  ).slice(0, 7); // solo próximos 7

  if(fixtures.length < 2){ section.style.display='none'; return; }
  section.style.display = '';

  // ── STEP 1: Calcular todas las selecciones candidatas ──────────
  const candidates = [];

  fixtures.forEach(fix => {
    const isHyper = !!(findStand(fix.homeTeam?.id,fix.homeTeam?.name,true)&&(S.raw?.standingsHyper||[]).length>0);
    const {p, hMom, aMom} = matchData(fix, isHyper);

    const mkt = [
      {key:'1',        label:'Victoria local',  prob:p.h,                type:'result'},
      {key:'X',        label:'Empate',          prob:p.d,                type:'result'},
      {key:'2',        label:'Victoria visita', prob:p.a,                type:'result'},
      {key:'O2.5',     label:'Over 2.5',        prob:p.ov,               type:'over'},
      {key:'U2.5',     label:'Under 2.5',       prob:p.un,               type:'under'},
      {key:'O3.5',     label:'Over 3.5',        prob:p.ov35,             type:'over'},
      {key:'U3.5',     label:'Under 3.5',       prob:p.un35,             type:'under'},
      {key:'BTTS',     label:'Ambos marcan',    prob:p.bt,               type:'btts'},
      {key:'AHH-0.5',  label:'AH Local -0.5',   prob:p.ahHomeMinus05,    type:'ah_hm'},
      {key:'AHA+0.5',  label:'AH Visita +0.5',  prob:p.ahAwayPlus05,     type:'ah_ap'},
      {key:'AHA-0.5',  label:'AH Visita -0.5',  prob:p.ahAwayMinus05,    type:'ah_am'},
      {key:'AHH+0.5',  label:'AH Local +0.5',   prob:p.ahHomePlus05,     type:'ah_hp'},
    ];

    mkt.forEach(m => {
      if(!m.prob || m.prob < 5 || m.prob > 95) return;

      // ── Cuota correcta: 100 / (prob% / (1+margin)) ──────────
      // mktOdd(p,mg) devuelve 1/(p/107) = 107/p que está en %
      // Necesitamos: 100 / (p / (1+mg/100)) = 100*(1+mg/100)/p
      const mg100 = 1 + mg/100;
      const fairOdd = 100 / m.prob;           // cuota justa
      const mktOddVal = fairOdd / mg100;       // cuota con margen casas
      if(mktOddVal < 1.01) return;

      const prob = m.prob / 100;

      // EV real del jugador contra la casa
      // EV = prob × (cuota - 1) - (1 - prob)
      const ev = prob * (mktOddVal - 1) - (1 - prob);

      // Edge = diferencia entre prob del modelo y prob implícita de la cuota
      // prob_implícita = 1 / mktOddVal
      const impliedProb = 1 / mktOddVal;
      const edgePct = Math.round((prob - impliedProb) * 1000) / 10; // en %

      // Solo incluir selecciones con EV positivo
      if(ev <= 0) return;

      // Momentum bonus: ajuste fino (±3%)
      let momBonus = 0;
      if(m.key==='1')  momBonus = (hMom?.value||0) * 0.03;
      if(m.key==='2')  momBonus = (aMom?.value||0) * 0.03;
      if(m.key==='X')  momBonus = -Math.abs((hMom?.value||0)-(aMom?.value||0)) * 0.01;

      // Score: combinación de EV normalizado + tamaño de prob (preferir probs altas)
      const score = ev + momBonus + (prob - 0.5) * 0.02;

      candidates.push({
        fix, key: m.key, label: m.label, type: m.type,
        prob: m.prob, oddMkt: mktOddVal, ev,
        edgePct, momBonus,
        score,
        fixId: fix.id || (fix.homeTeam?.name + fix.awayTeam?.name),
      });
    });
  });

  if(!candidates.length){
    // Fallback: si no hay EV positivo, mostrar las 3 selecciones con mayor prob
    // (útil cuando el margen es alto y aplana todos los EVs)
    const allCands = [];
    fixtures.forEach(fix => {
      const isHyperF = !!(findStand(fix.homeTeam?.id,fix.homeTeam?.name,true)&&(S.raw?.standingsHyper||[]).length>0);
      const {p:pf} = matchData(fix, isHyperF);
      const mktF = [
        {key:'1',label:'Victoria local',prob:pf.h,type:'result'},
        {key:'X',label:'Empate',prob:pf.d,type:'result'},
        {key:'2',label:'Victoria visita',prob:pf.a,type:'result'},
        {key:'O2.5',label:'Over 2.5',prob:pf.ov,type:'over'},
        {key:'U2.5',label:'Under 2.5',prob:pf.un,type:'under'},
        {key:'O3.5',label:'Over 3.5',prob:pf.ov35,type:'over'},
        {key:'U3.5',label:'Under 3.5',prob:pf.un35,type:'under'},
      ];
      const mg100 = 1+mg/100;
      mktF.forEach(m=>{
        if(!m.prob||m.prob<5||m.prob>95) return;
        const fairOdd=100/m.prob, mktOddVal=fairOdd/mg100;
        const prob=m.prob/100;
        const ev=prob*(mktOddVal-1)-(1-prob);
        const edgePct=Math.round((prob-1/mktOddVal)*1000)/10;
        allCands.push({fix,key:m.key,label:m.label,type:m.type,
          prob:m.prob,oddMkt:mktOddVal,ev,edgePct,momBonus:0,
          score:ev,fixId:fix.id||(fix.homeTeam?.name+fix.awayTeam?.name)});
      });
    });
    // Best per match by prob
    const bpm={};
    allCands.forEach(c=>{if(!bpm[c.fixId]||c.prob>bpm[c.fixId].prob) bpm[c.fixId]=c;});
    const fallbackLegs=Object.values(bpm).sort((a,b)=>b.prob-a.prob).slice(0,Math.min(N,Object.keys(bpm).length));
    if(!fallbackLegs.length){
      body.innerHTML='<div class="comb-no-ev">Sin fixtures disponibles.</div>'; return;
    }
    // Use fallback legs
    const {totalOdd:to,probConj:pc,evComb:evc,kellyComb:kc}=combStats_ext(fallbackLegs);
    body.innerHTML=renderCombBody(fallbackLegs,to,pc,evc,kc,[],mg,true);
    return;
  }

  // ── STEP 2: Seleccionar la mejor selección por partido ──────────
  // Agrupa por partido, queda la de mayor score
  const bestPerMatch = {};
  candidates.forEach(c => {
    if(!bestPerMatch[c.fixId] || c.score > bestPerMatch[c.fixId].score)
      bestPerMatch[c.fixId] = c;
  });
  const pool = Object.values(bestPerMatch).sort((a,b) => b.score - a.score);

  // ── STEP 3: Penalización de correlación entre selecciones ───────
  // Si ya incluimos Over2.5 de un partido, BTTS del mismo partido suma poco
  // Si ya incluimos '1' y AH local del mismo partido → redundante
  function corrPenalty(selected, candidate){
    let pen = 0;
    selected.forEach(s => {
      if(s.fixId === candidate.fixId) { pen = 1; return; } // mismo partido: excluir
      // Misma dirección en goles (over corr con btts)
      if((s.type==='over'&&candidate.type==='btts')||(s.type==='btts'&&candidate.type==='over'))
        pen += 0.15;
      // Múltiples unders
      if(s.type==='under'&&candidate.type==='under') pen += 0.1;
    });
    return Math.min(pen, 0.5);
  }

  // ── STEP 4: Greedy selection de N legs con anti-correlación ──────
  function selectLegs(pool, n){
    const selected = [];
    const remaining = [...pool];
    while(selected.length < n && remaining.length){
      // Recalcular score con penalización de correlación
      let best = null, bestAdj = -Infinity;
      remaining.forEach(c => {
        const pen = corrPenalty(selected, c);
        if(pen >= 1) return; // mismo partido ya incluido
        const adj = c.score * (1 - pen);
        if(adj > bestAdj){ bestAdj = adj; best = c; }
      });
      if(!best) break;
      selected.push(best);
      remaining.splice(remaining.indexOf(best), 1);
    }
    return selected;
  }

  const mainLegs = selectLegs(pool, Math.min(N, pool.length));

  // ── STEP 5: Calcular estadísticas de la combinada ───────────────
  function combStats(legs){
    const totalOdd = legs.reduce((p,l) => p * l.oddMkt, 1);
    const probConj = legs.reduce((p,l) => p * l.prob/100, 1) * 100;
    // EV de la combinada: EV_acum = prod(1+ev_i) - 1 aproximado
    // Más correcto: EV = prob_conjunta × (totalOdd - 1) - (1 - prob_conjunta)
    const probC = probConj/100;
    const evComb = probC * (totalOdd - 1) - (1 - probC);
    const kellyComb = Math.max(0, Math.round(
      ((probC * (totalOdd-1) - (1-probC)) / (totalOdd-1)) / 4 * 1000
    ) / 10);
    return {totalOdd, probConj, evComb, kellyComb};
  }

  const {totalOdd, probConj, evComb, kellyComb} = combStats(mainLegs);

  // ── STEP 6: Alternativas (siguiente mejor combinación) ──────────
  const alts = [];
  if(pool.length > N){
    // Alt A: quitar la peor leg de la principal y meter la siguiente
    for(let skip=mainLegs.length-1; skip>=0; skip--){
      const altPool = pool.filter(c => !mainLegs.slice(0,skip).find(l=>l.fixId===c.fixId));
      const altLegs = selectLegs(altPool, Math.min(N, altPool.length));
      if(altLegs.length === mainLegs.length){
        const diff = altLegs.filter(l=>!mainLegs.find(m=>m.fixId===l.fixId&&m.key===l.key));
        if(diff.length > 0){
          const st = combStats(altLegs);
          alts.push({legs:altLegs, ...st});
          if(alts.length >= 2) break;
        }
      }
    }
  }

  // ── RENDER ──────────────────────────────────────────────────────
  const hName = f => cleanName(f.homeTeam?.name||'').split(' ').slice(0,2).join(' ');
  const aName = f => cleanName(f.awayTeam?.name||'').split(' ').slice(0,2).join(' ');
  const evColor = ev => ev > 0 ? 'var(--green)' : 'var(--red)';
  const signColor = k => k==='1'?'var(--blue)':k==='X'?'var(--amber)':k==='2'?'var(--red)':k.startsWith('O')||k==='BTTS'?'var(--green)':'var(--text2)';

  body.innerHTML = renderCombBody(mainLegs, totalOdd, probConj, evComb, kellyComb, alts, mg, false);

  // Store alts for click handler
  window._combAlts = alts;
  window._combMainLegs = mainLegs;
}


function applyCombAlt(idx){
  // Swap main with alt — just re-render with alt legs
  const alt = window._combAlts[idx];
  if(!alt) return;
  // Temporarily swap to show it
  window._combAlts[idx] = {legs: window._combMainLegs, ...combStats_ext(window._combMainLegs)};
  window._combMainLegs = alt.legs;
  buildCombinada();
}


function combStats_ext(legs){
  const totalOdd = legs.reduce((p,l)=>p*l.oddMkt,1);
  const probC    = legs.reduce((p,l)=>p*l.prob/100,1);
  const evComb   = probC*(totalOdd-1)-(1-probC);
  const kellyComb= Math.max(0,Math.round(((probC*(totalOdd-1)-(1-probC))/(totalOdd-1))/4*1000)/10);
  return {totalOdd, probConj:probC*100, evComb, kellyComb};
}

Object.assign(window,{toggleComb,renderCombBody,buildCombinada,applyCombAlt,combStats_ext});


'use strict';

document.addEventListener('DOMContentLoaded',()=>{
  load();
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key==='r'){e.preventDefault();load(true);}
  });
});
