'use strict';

document.addEventListener('DOMContentLoaded',()=>{
  load();
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key==='r'){e.preventDefault();load(true);}
  });
});
