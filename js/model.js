'use strict';

function fixtureModel(fix){
  return fix?.model || {lambda_home:null,lambda_away:null,probs:{},markets:[]};
}

function fixtureProbs(fix){
  const probs = fixtureModel(fix).probs || {};
  return {
    h:Number(probs['1']||0),
    d:Number(probs['X']||0),
    a:Number(probs['2']||0),
    ov25:Number(probs['O2.5']||0),
    un25:Number(probs['U2.5']||0),
    ov35:Number(probs['O3.5']||0),
    un35:Number(probs['U3.5']||0),
    bttsY:Number(probs['BTTS_Y']||0),
    bttsN:Number(probs['BTTS_N']||0),
    ahHomeMinus05:Number(probs['AH_HOME_-0.5']||0),
    ahAwayMinus05:Number(probs['AH_AWAY_-0.5']||0),
  };
}

function marketByKey(fix){
  const out={};
  for(const m of (fixtureModel(fix).markets||[])) out[m.key]=m;
  return out;
}

Object.assign(window,{fixtureModel,fixtureProbs,marketByKey});
