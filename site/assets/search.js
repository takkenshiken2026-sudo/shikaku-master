(function(){
  var q=document.getElementById('q'),listQ=document.getElementById('list-q'),
      majorSel=document.getElementById('major'),sortSel=document.getElementById('sort'),
      studySel=document.getElementById('study'),passSel=document.getElementById('pass'),
      freqSel=document.getElementById('frequency'),
      fPub=document.getElementById('f-pub'),
      studyNote=document.getElementById('studynote'),
      results=document.getElementById('results'),
      countEl=document.getElementById('allCertsCount'),
      pagination=document.getElementById('pagination'),
      count=document.getElementById('count'),
      heroResult=document.getElementById('heroResult'),
      clearBtn=document.getElementById('clearFilters');
  var DATA=[], activeTags=new Set(), currentPage=1, PAGE_SIZE=20, resetPage=true,TROPHY="<span class=\"all-certs-trophy\" aria-hidden=\"true\"><svg class=\"icon-svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M8 21h8\"/><path d=\"M12 17v4\"/><path d=\"M7 4h10v5a5 5 0 0 1-10 0V4z\"/><path d=\"M5 5H3v2a3 3 0 0 0 3 3\"/><path d=\"M19 5h2v2a3 3 0 0 1-3 3\"/></svg></span>";
  var legacyType='',legacyIndustry='';
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function fmtN(n){return Number(n).toLocaleString('ja-JP');}
  function certDisplayName(x){return (x&&(x.display_name||x.name))||'';}
  function opt(sel,v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function studyLow(x){var m=(x.study_hours||'').replace(/,/g,'').match(/([0-9]+)/);return m?parseInt(m[1],10):null;}
  function appNum(x){var m=(x.applicants||'').replace(/,/g,'').match(/([0-9]+)\s*[人名]/);return m?parseInt(m[1],10):null;}
  function queryText(){return ((q&&q.value)||(listQ&&listQ.value)||'').trim().toLowerCase();}
  function syncQueryInputs(src){
    var v=src?src.value:'';
    if(q&&src!==q)q.value=v;
    if(listQ&&src!==listQ)listQ.value=v;
  }
  function freqBucket(f){
    f=(f||'').trim();
    if(!f)return 'unknown';
    if(/休止/.test(f))return 'other';
    if(/通年|随時|CBT|ネット/i.test(f))return 'anytime';
    if(/年5回|年6回|年複数|年[34]回/.test(f))return '3plus';
    if(/年2回/.test(f))return 'twice';
    if(/年1回/.test(f))return 'once';
    return 'other';
  }
  function passHit(x,band){
    var v=passNum(x);
    if(band==='unknown')return v===null;
    if(v===null)return false;
    if(band==='80-')return v>=80;
    var p=band.split('-'),lo=parseFloat(p[0],10),hi=p[1]===''?Infinity:parseFloat(p[1],10);
    return v>=lo&&v<hi;
  }
  function syncURL(){
    try{
      var p=new URLSearchParams();
      var qt=queryText();
      if(qt)p.set('q',qt);
      if(majorSel.value)p.set('major',majorSel.value);
      if(studySel.value)p.set('study',studySel.value);
      if(passSel&&passSel.value)p.set('pass',passSel.value);
      if(freqSel&&freqSel.value)p.set('frequency',freqSel.value);
      if(sortSel.value&&sortSel.value!=='app-desc')p.set('sort',sortSel.value);
      if(fPub.checked)p.set('pub','1');
      if(activeTags.size)p.set('tag',[].slice.call(activeTags).join(','));
      if(legacyType)p.set('type',legacyType);
      if(legacyIndustry)p.set('industry',legacyIndustry);
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
    var t=queryText(),mj=majorSel.value,sk=sortSel.value||'app-desc',
        band=studySel.value,pBand=passSel?passSel.value:'',fBand=freqSel?freqSel.value:'';
    if(studyNote)studyNote.style.display=band?'inline':'none';
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(legacyType&&x.type!==legacyType)return false;
      if(t&&x.name.toLowerCase().indexOf(t)<0)return false;
      if(fPub.checked&&x.status!=='published')return false;
      if(legacyIndustry&&(x.industries||[]).indexOf(legacyIndustry)<0)return false;
      if(band&&!studyHit(x,band))return false;
      if(pBand&&!passHit(x,pBand))return false;
      if(fBand&&freqBucket(x.frequency)!==fBand)return false;
      if(activeTags.size){
        var tg=x.tags||[],ok=true;
        activeTags.forEach(function(a){if(tg.indexOf(a)<0)ok=false;});
        if(!ok)return false;
      }
      return true;
    });
    var key=sk.indexOf('app')===0?appNum:(sk.indexOf('study')===0?studyLow:(sk.indexOf('pass')===0?passNum:appNum)), asc=sk.indexOf('asc')>=0;
    out=out.slice().sort(function(a,b){
      var va=key(a),vb=key(b);
      if(va===null&&vb===null)return 0;
      if(va===null)return 1; if(vb===null)return -1;
      return asc?va-vb:vb-va;
    });
    var pages=Math.max(1,Math.ceil(out.length/PAGE_SIZE));
    if(currentPage>pages)currentPage=pages;
    var sliceStart=(currentPage-1)*PAGE_SIZE;
    var pageItems=out.slice(sliceStart,sliceStart+PAGE_SIZE);
    var anyFilter=t||mj||band||pBand||fBand||activeTags.size||fPub.checked||legacyType||legacyIndustry;
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
      var study=x.study_hours?esc(x.study_hours):'—';
      var pass=x.pass_rate?esc(x.pass_rate):'—';
      var freq=x.frequency?esc(x.frequency):'—';
      return '<tr class="cert-row" tabindex="0" data-href="c/'+esc(x.slug)+'.html">'+
        '<td class="all-certs-name"><span class="all-certs-name-inner">'+
        (x.popular?TROPHY:'')+
        '<span class="all-certs-name-text">'+esc(certDisplayName(x))+'</span></span></td>'+
        '<td class="all-certs-cell all-certs-cell--major">'+esc(x.major)+'</td>'+
        '<td class="all-certs-cell all-certs-num all-certs-cell--study">'+study+'</td>'+
        '<td class="all-certs-cell all-certs-num all-certs-cell--pass">'+pass+'</td>'+
        '<td class="all-certs-cell all-certs-cell--freq">'+freq+'</td></tr>';
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
  if(results){
    results.addEventListener('click',function(e){
      var tr=e.target.closest('tr.cert-row');
      if(!tr)return;
      var href=tr.getAttribute('data-href');
      if(href)location.href=href;
    });
    results.addEventListener('keydown',function(e){
      if(e.key!=='Enter'&&e.key!==' ')return;
      var tr=e.target.closest('tr.cert-row');
      if(!tr)return;
      e.preventDefault();
      var href=tr.getAttribute('data-href');
      if(href)location.href=href;
    });
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    DATA=all; if(count)count.textContent=fmtN(all.length);
    var majors={};
    all.forEach(function(x){majors[x.major]=1;});
    Object.keys(majors).sort().forEach(function(v){opt(majorSel,v);});
    var p=new URLSearchParams(location.search);
    if(p.get('q')){syncQueryInputs({value:p.get('q')});}
    if(p.get('major'))majorSel.value=p.get('major');
    if(p.get('study'))studySel.value=p.get('study');
    if(passSel&&p.get('pass'))passSel.value=p.get('pass');
    if(freqSel&&p.get('frequency'))freqSel.value=p.get('frequency');
    sortSel.value=p.get('sort')||'app-desc';
    if(p.get('pub')==='1')fPub.checked=true;
    if(p.get('page'))currentPage=Math.max(1,parseInt(p.get('page'),10)||1);
    if(p.get('tag')){p.get('tag').split(',').forEach(function(tg){activeTags.add(tg);});}
    if(p.get('type'))legacyType=p.get('type');
    if(p.get('industry'))legacyIndustry=p.get('industry');
    if(location.hash==='#all')location.hash='#all-certs';
    render();
  });
  function onFilter(){resetPage=true;render();}
  function onQueryInput(e){syncQueryInputs(e.target);onFilter();}
  if(q)q.addEventListener('input',onQueryInput);
  if(listQ)listQ.addEventListener('input',onQueryInput);
  [majorSel,sortSel,studySel,passSel,freqSel].forEach(function(el){if(el)el.addEventListener('input',onFilter);});
  fPub.addEventListener('change',onFilter);
  if(q)q.addEventListener('keydown',function(e){
    if(e.key==='Enter'){var a=document.getElementById('all-certs');if(a){e.preventDefault();a.scrollIntoView();}}
  });
  if(listQ)listQ.addEventListener('keydown',function(e){
    if(e.key==='Enter'){e.preventDefault();onFilter();}
  });
  if(clearBtn)clearBtn.addEventListener('click',function(){
    syncQueryInputs({value:''});
    majorSel.value='';studySel.value='';
    if(passSel)passSel.value='';
    if(freqSel)freqSel.value='';
    sortSel.value='app-desc';fPub.checked=false;
    legacyType='';legacyIndustry='';
    activeTags.clear();resetPage=true;render();
  });
  (function renderRecent(){
    try{
      var a=JSON.parse(localStorage.getItem('recent')||'[]');
      var blk=document.getElementById('recentBlock'),grid=document.getElementById('recentGrid');
      if(!blk||!grid||!a.length)return;
      fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
        var nm={};all.forEach(function(x){nm[x.slug]=x.display_name||x.name;});
        grid.innerHTML=a.slice(0,8).map(function(x){
          return '<li><a href="c/'+esc(x.s)+'.html">'+esc(nm[x.s]||x.n)+'</a></li>';
        }).join('');
        blk.hidden=false;
      });
    }catch(e){}
  })();
})();
