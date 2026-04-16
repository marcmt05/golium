'use strict';

const MARKET_NAMES = {
  '1': 'Victoria local',
  'X': 'Empate',
  '2': 'Victoria visitante',
  'O2.5': 'Over 2.5',
  'U2.5': 'Under 2.5',
  'O3.5': 'Over 3.5',
  'U3.5': 'Under 3.5',
  'BTTS_Y': 'BTTS Sí',
  'BTTS_N': 'BTTS No',
  'AH_HOME_-0.5': 'AH Local -0.5',
  'AH_AWAY_-0.5': 'AH Visitante -0.5',
};

function buildCard(fix){
  const probs = getFixtureProbs(fix);
  const picks = findPicksForFixture(fix.id);
  const realOdds = hasRealOddsForFixture(fix.id);
  const ds=fix.date?new Date(fix.date).toLocaleString('es-ES',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'?';

  const tags=[];
  tags.push({l:realOdds?'Cuotas reales integradas':'Model pick · Sin cuota real integrada',c:'data'});

  const hName=cleanName(fix.homeTeam?.name);
  const aName=cleanName(fix.awayTeam?.name);

  const mktRows = Object.entries(probs)
    .filter(([,v]) => v > 0)
    .sort((a,b)=>b[1]-a[1]);

  const picksHtml = picks.slice(0,4).map(p=>{
    const kind = p.pick_type === 'value_bet' ? 'Value bet real' : 'Model pick';
    const aux = p.pick_type === 'value_bet'
      ? `edge ${(Number(p.edge||0)*100).toFixed(2)}% · EV ${(Number(p.ev||0)*100).toFixed(2)}% · cuota ${p.offered_odds?.toFixed?.(2) || p.offered_odds}`
      : 'Predicción del modelo';
    return `<div class="vc">${p.market} · ${kind}<span class="ve">${aux}</span></div>`;
  }).join('');

  const el=document.createElement('div');
  el.className='mc';
  el.innerHTML=`
    <div class="ch">
      <span class="cdt">${ds} · <strong>J${fix.matchday||'?'}</strong></span>
      <div class="tagrow">${tags.map(t=>`<span class="tag t${t.c}">${t.l}</span>`).join('')}</div>
    </div>
    <div class="cb">
      <div class="team"><div class="tn">${hName}</div></div>
      <div class="vsb">
        <div class="vs">VS</div>
        <div class="mid">#${fix.id}</div>
      </div>
      <div class="team aw"><div class="tn">${aName}</div></div>
    </div>
    <div class="xgrow">
      <span class="xgh">xG local: ${Number(fix?.model?.lambda_home || 0).toFixed(2)}</span>
      <span style="font-size:9px;color:var(--text4)">GOLES ESPERADOS (ENGINE)</span>
      <span class="xga">xG visita: ${Number(fix?.model?.lambda_away || 0).toFixed(2)}</span>
    </div>
    <div class="mktgrid">${mktRows.map(([k,v])=>`
      <div class="mkt">
        <div class="mkt-key">${k} · ${MARKET_NAMES[k]||k}</div>
        <div class="mkt-p">${v.toFixed(1)}%</div>
      </div>`).join('')}</div>
    ${picksHtml ? `<div class="vbanner"><div class="vlbl">Picks del engine</div>${picksHtml}</div>` : ''}
  `;
  return el;
}

function renderFixtures(){
  const g=document.getElementById('grid');
  if(!S.fixtures.length){
    g.innerHTML=`<div class="estate"><div class="eico">📅</div><div class="etitle">Sin fixtures</div></div>`;
    return;
  }
  g.innerHTML='';
  S.fixtures.forEach((f,i)=>{const c=buildCard(f);c.style.animationDelay=`${i*.06}s`;g.appendChild(c);});
}

function renderStandings(){
  const c=document.getElementById('standC');
  const rows=(S.raw?.standings||[]).sort((a,b)=>a.position-b.position);
  if(!rows.length){c.innerHTML=`<div class="estate"><div class="eico">🏆</div><div class="etitle">Sin clasificación</div></div>`;return;}
  c.innerHTML = `<div style="overflow-x:auto"><table class="stbl"><thead><tr><th>#</th><th>Equipo</th><th class="n">PJ</th><th class="n">Pts</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.position}</td><td>${r.teamName}</td><td class="n">${r.played}</td><td class="n">${r.points}</td></tr>`).join('')}</tbody></table></div>`;
}

function renderDebug(){
  const c=document.getElementById('debugContent');
  if(!c) return;
  const met=S.metrics?.global||{};
  const info=S.modelInfo||{};
  c.textContent=[
    '=== ENGINE MODEL ===',
    `Snapshot: ${info.snapshot_id||'n/a'}`,
    `Version: ${info.model_version||'n/a'}`,
    `Generated: ${info.generated_at||'n/a'}`,
    `Pick mode: ${info.pick_mode||'n/a'}`,
    `Picks: ${(S.picks||[]).length}`,
    `ROI: ${met.roi!=null?(met.roi*100).toFixed(2)+'%':'n/a'}`,
  ].join('\n');
}

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
