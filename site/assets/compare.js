(function(){
  var p=new URLSearchParams(location.search);
  var ids=(p.get('ids')||'').split(',').filter(Boolean);
  var root=document.getElementById('cmp');
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  if(!ids.length){root.innerHTML='<p class="muted">比較する資格が選択されていません。<a href="index.html">資格一覧</a>から各行の「＋比較」で資格を選んでください。</p>';return;}
  function feeNum(x){var m=(x.fee||'').replace(/,/g,'').match(/([0-9]+)\s*円/);return m?parseInt(m[1],10):null;}
  function passNum(x){var m=(x.pass_rate||'').replace(/,/g,'').match(/([0-9]+(?:\.[0-9]+)?)\s*%/);return m?parseFloat(m[1]):null;}
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
