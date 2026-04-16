'use strict';

const S = {
  raw:null, fixtures:[], byId:{}, byNorm:{}, byIdH:{}, byNormH:{},
  formById:{}, formByNorm:{},
  lgH:1.45, lgA:1.15, lgHH:1.35, lgAH:1.10,
  vt:55, mg:7, tab:'f', dbg:[],
  allLeagues: {},      // { key → leagueData } cuando hay multiple ligas
  currentKey: null,    // liga activa actualmente
  cardModel: {teams:{}, fixtures:{}, referees:{}, leagueAvgTotal:3.8},
};
window.S = S;
