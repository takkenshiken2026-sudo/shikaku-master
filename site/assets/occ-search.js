(function(){
  var q=document.getElementById('occ-q'),mj=document.getElementById('occ-major'),
      res=document.getElementById('occ-results'),stat=document.getElementById('occ-status'),
      stat0=document.getElementById('occ-static');
  if(!q)return;
  var DATA=[];
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function render(){
    var t=(q.value||'').trim().toLowerCase(),m=mj.value;
    if(!t&&!m){res.hidden=true;stat0.hidden=false;stat.textContent='';return;}
    var out=DATA.filter(function(x){
      if(m&&x.m!==m)return false;
      if(t&&x.n.toLowerCase().indexOf(t)<0)return false;
      return true;
    });
    stat0.hidden=true;res.hidden=false;
    stat.textContent=out.length+' 件';
    res.innerHTML=out.slice(0,400).map(function(x){
      return '<li><a href="'+x.id+'.html">'+esc(x.n)+'</a> <span class="muted">（'+x.c+'資格）</span></li>';
    }).join('')||'<li class="muted">該当なし</li>';
    if(out.length>400)res.innerHTML+='<li class="muted">…他 '+(out.length-400)+' 件（絞り込んでください）</li>';
  }
  fetch('../data/occupations.json').then(function(r){return r.json();}).then(function(all){
    DATA=all.slice().sort(function(a,b){return b.c-a.c||(a.n<b.n?-1:1);});
    var mset={};all.forEach(function(x){if(x.m)mset[x.m]=1;});
    Object.keys(mset).sort().forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;mj.appendChild(o);});
    render();
  });
  q.addEventListener('input',render);mj.addEventListener('change',render);
})();
