(function(){
  var q=document.getElementById('q'),majorSel=document.getElementById('major'),
      typeSel=document.getElementById('type'),sortSel=document.getElementById('sort'),
      industrySel=document.getElementById('industry'),studySel=document.getElementById('study'),
      fPub=document.getElementById('f-pub'),
      studyNote=document.getElementById('studynote'),
      results=document.getElementById('results'),
      countEl=document.getElementById('allCertsCount'),
      pagination=document.getElementById('pagination'),
      count=document.getElementById('count'),
      heroResult=document.getElementById('heroResult'),
      clearBtn=document.getElementById('clearFilters');
  var DATA=[], activeTags=new Set(), currentPage=1, PAGE_SIZE=20, resetPage=true;
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function fmtN(n){return Number(n).toLocaleString('ja-JP');}
  function shortName(n){return (n||'').replace(/[（(][^）)]*[）)]/g,'').trim()||n;}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function studyLow(x){var m=(x.study_hours||'').replace(/,/g,'').match(/([0-9]+)/);return m?parseInt(m[1],10):null;}
  function appNum(x){var m=(x.applicants||'').replace(/,/g,'').match(/([0-9]+)\s*[人名]/);return m?parseInt(m[1],10):null;}
  function syncURL(){
    try{
      var p=new URLSearchParams();
      if(q.value.trim())p.set('q',q.value.trim());
      if(majorSel.value)p.set('major',majorSel.value);
      if(typeSel.value)p.set('type',typeSel.value);
      if(industrySel.value)p.set('industry',industrySel.value);
      if(studySel.value)p.set('study',studySel.value);
      if(sortSel.value)p.set('sort',sortSel.value);
      if(fPub.checked)p.set('pub','1');
      if(activeTags.size)p.set('tag',[].slice.call(activeTags).join(','));
      if(currentPage>1)p.set('page',String(currentPage));
      var qs=p.toString();
      history.replaceState(null,'',qs?('?'+qs):location.pathname);
    }catch(e){}
  }
  function studyHit(x,band){
    var v=studyLow(x); if(v===null)return false;
    var p=band.split('-'),lo=parseInt(p[0],10),hi=p[1]===''?Infinity:parseInt(p[1],10);
    return v>=lo&&v<hi;
  }
  function renderPagination(total){
    if(!pagination)return;
    var pages=Math.max(1,Math.ceil(total/PAGE_SIZE));
    if(total<=PAGE_SIZE){pagination.innerHTML='';pagination.hidden=true;return;}
    pagination.hidden=false;
    if(currentPage>pages)currentPage=pages;
    var start=(currentPage-1)*PAGE_SIZE+1;
    var end=Math.min(currentPage*PAGE_SIZE,total);
    var links='';
    links+='<button type="button" class="pagination-btn'+(currentPage<=1?' is-disabled':'')+'" data-page="'+(currentPage-1)+'"'+(currentPage<=1?' aria-disabled="true"':'')+'>← 前へ</button>';
    var nums=[];
    for(var i=1;i<=pages;i++){
      if(i===1||i===pages||Math.abs(i-currentPage)<=1)nums.push(i);
      else if(nums[nums.length-1]!=='…')nums.push('…');
    }
    nums.forEach(function(n){
      if(n==='…')links+='<span class="pagination-ellipsis" aria-hidden="true">…</span>';
      else links+='<button type="button" class="pagination-num'+(n===currentPage?' is-current':'')+'" data-page="'+n+'"'+(n===currentPage?' aria-current="page"':'')+'>'+n+'</button>';
    });
    links+='<button type="button" class="pagination-btn'+(currentPage>=pages?' is-disabled':'')+'" data-page="'+(currentPage+1)+'"'+(currentPage>=pages?' aria-disabled="true"':'')+'>次へ →</button>';
    pagination.innerHTML='<span class="pagination-status">'+fmtN(start)+'–'+fmtN(end)+'件 / 全'+fmtN(total)+'件</span><div class="pagination-links">'+links+'</div>';
  }
  function render(){
    if(resetPage){currentPage=1;resetPage=false;}
    var t=(q.value||'').trim().toLowerCase(),mj=majorSel.value,tp=typeSel.value,sk=sortSel.value,
        ind=industrySel.value,band=studySel.value;
    if(studyNote)studyNote.style.display=band?'inline':'none';
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
      var key=sk.indexOf('app')===0?appNum:(sk.indexOf('fee')===0?feeNum:passNum), asc=sk.indexOf('asc')>=0;
      out=out.slice().sort(function(a,b){
        var va=key(a),vb=key(b);
        if(va===null&&vb===null)return 0;
        if(va===null)return 1; if(vb===null)return -1;
        return asc?va-vb:vb-va;
      });
    } else {
      out=out.slice().sort(function(a,b){
        var pa=a.popular?1:0,pb=b.popular?1:0;
        if(pa!==pb)return pb-pa;
        return (appNum(b)||0)-(appNum(a)||0);
      });
    }
    var pages=Math.max(1,Math.ceil(out.length/PAGE_SIZE));
    if(currentPage>pages)currentPage=pages;
    var sliceStart=(currentPage-1)*PAGE_SIZE;
    var pageItems=out.slice(sliceStart,sliceStart+PAGE_SIZE);
    var anyFilter=t||mj||tp||ind||band||activeTags.size||fPub.checked;
    if(clearBtn)clearBtn.hidden=!anyFilter;
    if(countEl){
      if(out.length){
        countEl.innerHTML='全 <strong>'+fmtN(out.length)+'</strong> 件 · '+fmtN(sliceStart+1)+'–'+fmtN(sliceStart+pageItems.length)+'件を表示';
      } else countEl.textContent='該当する資格はありません';
    }
    if(heroResult){
      if(anyFilter){
        heroResult.hidden=false;
        heroResult.innerHTML=(t?'「<strong>'+esc(t)+'</strong>」を含む資格 ':'絞り込み結果 ')+
          '<strong>'+fmtN(out.length)+'</strong> 件 <a href="#all-certs">一覧へ ↓</a>';
      } else { heroResult.hidden=true; heroResult.innerHTML=''; }
    }
    results.innerHTML=pageItems.map(function(x){
      var fee=x.fee?esc(x.fee):'—';
      var pass=x.pass_rate?esc(x.pass_rate):'—';
      return '<tr>'+
        '<td class="all-certs-name"><a href="c/'+x.slug+'.html">'+esc(shortName(x.name))+'</a></td>'+
        '<td class="all-certs-cell">'+esc(x.major)+'</td>'+
        '<td class="all-certs-cell">'+esc(x.type)+'</td>'+
        '<td class="all-certs-cell all-certs-num">'+fee+'</td>'+
        '<td class="all-certs-cell all-certs-num">'+pass+'</td></tr>';
    }).join('')||'<tr><td colspan="5" class="empty-state">条件に一致する資格が見つかりませんでした。<br>キーワードを短くするか、上の「× 条件をクリア」で絞り込みを解除してください。</td></tr>';
    renderPagination(out.length);
    syncURL();
  }
  if(pagination)pagination.addEventListener('click',function(e){
    var btn=e.target.closest('[data-page]');
    if(!btn||btn.classList.contains('is-disabled'))return;
    var p=parseInt(btn.getAttribute('data-page'),10);
    if(!p||p===currentPage)return;
    currentPage=p; render();
    var sec=document.getElementById('all-certs'); if(sec)sec.scrollIntoView({behavior:'smooth',block:'start'});
  });
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; if(count)count.textContent=fmtN(all.length);
    var majors={},types={},inds={};
    all.forEach(function(x){majors[x.major]=1;types[x.type]=1;(x.industries||[]).forEach(function(i){inds[i]=(inds[i]||0)+1;});});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    ['国家','公的','民間','要確認'].forEach(function(v){if(types[v])opt(typeSel,v);});
    Object.keys(inds).sort(function(a,b){return inds[b]-inds[a];}).forEach(function(v){
      var o=document.createElement('option');o.value=v;o.textContent=v+'（'+fmtN(inds[v])+'）';industrySel.appendChild(o);});
    var p=new URLSearchParams(location.search);
    if(p.get('q'))q.value=p.get('q');
    if(p.get('major'))majorSel.value=p.get('major');
    if(p.get('type'))typeSel.value=p.get('type');
    if(p.get('industry'))industrySel.value=p.get('industry');
    if(p.get('study'))studySel.value=p.get('study');
    if(p.get('sort'))sortSel.value=p.get('sort');
    if(p.get('pub')==='1')fPub.checked=true;
    if(p.get('page'))currentPage=Math.max(1,parseInt(p.get('page'),10)||1);
    if(p.get('tag')){p.get('tag').split(',').forEach(function(tg){activeTags.add(tg);});}
    if(location.hash==='#all')location.hash='#all-certs';
    render();
  });
  function onFilter(){resetPage=true;render();}
  [q,majorSel,typeSel,sortSel,industrySel,studySel].forEach(function(el){el.addEventListener('input',onFilter);});
  fPub.addEventListener('change',onFilter);
  q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){var a=document.getElementById('all-certs');if(a){e.preventDefault();a.scrollIntoView();}}
  });
  if(clearBtn)clearBtn.addEventListener('click',function(){
    q.value='';majorSel.value='';typeSel.value='';industrySel.value='';studySel.value='';sortSel.value='';fPub.checked=false;
    activeTags.clear();resetPage=true;render();
  });
  (function renderRecent(){
    try{
      var a=JSON.parse(localStorage.getItem('recent')||'[]');
      var blk=document.getElementById('recentBlock'),grid=document.getElementById('recentGrid');
      if(!blk||!grid||!a.length)return;
      grid.innerHTML=a.slice(0,8).map(function(x){
        return '<li><a href="c/'+esc(x.s)+'.html">'+esc(x.n)+'</a></li>';
      }).join('');
      blk.hidden=false;
    }catch(e){}
  })();
})();
