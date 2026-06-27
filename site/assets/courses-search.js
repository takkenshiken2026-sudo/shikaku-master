(function(){
  var q=document.getElementById('course-q'),
      mj=document.getElementById('course-major'),
      tb=document.querySelector('#course-table tbody'),
      cnt=document.getElementById('course-count'),
      empty=document.getElementById('course-empty');
  if(!tb)return;
  var rows=[].slice.call(tb.querySelectorAll('tr[data-major]'));
  function render(){
    var t=(q&&q.value||'').trim().toLowerCase(),
        m=mj?mj.value:'';
    var vis=0;
    rows.forEach(function(tr){
      var ok=true;
      if(m&&tr.dataset.major!==m)ok=false;
      if(ok&&t&&tr.textContent.toLowerCase().indexOf(t)<0)ok=false;
      tr.hidden=!ok;
      if(ok)vis++;
    });
    if(empty)empty.hidden=vis>0||!rows.length;
    if(cnt)cnt.textContent=vis+'件';
  }
  if(q)q.addEventListener('input',render);
  if(mj)mj.addEventListener('change',render);
})();
