(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),results=document.getElementById('results'),
      status=document.getElementById('status'),count=document.getElementById('count');
  var DATA=[];
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function render(){
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value;
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(tp&&x.type!==tp)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      return true;
    });
    status.textContent=out.length+' 件';
    results.innerHTML=out.slice(0,300).map(function(x){
      return '<li><a href="c/'+x.slug+'.html">'+x.name+'</a>'+
        '<span class="meta"><span class="badge b-'+x.type+'">'+x.type+'</span> '+x.major+' / '+x.category+'</span></li>';
    }).join('')||'<li class="muted">該当なし</li>';
    if(out.length>300) results.innerHTML+='<li class="muted">…他 '+(out.length-300)+' 件（絞り込んでください）</li>';
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; count.textContent=all.length;
    var majors={},types={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    var p=new URLSearchParams(location.search);
    if(p.get('major'))majorSel.value=p.get('major');
    render();
  });
  [q,majorSel,typeSel].forEach(function(el){el.addEventListener('input',render);});
})();
