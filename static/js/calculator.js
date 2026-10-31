// Expense Ratio Impact Calculator — neutral compounding math, no return projections marketed as advice.
(function(){
  var $ = function(id){return document.getElementById(id);};
  var fmt = function(n){return '$'+Math.round(n).toLocaleString('en-US');};
  var fmtK = function(n){
    if(n>=1e6) return '$'+(n/1e6).toFixed(2)+'M';
    if(n>=1e3) return '$'+Math.round(n/1e3)+'k';
    return '$'+Math.round(n);
  };

  var ranges = [
    ['initial','initialV',function(v){return fmt(v);}],
    ['monthly','monthlyV',function(v){return fmt(v);}],
    ['years','yearsV',function(v){return v+' yrs';}],
    ['ret','retV',function(v){return (v)+'%';}],
    ['erA','erAV',function(v){return (v)+'%';}],
    ['erB','erBV',function(v){return (v)+'%';}]
  ];

  function simulate(initial, monthly, years, annualReturn, er){
    // monthly compounding; expense ratio deducted monthly from balance
    var months = years*12;
    var rNet = (annualReturn/100 - er/100)/12; // net monthly growth
    var bal = initial;
    var series = [bal];
    for(var m=1;m<=months;m++){
      bal = bal*(1+rNet) + monthly;
      if(m%12===0) series.push(bal);
    }
    return {end:bal, series:series};
  }

  function totalContributed(initial,monthly,years){
    return initial + monthly*12*years;
  }

  var canvas = $('feeChart');
  var ctx = canvas ? canvas.getContext('2d') : null;

  function draw(sA, sB, years){
    if(!ctx) return;
    var dpr = window.devicePixelRatio||1;
    var cssW = canvas.clientWidth, cssH = 320;
    canvas.width = cssW*dpr; canvas.height = cssH*dpr;
    canvas.style.height = cssH+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,cssW,cssH);

    var padL=58, padR=16, padT=18, padB=34;
    var W=cssW-padL-padR, H=cssH-padT-padB;
    var maxV = Math.max(sA[sA.length-1], sB[sB.length-1])*1.05;
    var n = sA.length-1;

    function x(i){return padL + (i/n)*W;}
    function y(v){return padT + H - (v/maxV)*H;}

    // gridlines + y labels
    ctx.font='11px "Public Sans",sans-serif';
    ctx.textBaseline='middle';
    ctx.strokeStyle='#e2dccb'; ctx.fillStyle='#46535f'; ctx.lineWidth=1;
    for(var g=0;g<=4;g++){
      var v=maxV*g/4, yy=y(v);
      ctx.beginPath();ctx.moveTo(padL,yy);ctx.lineTo(cssW-padR,yy);ctx.stroke();
      ctx.textAlign='right'; ctx.fillText(fmtK(v), padL-8, yy);
    }
    // x labels
    ctx.textAlign='center'; ctx.textBaseline='top';
    var step = years<=10?2:(years<=20?5:5);
    for(var t=0;t<=years;t+=step){
      ctx.fillText(t+'y', x(t), padT+H+8);
    }

    function plot(series,color,fill){
      ctx.beginPath();
      for(var i=0;i<series.length;i++){
        var px=x(i), py=y(series[i]);
        if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py);
      }
      if(fill){
        ctx.lineTo(x(series.length-1),y(0));ctx.lineTo(x(0),y(0));ctx.closePath();
        ctx.fillStyle=fill;ctx.fill();
      } else {
        ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();
      }
    }
    // shaded gap between A (lower fee, higher) and B
    plot(sA,'#0b2a4a',null);
    plot(sB,'#9a2b25',null);
    // markers
    ctx.fillStyle='#0b2a4a';ctx.beginPath();ctx.arc(x(n),y(sA[n]),3.5,0,7);ctx.fill();
    ctx.fillStyle='#9a2b25';ctx.beginPath();ctx.arc(x(n),y(sB[n]),3.5,0,7);ctx.fill();
  }

  function recalc(){
    var initial=+$('initial').value, monthly=+$('monthly').value, years=+$('years').value,
        ret=+$('ret').value, erA=+$('erA').value, erB=+$('erB').value;
    var a=simulate(initial,monthly,years,ret,erA);
    var b=simulate(initial,monthly,years,ret,erB);
    var diff=a.end-b.end;
    var contributed=totalContributed(initial,monthly,years);

    $('endA').textContent=fmt(a.end);
    $('endB').textContent=fmt(b.end);
    $('feeCost').textContent=fmt(Math.abs(diff));
    $('contributed').textContent=fmt(contributed);
    var pct = b.end>0 ? (Math.abs(diff)/b.end*100) : 0;
    $('feePct').textContent=pct.toFixed(1)+'%';
    $('erAlabel').textContent=erA.toFixed(2)+'%';
    $('erBlabel').textContent=erB.toFixed(2)+'%';
    draw(a.series,b.series,years);
  }

  ranges.forEach(function(r){
    var el=$(r[0]), lbl=$(r[1]);
    if(!el) return;
    var update=function(){ if(lbl) lbl.textContent=r[2](+el.value); recalc(); };
    el.addEventListener('input',update);
    update();
  });

  window.addEventListener('resize',recalc);
  recalc();
})();
