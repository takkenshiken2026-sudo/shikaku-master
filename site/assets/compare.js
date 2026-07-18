(function(){
  var p=new URLSearchParams(location.search);
  var ids=(p.get('ids')||'').split(',').filter(Boolean);
  var root=document.getElementById('cmp');
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  if(!ids.length){root.innerHTML='<p class="muted">比較する資格が選択されていません。<a href="index.html">資格一覧</a>から各行の「＋比較」で資格を選んでください。</p>';return;}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
  function studyNum(x){var a=(x.study_hours||'').replace(/,/g,'').match(/[0-9]+/g);if(!a)return null;var m=0;a.forEach(function(n){n=parseInt(n,10);if(n>m)m=n;});return m||null;}
  function clamp(v){return Math.max(0,Math.min(100,v));}
  function easeScore(x){var t=x.tags||[],s=35;
    if(t.indexOf('受験資格なし')>=0||/(なし|不問|制限なし)/.test(x.eligibility||''))s+=35;
    if(t.indexOf('CBT・ネット試験')>=0||/CBT|ネット/.test(x.exam_format||''))s+=20;
    if(/通年|随時|年[3-9]回|年複数/.test(x.frequency||''))s+=10;
    return clamp(s);}
  var RADAR_AXES=['難易度','学習量','合格率','受験しやすさ','年収期待'];
  function radarVals(x){
    var hn=(typeof x.hensa==='number')?x.hensa:null;
    var hr=studyNum(x),pp=passNum(x),su=(typeof x.salary_upper==='number')?x.salary_upper:null;
    return [
      hn===null?null:clamp((hn-25)/50*100),
      hr===null?null:clamp((Math.log(hr)/Math.LN10-1)/(Math.log(1200)/Math.LN10-1)*100),
      pp===null?null:clamp(pp),
      easeScore(x),
      su===null?null:clamp((su-300)/1200*100)
    ];
  }
  var RADAR_COLORS=['#0b57d0','#b8860b','#0b7a3b','#c0392b'];
  function buildRadar(items){
    var elig=items.map(radarVals);
    var usable=items.filter(function(_x,i){return elig[i].filter(function(v){return v!==null;}).length>=3;});
    if(usable.length<2)return '';
    var W=380,H=340,cx=W/2,cy=H/2+2,R=118,n=RADAR_AXES.length;
    function pt(i,frac){var a=-Math.PI/2+i*2*Math.PI/n;return [cx+R*frac*Math.cos(a),cy+R*frac*Math.sin(a)];}
    var s='<svg class="radar-svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="選択した資格の特性レーダー比較">';
    [0.25,0.5,0.75,1].forEach(function(g){
      var pts=[];for(var i=0;i<n;i++){var p=pt(i,g);pts.push(p[0].toFixed(1)+','+p[1].toFixed(1));}
      s+='<polygon points="'+pts.join(' ')+'" class="radar-ring"/>';});
    for(var i=0;i<n;i++){var e=pt(i,1);s+='<line x1="'+cx+'" y1="'+cy+'" x2="'+e[0].toFixed(1)+'" y2="'+e[1].toFixed(1)+'" class="radar-spoke"/>';
      var l=pt(i,1.14),anc='middle';if(l[0]>cx+8)anc='start';else if(l[0]<cx-8)anc='end';
      s+='<text x="'+l[0].toFixed(1)+'" y="'+(l[1]+4).toFixed(1)+'" text-anchor="'+anc+'" class="radar-label">'+esc(RADAR_AXES[i])+'</text>';}
    items.forEach(function(x,idx){
      var v=elig[idx];if(v.filter(function(z){return z!==null;}).length<3)return;
      var c=RADAR_COLORS[idx%RADAR_COLORS.length],pts=[];
      for(var i=0;i<n;i++){var p=pt(i,(v[i]||0)/100);pts.push(p[0].toFixed(1)+','+p[1].toFixed(1));}
      s+='<polygon points="'+pts.join(' ')+'" fill="'+c+'" fill-opacity="0.14" stroke="'+c+'" stroke-width="2"/>';
    });
    s+='</svg>';
    var leg=items.map(function(x,idx){var v=elig[idx];if(v.filter(function(z){return z!==null;}).length<3)return '';
      var c=RADAR_COLORS[idx%RADAR_COLORS.length];
      return '<span class="radar-leg"><span class="radar-leg-key" style="background:'+c+'"></span>'+esc(x.display_name||x.name)+'</span>';}).join('');
    return '<section class="cmp-radar"><h2 class="cmp-verdict-title">特性レーダー比較</h2>'+
      '<div class="radar-wrap radar-wrap--cmp">'+s+'</div><p class="radar-leg-row">'+leg+'</p>'+
      '<p class="muted radar-note">難易度・学習量・合格率・受験しやすさ・年収期待の5軸。難易度・学習時間・想定年収は編集部の目安（非公式）。3軸以上のデータがある資格のみ表示。</p></section>';
  }
  var FIELDS=[['区分','type'],['分野','major'],['カテゴリ','category'],
    ['実施団体','authority'],['受験資格','eligibility'],['試験形式','exam_format'],
    ['受験料','fee'],['合格率','pass_rate'],['実施頻度','frequency']];
  var TYPE_BADGE={国家:['国家資格','badge-national'],公的:['公的資格','badge-public'],
    民間:['民間資格','badge-private'],要確認:['区分要確認','badge-unknown'],
    海外:['海外資格','badge-overseas']};
  function typeBadge(t){
    var b=TYPE_BADGE[t]||['区分要確認','badge-unknown'];
    return '<span class="badge '+b[1]+'">'+esc(b[0])+'</span>';
  }
  fetch('data/certifications.json').then(function(r){return r.json();}).then(function(all){
    var map={};all.forEach(function(x){map[x.slug]=x;});
    var items=ids.map(function(s){return map[s];}).filter(Boolean);
    if(!items.length){root.innerHTML='<p class="muted">該当する資格データが見つかりませんでした。</p>';return;}
    var v=[],seen={};
    function card(label,x,why){if(!x||seen[label+x.slug])return;seen[label+x.slug]=1;
      v.push('<div class="cmp-verdict-card"><div class="pick">'+label+'</div>'+
        '<div class="pickname"><a href="c/'+x.slug+'.html">'+esc(x.name)+'</a></div>'+
        '<div class="why">'+why+'</div></div>');}
    if(items.length>=2){
      var cheap=items.filter(function(x){return feeNum(x)!==null;}).sort(function(a,b){return feeNum(a)-feeNum(b);})[0];
      if(cheap)card('費用を抑えたいなら',cheap,'受験料が最も安い：'+esc(cheap.fee));
      var hp=items.filter(function(x){return passNum(x)!==null;}).sort(function(a,b){return passNum(b)-passNum(a);})[0];
      if(hp)card('合格しやすさなら',hp,'公表合格率が最も高い：'+esc(hp.pass_rate));
      var nr=items.filter(function(x){return /(なし|不問|制限なし)/.test(x.eligibility||'');})[0];
      if(nr)card('誰でも受けたいなら',nr,'受験資格の制限なし');
    }
    var vhtml=v.length?('<section class="cmp-verdict"><h2 class="cmp-verdict-title">選び方の目安（掲載データに基づく簡易判定）</h2><div class="cmp-verdict-grid">'+v.join('')+'</div></section>'):'';
    var vroot=document.getElementById('cmpVerdict'); if(vroot)vroot.innerHTML=vhtml;
    var rroot=document.getElementById('cmpRadar'); if(rroot)rroot.innerHTML=buildRadar(items);
    var h='<table class="cmp" style="min-width:'+(130+items.length*150)+'px"><colgroup><col class="cmp-col-label">';
    items.forEach(function(){h+='<col class="cmp-col-cert">';});
    h+='</colgroup><thead><tr><th></th>';
    items.forEach(function(x){h+='<th><a href="c/'+x.slug+'.html">'+esc(x.display_name||x.name)+'</a></th>';});
    h+='</tr></thead><tbody>';
    FIELDS.forEach(function(f){
      h+='<tr><th>'+f[0]+'</th>';
      items.forEach(function(x){
        var v;
        if(f[1]==='type')v=typeBadge(x.type);
        else v=x[f[1]]?esc(x[f[1]]):'<span class="muted">公式で確認</span>';
        h+='<td>'+v+'</td>';
      });
      h+='</tr>';
    });
    h+='<tr><th>公式サイト</th>';
    items.forEach(function(x){
      h+='<td>'+(x.official_url?'<a href="'+esc(x.official_url)+'" target="_blank" rel="nofollow noopener">公式サイト</a>':'<span class="muted">未登録</span>')+'</td>';
    });
    h+='</tr></tbody></table>';
    root.innerHTML=h;
  });
})();
