(function(){
  var MAX=4;
  function load(){try{return JSON.parse(localStorage.getItem('cmp')||'[]');}catch(e){return [];}}
  function names(){try{return JSON.parse(localStorage.getItem('cmpNames')||'{}');}catch(e){return {};}}
  function save(a,nm){try{localStorage.setItem('cmp',JSON.stringify(a));localStorage.setItem('cmpNames',JSON.stringify(nm));}catch(e){}}
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function toggle(slug,name){
    var a=load(),nm=names(),i=a.indexOf(slug);
    if(i>=0){a.splice(i,1);delete nm[slug];}
    else{if(a.length>=MAX){alert('比較は最大'+MAX+'件までです');return;}a.push(slug);if(name)nm[slug]=name;}
    save(a,nm);refresh();
  }
  function remove(slug){var a=load(),nm=names(),i=a.indexOf(slug);if(i>=0){a.splice(i,1);delete nm[slug];save(a,nm);refresh();}}
  function clear(){save([],{});refresh();}
  function refresh(){
    var a=load(),nm=names();
    var sel={};a.forEach(function(s){sel[s]=1;});
    var btns=document.querySelectorAll('.cmp-add-btn[data-slug]');
    for(var i=0;i<btns.length;i++){
      var b=btns[i],on=!!sel[b.getAttribute('data-slug')];
      b.classList.toggle('is-active',on);
      b.textContent=on?'✓ 比較中':'＋ 比較';
      b.setAttribute('aria-pressed',on?'true':'false');
    }
    var bar=document.getElementById('cmpbar');
    if(!bar)return;
    if(!a.length){bar.className='cmpbar';bar.innerHTML='';document.body.classList.remove('cmp-open');return;}
    var base=bar.getAttribute('data-base')||'';
    var pills=a.map(function(s){return '<span class="pill">'+esc(nm[s]||s)+' <button type="button" data-rm="'+esc(s)+'" aria-label="比較から外す">×</button></span>';}).join('');
    bar.className='cmpbar on';
    bar.innerHTML='<div class="cmpbar-inner"><span class="cmpbar-lbl">比較リスト</span>'+pills+
      '<a class="btn btn-sm" href="'+base+'compare.html?ids='+a.join(',')+'">'+a.length+'件を比較する →</a>'+
      '<button type="button" class="btn-ghost" data-cmpclear>クリア</button></div>';
    document.body.classList.add('cmp-open');
  }
  document.addEventListener('click',function(e){
    var t=e.target;
    var add=t.closest?t.closest('.cmp-add-btn[data-slug]'):null;
    if(add){e.preventDefault();toggle(add.getAttribute('data-slug'),add.getAttribute('data-name'));return;}
    var rm=t.closest?t.closest('[data-rm]'):null;
    if(rm){e.preventDefault();remove(rm.getAttribute('data-rm'));return;}
    if(t.closest&&t.closest('[data-cmpclear]')){clear();return;}
  });
  window.CmpBar={refresh:refresh,toggle:toggle,get:load};
  if(document.readyState!=='loading')refresh();
  else document.addEventListener('DOMContentLoaded',refresh);
})();
