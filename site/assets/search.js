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
      heroSuggest=document.getElementById('heroSuggest'),
      clearBtn=document.getElementById('clearFilters');
  var DATA=[], activeTags=new Set(), currentPage=1, PAGE_SIZE=20, resetPage=true,TROPHY="<span class=\"all-certs-trophy\" aria-hidden=\"true\"><svg class=\"icon-svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M8 21h8\"/><path d=\"M12 17v4\"/><path d=\"M7 4h10v5a5 5 0 0 1-10 0V4z\"/><path d=\"M5 5H3v2a3 3 0 0 0 3 3\"/><path d=\"M19 5h2v2a3 3 0 0 1-3 3\"/></svg></span>";
  var legacyType='',legacyIndustry='';
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function fmtN(n){return Number(n).toLocaleString('ja-JP');}
  function certDisplayName(x){return (x&&(x.display_name||x.name))||'';}
  // 検索用正規化: 小文字化・全角英数→半角・ひらがな→カタカナ・空白/中点/括弧の除去
  function norm(s){
    s=(s||'').toLowerCase();
    s=s.replace(/[Ａ-Ｚａ-ｚ０-９]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-0xFEE0);});
    s=s.replace(/[ぁ-ゖ]/g,function(c){return String.fromCharCode(c.charCodeAt(0)+0x60);});
    return s.replace(/[\s・･·()（）　]/g,'');
  }
  function searchText(x){
    if(!x._st)x._st=norm([x.name,x.display_name||''].concat(x.aliases||[]).join(' '));
    return x._st;
  }
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
    var tn=norm(t);
    var out=DATA.filter(function(x){
      if(mj&&x.major!==mj)return false;
      if(legacyType&&x.type!==legacyType)return false;
      if(tn&&searchText(x).indexOf(tn)<0)return false;
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
    initShindan();
  });
  function initShindan(){
    var goalWrap=document.getElementById('sdGoal'),
        fieldSel=document.getElementById('sdField'),
        timeSel=document.getElementById('sdTime'),
        runBtn=document.getElementById('sdRun'),
        resultBox=document.getElementById('sdResult');
    if(!goalWrap||!fieldSel||!timeSel||!resultBox)return;
    // 目的 → タグの重み（希少なタグほど強いシグナル）
    var GOAL_TAGS={
      job:{'就職・転職':1,'受験資格なし':2,'未経験からIT':3},
      change:{'就職・転職':1,'手に職':3,'未経験からIT':2},
      skill:{'働きながら':3,'CBT・ネット試験':2},
      independent:{'独立・開業':6,'手に職':3}
    };
    var GOAL_LABEL={job:'就職',change:'転職',skill:'スキルアップ',independent:'独立・開業'};
    var TIME_LABEL={'0-50':'〜50時間','50-100':'50〜100時間','100-300':'100〜300時間','300-1000':'300〜1000時間','1000-':'1000時間以上'};
    var goal='job';
    // 分野プルダウンを industries から生成（件数の多い順）
    var indCount={};
    DATA.forEach(function(x){(x.industries||[]).forEach(function(i){indCount[i]=(indCount[i]||0)+1;});});
    Object.keys(indCount).sort(function(a,b){return indCount[b]-indCount[a];}).forEach(function(v){
      opt(fieldSel,v);
    });
    function bandHit(x,band){
      var v=studyLow(x); if(v===null)return null;
      var pr=band.split('-'),lo=parseInt(pr[0],10),hi=pr[1]===''?Infinity:parseInt(pr[1],10);
      return v>=lo&&v<hi;
    }
    function scoreOf(x,field,time){
      if(x.status!=='published')return null;
      var score=0,reasons=[];
      var tw=GOAL_TAGS[goal]||{},tg=x.tags||[],goalScore=0;
      for(var k in tw){if(tg.indexOf(k)>=0)goalScore+=tw[k];}
      score+=goalScore;
      if(goal==='independent'&&tg.indexOf('独立・開業')>=0)reasons.push('独立・開業向き');
      else if(goal==='skill'&&tg.indexOf('働きながら')>=0)reasons.push('働きながら取りやすい');
      else if(goal==='job'&&tg.indexOf('受験資格なし')>=0)reasons.push('受験資格なし');
      else if(goal==='change'&&tg.indexOf('手に職')>=0)reasons.push('手に職');
      if(field){
        if((x.industries||[]).indexOf(field)>=0){score+=6;reasons.push(field);}
        else return null; // 分野指定時はその業界で活かせる資格のみ
      }
      if(time){
        var hit=bandHit(x,time);
        if(hit===true){score+=4;reasons.push('学習時間が合う');}
        else if(hit===false)score-=3;
      }
      if(x.popular){score+=2;if(reasons.length<3)reasons.push('人気');}
      var ap=appNum(x);if(ap)score+=Math.min(2,ap/50000);
      return {x:x,score:score,reasons:reasons.slice(0,3)};
    }
    function run(){
      var field=fieldSel.value,time=timeSel.value;
      var scored=[];
      DATA.forEach(function(x){var s=scoreOf(x,field,time);if(s)scored.push(s);});
      scored.sort(function(a,b){
        if(b.score!==a.score)return b.score-a.score;
        return (appNum(b.x)||0)-(appNum(a.x)||0);
      });
      var top=scored.slice(0,6);
      var cond='「<strong>'+esc(GOAL_LABEL[goal])+'</strong>」'+
        (field?'／<strong>'+esc(field)+'</strong>':'')+
        (time?'／学習時間 <strong>'+esc(TIME_LABEL[time]||time)+'</strong>':'');
      if(!top.length){
        resultBox.innerHTML='<p class="shindan-result-head">'+cond+' の条件に合う資格が見つかりませんでした。分野や学習時間の条件をゆるめてお試しください。</p>';
        resultBox.hidden=false;return;
      }
      var head='<p class="shindan-result-head">'+cond+' のおすすめ資格 <strong>'+top.length+'</strong> 件</p>';
      var cards=top.map(function(s,i){
        var x=s.x;
        var meta=[x.major,x.study_hours?'学習 '+x.study_hours:'',x.pass_rate?'合格率 '+x.pass_rate:''].filter(Boolean).join('　·　');
        var rs=s.reasons.map(function(r){return '<span class="sd-reason">'+esc(r)+'</span>';}).join('');
        return '<li><a class="sd-card" href="c/'+esc(x.slug)+'.html">'+
          '<span class="sd-card-rank">'+(i+1)+'位</span>'+
          '<span class="sd-card-name">'+esc(certDisplayName(x))+'</span>'+
          '<span class="sd-card-meta">'+esc(meta)+'</span>'+
          (rs?'<span class="sd-card-reasons">'+rs+'</span>':'')+
          '</a></li>';
      }).join('');
      resultBox.innerHTML=head+'<ul class="sd-cards">'+cards+'</ul>';
      resultBox.hidden=false;
    }
    goalWrap.addEventListener('click',function(e){
      var b=e.target.closest('.sd-chip');if(!b)return;
      goal=b.getAttribute('data-goal')||'job';
      goalWrap.querySelectorAll('.sd-chip').forEach(function(c){
        var on=c===b;c.classList.toggle('is-on',on);c.setAttribute('aria-pressed',on?'true':'false');
      });
      if(!resultBox.hidden)run();
    });
    fieldSel.addEventListener('change',function(){if(!resultBox.hidden)run();});
    timeSel.addEventListener('change',function(){if(!resultBox.hidden)run();});
    if(runBtn)runBtn.addEventListener('click',run);
  }
  function onFilter(){resetPage=true;render();}
  function onQueryInput(e){syncQueryInputs(e.target);onFilter();}
  var suggestList=heroSuggest?heroSuggest.querySelector('.hero-suggest-list'):null;
  var suggestLabel=heroSuggest?heroSuggest.querySelector('.hero-suggest-label'):null;
  var staticSuggest=suggestList?suggestList.innerHTML:'';
  function showHeroSuggest(filter){
    if(!heroSuggest||!q||!suggestList)return;
    var t=norm((filter||'').trim());
    if(!t){
      suggestList.innerHTML=staticSuggest;
      if(suggestLabel)suggestLabel.textContent='よく探される資格';
      heroSuggest.hidden=false;q.setAttribute('aria-expanded','true');return;
    }
    if(!DATA.length){heroSuggest.hidden=true;q.setAttribute('aria-expanded','false');return;}
    var hits=DATA.filter(function(x){return searchText(x).indexOf(t)>=0;});
    hits.sort(function(a,b){
      var pa=a.popular?1:0,pb=b.popular?1:0;
      if(pa!==pb)return pb-pa;
      return (appNum(b)||0)-(appNum(a)||0);
    });
    hits=hits.slice(0,8);
    if(!hits.length){heroSuggest.hidden=true;q.setAttribute('aria-expanded','false');return;}
    if(suggestLabel)suggestLabel.textContent='候補の資格';
    suggestList.innerHTML=hits.map(function(x){
      return '<li><a class="hero-suggest-item" href="c/'+esc(x.slug)+'.html">'+esc(certDisplayName(x))+
        '<span class="hero-suggest-meta">'+esc(x.major)+'</span></a></li>';
    }).join('');
    heroSuggest.hidden=false;q.setAttribute('aria-expanded','true');
  }
  function hideHeroSuggest(){
    if(!heroSuggest)return;
    heroSuggest.hidden=true;
    if(q)q.setAttribute('aria-expanded','false');
  }
  if(q)q.addEventListener('input',function(e){showHeroSuggest(e.target.value);onQueryInput(e);});
  if(listQ)listQ.addEventListener('input',onQueryInput);
  [majorSel,sortSel,studySel,passSel,freqSel].forEach(function(el){if(el)el.addEventListener('input',onFilter);});
  fPub.addEventListener('change',onFilter);
  if(q){
    q.addEventListener('focus',function(){showHeroSuggest(q.value);});
    q.addEventListener('blur',function(){setTimeout(hideHeroSuggest,150);});
    q.addEventListener('keydown',function(e){
      if(e.key==='Escape'){hideHeroSuggest();return;}
      if(e.key==='Enter'){hideHeroSuggest();var a=document.getElementById('all-certs');if(a){e.preventDefault();a.scrollIntoView();}}
    });
  }
  if(heroSuggest){
    heroSuggest.addEventListener('mousedown',function(e){e.preventDefault();});
    heroSuggest.addEventListener('click',function(e){
      var btn=e.target.closest('.hero-suggest-item');
      if(!btn)return;
      if(btn.tagName==='A')return; // 動的候補は詳細ページへそのまま遷移
      var val=btn.getAttribute('data-q')||'';
      syncQueryInputs({value:val});
      hideHeroSuggest();
      onFilter();
      var sec=document.getElementById('all-certs');
      if(sec)sec.scrollIntoView({behavior:'smooth',block:'start'});
    });
  }
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
})();
