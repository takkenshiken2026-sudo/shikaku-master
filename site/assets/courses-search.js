(function(){
  var q=document.getElementById('course-q'),
      tb=document.querySelector('#course-table tbody'),
      cnt=document.getElementById('course-count'),
      empty=document.getElementById('course-empty');
  if(!tb)return;
  var rows=[].slice.call(tb.querySelectorAll('tr:not(#course-empty)'));
  function render(){
    var t=(q&&q.value||'').trim().toLowerCase();
    var vis=0;
    rows.forEach(function(tr){
      var ok=!t||tr.textContent.toLowerCase().indexOf(t)>=0;
      tr.hidden=!ok;
      if(ok)vis++;
    });
    if(empty)empty.hidden=vis>0||!rows.length;
    if(cnt)cnt.textContent=vis+'件';
  }
  if(q)q.addEventListener('input',render);
})();
