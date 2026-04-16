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
