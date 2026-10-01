
(function(){
  var KEY="cg_remind_v1";
  var MAX=10;
  var state={on:true, items:[]};
  function $(id){return document.getElementById(id);}
  function load(){ try{ var r=JSON.parse(localStorage.getItem(KEY)||"{}"); state.on=r.on!==false; state.items=Array.isArray(r.items)?r.items.slice(0,MAX):[]; }catch(e){} }
  function pending(){ return state.on ? state.items.filter(function(it){return !it.done;}).length : 0; }
  function badge(notify){
    var n=pending();
    if(navigator.setAppBadge){ if(n) navigator.setAppBadge(n).catch(function(){}); else if(navigator.clearAppBadge) navigator.clearAppBadge().catch(function(){}); }
    if(navigator.serviceWorker && navigator.serviceWorker.controller){
      navigator.serviceWorker.controller.postMessage({type:"cg-remind", count:n, notify:!!notify});
    }
  }
  function save(){ localStorage.setItem(KEY, JSON.stringify({on:state.on, items:state.items})); paint(); badge(false); }
  function dueCount(){ var n=Date.now(); return state.items.filter(function(it){return it.at && it.at<=n && !it.done;}).length; }
  function soonCount(){ return state.items.filter(function(it){return !it.done;}).length; }
  function paint(){
    var btn=$("cg-remind-btn");
    if(btn){
      btn.innerHTML = (state.on?"Remind":"Remind off") + (soonCount()?'<span class="dot">'+soonCount()+"</span>":"");
      btn.classList.toggle("is-off", !state.on);
    }
    var panel=$("cg-remind");
    if(panel) panel.classList.toggle("is-off", !state.on);
    var list=$("cg-remind-list");
    if(!list) return;
    list.innerHTML="";
    state.items.forEach(function(it, i){
      var li=document.createElement("div");
      li.className="item";
      var when=it.at? new Date(it.at).toLocaleString():"";
      li.innerHTML='<div><b>'+escapeHtml(it.note)+'</b><small>'+escapeHtml(when)+(it.done?" · done":"")+'</small></div>';
      var x=document.createElement("button");
      x.className="x"; x.textContent="✕";
      x.onclick=function(){ state.items.splice(i,1); save(); };
      li.appendChild(x);
      list.appendChild(li);
    });
  }
  function escapeHtml(s){ return String(s||"").replace(/[&<>]/g,function(c){return {"&":"&","<":"<",">":">"}[c];}); }
  function ring(note){
    var a=$("cg-remind-audio");
    if(a){ try{ a.currentTime=0; a.play(); }catch(e){} setTimeout(function(){ try{a.pause(); a.currentTime=0;}catch(e){} }, 3000); }
    try{ if(window.speechSynthesis){ speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance("Reminder, "+note)); } }catch(e){}
    try{
      if(window.Notification && Notification.permission==="granted") new Notification("Reminder", {body: note, tag:"cg-remind"});
    }catch(e){}
  }
  function check(){
    if(!state.on) return;
    var now=Date.now(), changed=false;
    state.items.forEach(function(it){
      if(!it.done && it.at && it.at<=now){ it.done=true; changed=true; ring(it.note); }
    });
    if(changed) save();
  }
  function add(){
    var note=($("cg-remind-note").value||"").trim();
    var when=$("cg-remind-when").value;
    if(!note || !when) return;
    if(state.items.filter(function(it){return !it.done;}).length>=MAX){ alert("Remind holds 10 active notes."); return; }
    var at=new Date(when).getTime();
    if(!at || at<Date.now()-1000){ alert("Pick a future time."); return; }
    state.items.push({id:Date.now(), note:note.slice(0,180), at:at, done:false});
    $("cg-remind-note").value="";
    save();
    if(window.Notification && Notification.permission==="default") Notification.requestPermission();
  }
  function init(){
    load();
    var btn=$("cg-remind-btn");
    if(btn) btn.onclick=function(){ state.on=!state.on; if(!state.on){ var a=$("cg-remind-audio"); if(a) a.pause(); } save(); };
    var addBtn=$("cg-remind-add");
    if(addBtn) addBtn.onclick=add;
    paint();
    setInterval(check, 1000);
    document.addEventListener("visibilitychange", function(){ check(); if(document.hidden) badge(true); });
    window.addEventListener("pagehide", function(){ badge(true); });
    badge(false);
    if(window.Notification && Notification.permission==="default") Notification.requestPermission();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
