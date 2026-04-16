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
