'use strict';

let combOpen = true;

function toggleComb(){
  combOpen = !combOpen;
  document.getElementById('combBody').style.display = combOpen ? '' : 'none';
  document.getElementById('combToggleBtn').textContent = combOpen ? '▼' : '▶';
}

function buildCombinada(){
  const section = document.getElementById('combSection');
  const body = document.getElementById('combBody');
  const n = parseInt(document.getElementById('combN')?.value || 3, 10);

  const picks = (S.picks || [])
    .filter(p => p.pick_type === 'value_bet' && p.offered_odds_is_real)
    .sort((a,b)=>(Number(b.ev||0)-Number(a.ev||0)))
    .slice(0, n);

  if(!picks.length){
    section.style.display = '';
    body.innerHTML = '<div class="comb-no-ev">Sin value bets reales disponibles. Mostrando solo model picks en las tarjetas.</div>';
    return;
  }

  section.style.display = '';
  body.innerHTML = `
    <div class="comb-legs">${picks.map(p=>`
      <div class="comb-leg">
        <div><div class="comb-match">${p.home_team} vs ${p.away_team}</div><div class="comb-market">${p.market}</div></div>
        <div class="comb-prob">${(Number(p.model_prob||0)*100).toFixed(1)}%</div>
        <div class="comb-odd">${Number(p.offered_odds||0).toFixed(2)}</div>
        <div class="comb-ev pos">EV +${(Number(p.ev||0)*100).toFixed(2)}%</div>
      </div>`).join('')}</div>
  `;
}

Object.assign(window,{toggleComb,buildCombinada});
