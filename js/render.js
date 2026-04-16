'use strict';

function buildCard(fix){
  const hs = findStand(fix.homeTeam?.id,fix.homeTeam?.name) || findStand(fix.homeTeam?.id,fix.homeTeam?.name,true) || {};
  const as_ = findStand(fix.awayTeam?.id,fix.awayTeam?.name) || findStand(fix.awayTeam?.id,fix.awayTeam?.name,true) || {};
  const hForm = findForm(fix.homeTeam?.id,fix.homeTeam?.rawId,fix.homeTeam?.name).map(x=>x.r||x);
  const aForm = findForm(fix.awayTeam?.id,fix.awayTeam?.rawId,fix.awayTeam?.name).map(x=>x.r||x);
  const probs = fixtureProbs(fix);
  const model = fixtureModel(fix);
  const marketMap = marketByKey(fix);

  const markets = [
    ['1','Victoria local',probs.h],
    ['X','Empate',probs.d],
    ['2','Victoria visita',probs.a],
    ['O2.5','Over 2.5',probs.ov25],
    ['U2.5','Under 2.5',probs.un25],
    ['O3.5','Over 3.5',probs.ov35],
    ['U3.5','Under 3.5',probs.un35],
    ['BTTS_Y','BTTS Sí',probs.bttsY],
    ['BTTS_N','BTTS No',probs.bttsN],
    ['AH_HOME_-0.5','AH Local -0.5',probs.ahHomeMinus05],
    ['AH_AWAY_-0.5','AH Visita -0.5',probs.ahAwayMinus05],
  ];

  const hasRealOdds = markets.some(([k])=>marketMap[k]?.offered_odds_is_real);
  const fin=(fix.status||'').includes('FINAL')||(fix.status||'').includes('FULL');
  const ds=fix.date?new Date(fix.date).toLocaleString('es-ES',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'?';

  const hName=cleanName(fix.homeTeam?.name);
  const aName=cleanName(fix.awayTeam?.name);
  const fh=arr=>(arr||[]).slice(-6).map(r=>`<div class="fp ${r}">${r}</div>`).join('');

  const el=document.createElement('div');
  el.className='mc';
  el.innerHTML=`
    <div class="ch">
      <span class="cdt">${ds} · <strong>J${fix.matchday||'?'}</strong></span>
      <div class="tagrow">
        <span class="tag tdata">${hasRealOdds?'VALUE BET CANDIDATES':'MODEL PICKS'}</span>
        <span class="tag tdata">${hasRealOdds?'Cuotas reales integradas':'Sin cuota real integrada'}</span>
      </div>
    </div>
    <div class="cb">
      <div class="team">
        <div class="tn">${hName}</div>
        <div class="ti"><span class="tpos ${posC(hs.position)}">${hs.position||'?'}</span><span>${hs.points??'?'} pts</span><span style="color:var(--text4)">·</span><span>${hs.gf??'?'}GF ${hs.ga??'?'}GA</span></div>
        <div class="fstrip">${fh(hForm)}</div>
      </div>
      <div class="vsb">
        ${fin&&fix.homeScore!=null?`<div class="score-d">${fix.homeScore}–${fix.awayScore}</div>`:`<div class="vs">VS</div>`}
        <div class="mid">#${fix.id}</div>
      </div>
      <div class="team aw">
        <div class="tn">${aName}</div>
        <div class="ti"><span>${as_.gf??'?'}GF ${as_.ga??'?'}GA</span><span style="color:var(--text4)">·</span><span>${as_.points??'?'} pts</span><span class="tpos ${posC(as_.position)}">${as_.position||'?'}</span></div>
        <div class="fstrip">${fh(aForm)}</div>
      </div>
    </div>
    <div class="xgrow">
      <span class="xgh">xG local: ${model.lambda_home!=null?Number(model.lambda_home).toFixed(2):'—'}</span>
      <span style="font-size:9px;color:var(--text4)">ENGINE OUTPUT</span>
      <span class="xgtot">${(Number(model.lambda_home||0)+Number(model.lambda_away||0)).toFixed(2)}</span>
      <span style="font-size:9px;color:var(--text4)">TOTAL</span>
      <span class="xga">xG visita: ${model.lambda_away!=null?Number(model.lambda_away).toFixed(2):'—'}</span>
    </div>
    <div class="mktgrid">${markets.map(([key,name,prob])=>{
      const mk=marketMap[key]||{};
      const pickType = mk.pick_type==='value_bet'?'Value bet':'Model pick';
      const oddsTxt = mk.offered_odds_is_real && mk.offered_odds!=null ? `@ ${Number(mk.offered_odds).toFixed(2)}` : 'sin cuota real';
      const edgeTxt = mk.offered_odds_is_real && mk.offered_odds!=null ? `edge ${(((prob/100)-(1/Number(mk.offered_odds)))*100).toFixed(2)}%` : 'predicción de modelo';
      return `<div class="mkt">
        <div class="mkt-key">${key} · ${name}</div>
        <div class="mkt-p">${Number(prob||0).toFixed(1)}%</div>
        <div class="mkt-odds"><span class="mkt-fair">${mk.fair_odds?Number(mk.fair_odds).toFixed(2):'—'}</span><span class="mkt-mkt">${oddsTxt}</span></div>
        <div class="mkt-edge">${pickType} · ${edgeTxt}</div>
      </div>`;
    }).join('')}</div>
  `;
  return el;
}

function renderFixtures(){
  const g=document.getElementById('grid');
  if(!S.fixtures.length){
    g.innerHTML=`<div class="estate"><div class="eico">📅</div><div class="etitle">Sin fixtures</div><div class="esub">Ejecuta: <code>python scraper.py all && python run_pipeline.py</code></div></div>`;
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
            +(rowsH.length?tblHtml(rowsH,`CLASIFICACIÓN <span style="color:var(--amber)">LaLiga Hypermotion</span>`):'');
}

function renderDebug(){
  const c=document.getElementById('debugContent');
  if(!c) return;
  const picks=(S.picks||[]).slice(0,20).map(p=>`- ${p.home_team} vs ${p.away_team} | ${p.market} | ${p.pick_type} | p=${(p.model_prob*100).toFixed(1)}% | edge=${p.edge!=null?(p.edge*100).toFixed(2)+'%':'N/A'}`).join('\n');
  const met=S.metrics?.global||{};
  const info=S.modelInfo||{};
  c.textContent=[
    ...S.dbg,
    '',
    '=== ENGINE MODEL ===',
    `Snapshot: ${info.snapshot_id||'n/a'}`,
    `Version: ${info.model_version||'legacy'}`,
    `Generated: ${info.generated_at||'n/a'}`,
    `Picks: ${(S.picks||[]).length}`,
    `Settled: ${met.settled_picks??0}`,
    `ROI: ${met.roi!=null?(met.roi*100).toFixed(2)+'%':'n/a'}`,
    '',
    '=== TOP PICKS ===',
    picks || '(sin picks)'
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
