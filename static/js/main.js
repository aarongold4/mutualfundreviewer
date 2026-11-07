// nav toggle
document.addEventListener('click',function(e){
  var t=e.target.closest('#navToggle');
  if(t){var n=document.getElementById('mainNav');n.classList.toggle('open');}
});
