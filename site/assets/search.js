(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),sortSel=document.getElementById('sort'),
      industrySel=document.getElementById('industry'),studySel=document.getElementById('study'),
      fPub=document.getElementById('f-pub'),tagFilter=document.getElementById('tagfilter'),
      studyNote=document.getElementById('studynote'),
      results=document.getElementById('results'),
      status=document.getElementById('status'),count=document.getElementById('count'),
      heroResult=document.getElementById('heroResult');
  var DATA=[], activeTags=new Set();
  var TAG_ORDER=['就職・転職','独立・開業','在宅ワーク','手に職','未経験からIT','定年後・シニア','受験資格なし','CBT・ネット試験','働きながら'];
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function shortName(n){return (n||'').replace(/[（(][^）)]*[）)]/g,'').trim()||n;}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function studyLow(x){var m=(x.study_hours||'').replace(/,/g,'').match(/([0-9]+)/);return m?parseInt(m[1],10):null;}
  function studyHit(x,band){
    var v=studyLow(x); if(v===null)return false;
    var p=band.split('-'),lo=parseInt(p[0],10),hi=p[1]===''?Infinity:parseInt(p[1],10);
    return v>=lo&&v<hi;
  }
  function render(){
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value,sk=sortSel.value,
        ind=industrySel.value,band=studySel.value;
    studyNote.style.display=band?'inline':'none';
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(tp&&x.type!==tp)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(ind&&(x.industries||[]).indexOf(ind)<0)return false;
      if(band&&!studyHit(x,band))return false;
      if(activeTags.size){
        var tg=x.tags||[],ok=true;
        activeTags.forEach(function(a){if(tg.indexOf(a)<0)ok=false;});
        if(!ok)return false;
      }
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
    if(heroResult){
      var anyFilter=t||mj||tp||ind||band||activeTags.size||fPub.checked;
      if(anyFilter){
        heroResult.hidden=false;
        heroResult.innerHTML=(t?'「<strong>'+esc(t)+'</strong>」を含む資格 ':'絞り込み結果 ')+
          '<strong>'+out.length+'</strong> 件 <a href="#all">一覧へ ↓</a>';
      } else { heroResult.hidden=true; heroResult.innerHTML=''; }
    }
    results.innerHTML=out.slice(0,300).map(function(x){
      var extra=x.status==='published'?[feeNum(x)!==null?esc(x.fee):'',passNum(x)!==null?'合格率'+esc(x.pass_rate):''].filter(Boolean).join(' / '):'';
      return '<li><div class="result-main">'+
        '<a href="c/'+x.slug+'.html">'+esc(x.name)+'</a>'+(x.popular?' <span class="result-label">定番</span>':'')+
        '<span class="meta"><span class="badge b-'+x.type+'">'+x.type+'</span> '+esc(x.major)+' / '+esc(x.category)+(extra?' ・ '+extra:'')+'</span>'+
        '</div>'+
        '<button type="button" class="cmp-add-btn" data-slug="'+x.slug+'" data-name="'+esc(shortName(x.name))+'">＋ 比較</button>'+
        '</li>';
    }).join('')||'<li class="muted">該当なし</li>';
    if(out.length>300) results.innerHTML+='<li class="muted">…他 '+(out.length-300)+' 件（絞り込んでください）</li>';
    if(window.CmpBar)window.CmpBar.refresh();
  }
  function buildTagChips(all){
    var present={},counts={};
    all.forEach(function(x){(x.tags||[]).forEach(function(tg){present[tg]=1;counts[tg]=(counts[tg]||0)+1;});});
    TAG_ORDER.forEach(function(tg){
      if(!present[tg])return;
      var b=document.createElement('button');
      b.type='button';b.className='tf-chip';b.setAttribute('data-tag',tg);
      b.textContent=tg+'（'+counts[tg]+'）';
      b.onclick=function(){
        if(activeTags.has(tg)){activeTags.delete(tg);b.classList.remove('on');}
        else{activeTags.add(tg);b.classList.add('on');}
        render();
      };
      tagFilter.appendChild(b);
    });
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; if(count)count.textContent=all.length;
    var majors={},types={},inds={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;(x.industries||[]).forEach(function(i){inds[i]=(inds[i]||0)+1;});});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    Object.keys(inds).sort(function(a,b){return inds[b]-inds[a];}).forEach(function(v){
      var o=document.createElement('option');o.value=v;o.textContent=v+'（'+inds[v]+'）';industrySel.appendChild(o);});
    buildTagChips(all);
    var p=new URLSearchParams(location.search);
    if(p.get('q'))q.value=p.get('q');
    if(p.get('major'))majorSel.value=p.get('major');
    if(p.get('industry'))industrySel.value=p.get('industry');
    if(p.get('tag')){p.get('tag').split(',').forEach(function(tg){
      activeTags.add(tg);
      var c=tagFilter.querySelector('[data-tag="'+tg+'"]'); if(c)c.classList.add('on');});}
    render();
  });
  [q,majorSel,typeSel,sortSel,industrySel,studySel].forEach(function(el){el.addEventListener('input',render);});
  fPub.addEventListener('change',render);
  q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){var a=document.getElementById('all');if(a){e.preventDefault();a.scrollIntoView();}}
  });
})();
