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
  let picksPayload = { picks: [] };
  let metricsPayload = {};
  let modelInfoPayload = {};
  try{
    const base = 'public-data';
    const [resData, resPicks, resMetrics, resModelInfo] = await Promise.all([
      fetch(`${base}/data.json?_=${Date.now()}`).catch(()=>null),
      fetch(`${base}/picks.json?_=${Date.now()}`).catch(()=>null),
      fetch(`${base}/metrics.json?_=${Date.now()}`).catch(()=>null),
      fetch(`${base}/model-info.json?_=${Date.now()}`).catch(()=>null),
    ]);
    const res = (resData && resData.ok) ? resData : await fetch('data.json?_='+Date.now());
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    json = await res.json();
    if(resPicks?.ok) picksPayload = await resPicks.json();
    if(resMetrics?.ok) metricsPayload = await resMetrics.json();
    if(resModelInfo?.ok) modelInfoPayload = await resModelInfo.json();
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
    S.picks = Array.isArray(picksPayload?.picks) ? picksPayload.picks : [];
    S.metrics = metricsPayload || {};
    S.modelInfo = modelInfoPayload || {};
    if(manual) toast('Datos recargados ✓','success');
  }catch(processErr){
    console.error('Error en process():', processErr);
    setStatus('err','Error interno');
    toast(`Error procesando datos: ${processErr.message}`,'error',6000);
  }
}


Object.assign(window,{findStand,findForm,buildLookup,process,switchLeague,updateLeagueSelector,calcAvg,load});
