'use strict';

function getFixtureProbs(fix){
  const probs = fix?.model?.probs || {};
  return {
    '1': Number(probs['1'] || 0),
    'X': Number(probs['X'] || 0),
    '2': Number(probs['2'] || 0),
    'O2.5': Number(probs['O2.5'] || 0),
    'U2.5': Number(probs['U2.5'] || 0),
    'O3.5': Number(probs['O3.5'] || 0),
    'U3.5': Number(probs['U3.5'] || 0),
    'BTTS_Y': Number(probs['BTTS_Y'] || 0),
    'BTTS_N': Number(probs['BTTS_N'] || 0),
    'AH_HOME_-0.5': Number(probs['AH_HOME_-0.5'] || 0),
    'AH_AWAY_-0.5': Number(probs['AH_AWAY_-0.5'] || 0),
  };
}

function getFixtureMarkets(fix){
  return Array.isArray(fix?.model?.markets) ? fix.model.markets : [];
}

function findPicksForFixture(fixId){
  return (S.picks || []).filter(p => String(p.fixture_id || '') === String(fixId || ''));
}

function hasRealOddsForFixture(fixId){
  return findPicksForFixture(fixId).some(p => p.offered_odds_is_real);
}

Object.assign(window,{getFixtureProbs,getFixtureMarkets,findPicksForFixture,hasRealOddsForFixture});
