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


function renderDebug(){
  const c=document.getElementById('debugContent');
  if(!c) return;
  const picks=(S.picks||[]).slice(0,20).map(p=>`- ${p.fixture} | ${p.market} | p=${(p.prob*100).toFixed(1)}% | edge=${(p.edge*100).toFixed(2)}% | stake=${(p.stake*100).toFixed(2)}%`).join('\n');
  const met=S.metrics?.global||{};
  const info=S.modelInfo||{};
  c.textContent=[
    ...S.dbg,
    '',
    '=== ENGINE MODEL ===',
    `Version: ${info.model_version||'legacy'}`,
    `Generated: ${info.generated_at||'n/a'}`,
    `Picks: ${(S.picks||[]).length}`,
    `Global ROI: ${met.roi!=null?(met.roi*100).toFixed(2)+'%':'n/a'}`,
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
