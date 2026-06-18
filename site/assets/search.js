(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),sortSel=document.getElementById('sort'),
      fPub=document.getElementById('f-pub'),fNoreq=document.getElementById('f-noreq'),
      fCbt=document.getElementById('f-cbt'),results=document.getElementById('results'),
      status=document.getElementById('status'),count=document.getElementById('count'),
      bar=document.getElementById('cmpbar');
  var DATA=[], MAX=4, selected=loadSel();
  function loadSel(){try{return new Set(JSON.parse(localStorage.getItem('cmp')||'[]'));}catch(e){return new Set();}}
  function saveSel(){try{localStorage.setItem('cmp',JSON.stringify([].slice.call(selected)));}catch(e){}}
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function isNoreq(x){return /受験資格なし|受験(資格)?(の)?制限なし|誰でも|制限なし/.test(x.eligibility||'');}
  function isCbt(x){return /CBT|ネット試験|IBT/.test(x.exam_format||'');}
  function render(){
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value,sk=sortSel.value;
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(tp&&x.type!==tp)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(fNoreq.checked&&!isNoreq(x))return false;
      if(fCbt.checked&&!isCbt(x))return false;
      return true;
    });
    if(sk){
      var key=sk.indexOf('fee')===0?feeNum:passNum, asc=sk.indexOf('asc')>=0;
      out=out.slice().sort(function(a,b){
        var va=key(a),vb=key(b);
        if(va===null&&vb===null)return 0;
        if(va===null)return 1; if(vb===null)return -1;
        return asc?va-vb:vb-va;
      });
    }
    status.textContent=out.length+' 件';
    results.innerHTML=out.slice(0,300).map(function(x){
      var ck=selected.has(x.slug)?' checked':'';
      var extra=x.status==='published'?[feeNum(x)!==null?esc(x.fee):'',passNum(x)!==null?'合格率'+esc(x.pass_rate):''].filter(Boolean).join(' / '):'';
      return '<li><label class="cmp-add" title="比較に追加"><input type="checkbox" data-slug="'+x.slug+'"'+ck+'></label>'+
        '<a href="c/'+x.slug+'.html">'+esc(x.name)+'</a>'+
        '<span class="meta"><span class="badge b-'+x.type+'">'+x.type+'</span> '+esc(x.major)+' / '+esc(x.category)+(extra?' ・ '+extra:'')+'</span></li>';
    }).join('')||'<li class="muted">該当なし</li>';
    if(out.length>300) results.innerHTML+='<li class="muted">…他 '+(out.length-300)+' 件（絞り込んでください）</li>';
  }
  function updateBar(){
    if(!bar)return;
    var n=selected.size;
    if(!n){bar.classList.remove('on');bar.innerHTML='';return;}
    bar.classList.add('on');
    bar.innerHTML='<span>'+n+' 件を選択中（最大'+MAX+'）</span>'+
      '<a class="btn" href="compare.html?ids='+[].slice.call(selected).join(',')+'">比較する</a>'+
      '<button type="button" id="cmpclear" class="btn-ghost">クリア</button>';
    document.getElementById('cmpclear').onclick=function(){selected.clear();saveSel();render();updateBar();};
  }
  results.addEventListener('change',function(e){
    var cb=e.target;
    if(!cb||cb.tagName!=='INPUT')return;
    var slug=cb.getAttribute('data-slug');
    if(cb.checked){
      if(selected.size>=MAX&&!selected.has(slug)){cb.checked=false;alert('比較は最大'+MAX+'件までです');return;}
      selected.add(slug);
    } else selected.delete(slug);
    saveSel();updateBar();
  });
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; count.textContent=all.length;
    var majors={},types={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    var p=new URLSearchParams(location.search);
    if(p.get('major'))majorSel.value=p.get('major');
    render();updateBar();
  });
  [q,majorSel,typeSel,sortSel].forEach(function(el){el.addEventListener('input',render);});
  [fPub,fNoreq,fCbt].forEach(function(el){el.addEventListener('change',render);});
})();
