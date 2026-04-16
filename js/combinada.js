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
  const combo = S.metrics?.combo;

  if(!combo || !Array.isArray(combo.legs) || combo.legs.length < 2){
    section.style.display='none';
    return;
  }
  section.style.display='';

  body.innerHTML = `
    <div class="comb-legs">
      ${combo.legs.map((l)=>`
      <div class="comb-leg">
        <div>
          <div class="comb-match">${l.home_team} vs ${l.away_team}</div>
          <div style="font-size:9px;color:var(--text4)">${l.market} · ${l.selection}</div>
        </div>
        <div style="text-align:center">
          <div class="comb-prob">${(l.model_prob*100).toFixed(1)}%</div>
          <div class="comb-odd">${l.offered_odds?Number(l.offered_odds).toFixed(2):'N/A'}</div>
        </div>
        <div class="comb-ev ${l.edge&&l.edge>0?'pos':'neg'}">
          edge ${l.edge!=null?(l.edge*100).toFixed(2)+'%':'N/A'}
        </div>
      </div>`).join('')}
    </div>
    <div class="comb-summary">
      <div class="comb-stat"><div class="comb-stat-lbl">Cuota total</div><div class="comb-stat-val" style="color:var(--amber)">${combo.combined_odds.toFixed(2)}</div></div>
      <div class="comb-stat"><div class="comb-stat-lbl">Probabilidad</div><div class="comb-stat-val" style="color:var(--blue)">${(combo.combined_prob*100).toFixed(1)}%</div></div>
    </div>
  `;
}

Object.assign(window,{toggleComb,buildCombinada});
