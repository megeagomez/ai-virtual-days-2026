(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const slides = [...document.querySelectorAll('.slide')];
  if (!slides.length) return;
  const frame = $('zoom-frame'), container = $('presentation-container');
  let current = 0, scale = 1, mx = innerWidth/2, my = innerHeight/2;
  let light = false, spot = false, ink = false, black = false;
  let lightX=mx, lightY=my, lightW=440, lightH=260, lightPinned=false, lightDrag=null;
  let spotRadius=150, tool='pen', color='#e00048', width=4, drawing=null, editor=null;
  const SVG='http://www.w3.org/2000/svg';
  const marks=slides.map(()=>[]);
  const histories=slides.map(()=>[]);
  let endTime=null, interval=null, phase=-1;
  const SESSION_MIN=+(document.body.dataset.sessionMinutes||55), QA_MIN=+(document.body.dataset.qaMinutes||5);
  const QA_MS=QA_MIN*60000, TOTAL_MS=(SESSION_MIN+QA_MIN)*60000;
  const isTyping=e=>e.target instanceof Element && e.target.closest('input,textarea,select,[contenteditable="true"]');
  const svg = (tag,attrs={}) => {const el=document.createElementNS(SVG,tag); for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v); return el;};
  function resetZoom(){scale=1;container.style.transform='';container.style.transformOrigin='';document.body.classList.remove('zoom-active');}
  function zoom(){
    if(ink) setInk(false);
    scale = scale===1 ? 2 : scale===2 ? 3 : 1;
    if(scale===1){resetZoom();return;}
    const r=frame.getBoundingClientRect();
    const x=Math.max(0,Math.min(100,(mx-r.left)/r.width*100)), y=Math.max(0,Math.min(100,(my-r.top)/r.height*100));
    container.style.transformOrigin=`${x}% ${y}%`;container.style.transform=`scale(${scale})`;
    document.body.classList.add('zoom-active');
  }
  function announce(text){$('mode-status').textContent=text;}
  function updateNotes(){ $('notes').textContent=slides[current].dataset.notes||'Sin notas para esta diapositiva.'; }
  function goTo(index){
    if(!Number.isInteger(index)||index<0||index>=slides.length)return;
    finishText();if(ink)setInk(false);
    slides[current].classList.remove('active');slides[current].setAttribute('aria-hidden','true');
    current=index;slides[current].classList.add('active');slides[current].setAttribute('aria-hidden','false');
    resetZoom();updateNotes();renderInk();
    $('slide-counter').textContent=`${current+1} / ${slides.length}`;
    $('progress-bar').style.width=`${100*current/Math.max(1,slides.length-1)}%`;
    $('previous').disabled=current===0;$('next').disabled=current===slides.length-1;
    history.replaceState(null,'',`#slide=${current+1}`);
    document.dispatchEvent(new CustomEvent('presentation:slidechange',{detail:{index:current}}));
  }
  function updateLight(){
    const x=lightX-lightW/2,y=lightY-lightH/2;
    $('flashlight-hole').setAttribute('x',x);$('flashlight-hole').setAttribute('y',y);
    $('flashlight-hole').setAttribute('width',lightW);$('flashlight-hole').setAttribute('height',lightH);
    const border=$('flashlight-border');border.setAttribute('x',x);border.setAttribute('y',y);border.setAttribute('width',lightW);border.setAttribute('height',lightH);
  }
  function setLight(on){
    light=on;if(on){spot=false;$('spotlight-overlay').hidden=true;if(ink)setInk(false);lightX=mx;lightY=my;lightPinned=false;}
    $('flashlight').toggleAttribute('hidden',!on);updateLight();announce(on?'Linterna: rueda para tamaño; arrastra para fijar un marco; clic para seguir al ratón; L para salir.':'Linterna desactivada');
  }
  function updateSpot(){ $('spotlight-overlay').style.background=`radial-gradient(circle ${spotRadius}px at ${mx}px ${my}px,transparent 65%,rgba(0,0,0,.82) 100%)`; }
  function setSpot(on){spot=on;if(on)setLight(false);$('spotlight-overlay').hidden=!on;updateSpot();}
  window.addEventListener('pointermove',e=>{
    mx=e.clientX;my=e.clientY;
    if(light && !lightPinned && !lightDrag){lightX=mx;lightY=my;updateLight();}
    if(spot)updateSpot();
  });
  $('flashlight').addEventListener('pointerdown',e=>{e.preventDefault();lightDrag={x:e.clientX,y:e.clientY};$('flashlight').setPointerCapture(e.pointerId);});
  $('flashlight').addEventListener('pointermove',e=>{
    if(!lightDrag)return;
    const dx=Math.abs(e.clientX-lightDrag.x),dy=Math.abs(e.clientY-lightDrag.y);
    if(dx+dy<8)return;
    lightX=(e.clientX+lightDrag.x)/2;lightY=(e.clientY+lightDrag.y)/2;
    lightW=Math.max(30,dx);lightH=Math.max(30,dy);updateLight();
  });
  $('flashlight').addEventListener('pointerup',e=>{
    if(!lightDrag)return;
    lightPinned=Math.abs(e.clientX-lightDrag.x)+Math.abs(e.clientY-lightDrag.y)>8;
    lightDrag=null;
  });
  window.addEventListener('wheel',e=>{
    if(light){e.preventDefault();const factor=e.deltaY<0?1.1:1/1.1;
      const ratio=lightW/lightH;lightW=Math.max(50,Math.min(innerWidth*1.5,lightW*factor));lightH=lightW/ratio;updateLight();
    }else if(spot){e.preventDefault();spotRadius=Math.max(50,Math.min(600,spotRadius+(e.deltaY<0?18:-18)));updateSpot();}
  },{passive:false});
  function point(e){return {x:e.clientX/innerWidth*1920,y:e.clientY/innerHeight*1080};}
  function remember(){histories[current].push(JSON.stringify(marks[current]));if(histories[current].length>80)histories[current].shift();}
  function renderInk(){
    const layer=$('ink-drawing');layer.replaceChildren();
    for(const m of marks[current]){
      let node;
      const common={stroke:m.color,'stroke-width':m.width,fill:'none','stroke-linecap':'round','stroke-linejoin':'round'};
      if(m.type==='pen')node=svg('path',{...common,d:m.points.map((p,i)=>(i?'L':'M')+p.x+' '+p.y).join(' ')});
      if(m.type==='rect')node=svg('rect',{...common,x:Math.min(m.x,m.x2),y:Math.min(m.y,m.y2),width:Math.abs(m.x2-m.x),height:Math.abs(m.y2-m.y)});
      if(m.type==='arrow'){
        node=svg('g');node.append(svg('path',{...common,d:`M${m.x} ${m.y}L${m.x2} ${m.y2}`}));
        const a=Math.atan2(m.y2-m.y,m.x2-m.x),s=18+m.width;
        node.append(svg('path',{...common,d:`M${m.x2-s*Math.cos(a-.5)} ${m.y2-s*Math.sin(a-.5)} L${m.x2} ${m.y2} L${m.x2-s*Math.cos(a+.5)} ${m.y2-s*Math.sin(a+.5)}`}));
      }
      if(m.type==='text'){
        node=svg('text',{x:m.x,y:m.y,fill:m.color,'font-size':m.size,'font-family':'Aptos, "Segoe UI Variable Text", "Segoe UI", sans-serif','dominant-baseline':'text-before-edge'});
        m.text.split('\n').forEach((line,i)=>{const t=svg('tspan',{x:m.x,dy:i?'1.2em':'0'});t.textContent=line||' ';node.append(t);});
      }
      if(node)layer.append(node);
    }
  }
  function finishText(cancel=false){
    if(!editor)return;
    if(!cancel && editor.value.trim()){
      remember();marks[current].push({type:'text',x:+editor.dataset.x,y:+editor.dataset.y,text:editor.value,color,size:32+width*2});renderInk();
    }
    editor.remove();editor=null;
  }
  function setInk(on){
    finishText();ink=on;
    if(on){setLight(false);setSpot(false);resetZoom();}
    $('ink-layer').classList.toggle('editing',on);$('ink-toolbar').hidden=!on;
    document.body.classList.toggle('annotation-active',on);
    $('annotate').setAttribute('aria-pressed',String(on));
    announce(on?'Anotar: dibuja o elige Texto y haz clic. N para salir.':'Anotación desactivada');
  }
  function chooseTool(t){finishText();tool=t;document.querySelectorAll('[data-ink-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.inkTool===t)));}
  $('ink-layer').addEventListener('pointerdown',e=>{
    if(!ink)return;e.preventDefault();const p=point(e);
    if(tool==='text'){
      finishText();editor=document.createElement('textarea');editor.id='ink-text-editor';editor.placeholder='Escribe aquí…';editor.setAttribute('aria-label','Texto de la anotación');
      editor.dataset.x=p.x;editor.dataset.y=p.y;
      const r=frame.getBoundingClientRect();editor.style.left=`${Math.min(e.clientX,innerWidth-260)}px`;editor.style.top=`${Math.min(e.clientY,innerHeight-110)}px`;editor.style.color=color;
      editor.addEventListener('keydown',k=>{if(k.key==='Escape'){k.preventDefault();k.stopPropagation();finishText(true);}else if(k.key==='Enter'&&(k.ctrlKey||k.metaKey)){k.preventDefault();finishText();}});
      document.body.append(editor);editor.focus();return;
    }
    remember();
    if(tool==='eraser'){
      const last=[...$('ink-drawing').children].map((el,i)=>({el,i})).reverse().find(({el})=>{const b=el.getBBox();return p.x>=b.x-20&&p.x<=b.x+b.width+20&&p.y>=b.y-20&&p.y<=b.y+b.height+20;});
      if(last)marks[current].splice(last.i,1);renderInk();return;
    }
    drawing=tool==='pen'?{type:tool,color,width,points:[p,{x:p.x+.1,y:p.y+.1}]}:{type:tool,color,width,x:p.x,y:p.y,x2:p.x,y2:p.y};
    marks[current].push(drawing);$('ink-layer').setPointerCapture(e.pointerId);renderInk();
  });
  $('ink-layer').addEventListener('pointermove',e=>{if(!drawing)return;const p=point(e);if(drawing.type==='pen')drawing.points.push(p);else{drawing.x2=p.x;drawing.y2=p.y;}renderInk();});
  function endDrawing(){drawing=null;}
  $('ink-layer').addEventListener('pointerup',endDrawing);$('ink-layer').addEventListener('pointercancel',endDrawing);
  document.querySelectorAll('[data-ink-tool]').forEach(b=>b.onclick=()=>chooseTool(b.dataset.inkTool));
  $('ink-color').oninput=e=>{color=e.target.value;};$('ink-width').oninput=e=>{width=+e.target.value;};
  $('ink-undo').onclick=()=>{finishText(true);const old=histories[current].pop();if(old){marks[current]=JSON.parse(old);renderInk();}};
  $('ink-clear').onclick=()=>{finishText(true);remember();marks[current]=[];renderInk();};
  $('ink-done').onclick=()=>setInk(false);
  function hideGoto(){ $('goto-dialog').close(); }
  $('goto-form').onsubmit=e=>{e.preventDefault();const n=+$('goto-input').value;if(n>=1&&n<=slides.length){goTo(n-1);hideGoto();}};
  $('goto-input').max=slides.length;$('goto-total').textContent=slides.length;
  $('goto-close').onclick=hideGoto;
  function fullscreen(){(document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()).catch(()=>announce('Usa el botón de pantalla completa del navegador.'));}
  function tick(){
    if(!endTime)return;const left=Math.max(0,endTime-Date.now()),secs=Math.ceil(left/1000);
    $('timer-display').textContent=(left<=QA_MS?'Preguntas ':'Sesión ')+Math.floor(secs/60)+':'+String(secs%60).padStart(2,'0');
    $('timer-display').classList.toggle('timer-warning',left<=QA_MS&&left>0);
    if(left<=QA_MS && phase<1){phase=1;announce(`Turno de preguntas: quedan ${QA_MIN} minutos.`);}
    if(!left){$('timer-display').textContent='Tiempo terminado';clearInterval(interval);}
  }
  $('start-session').onclick=()=>{clearInterval(interval);phase=0;endTime=Date.now()+TOTAL_MS;$('timer-setup').hidden=true;tick();interval=setInterval(tick,1000);};
  $('skip-session').onclick=()=>{$('timer-setup').hidden=true;};
  $('previous').onclick=()=>goTo(current-1);$('next').onclick=()=>goTo(current+1);
  $('full').onclick=fullscreen;$('annotate').onclick=()=>setInk(!ink);$('light-button').onclick=()=>setLight(!light);
  $('show-notes').onclick=()=>{$('notes').hidden=!$('notes').hidden;updateNotes();};
  $('help-button').onclick=()=>{$('help-dialog').showModal();};$('help-close').onclick=()=>$('help-dialog').close();
  document.addEventListener('keydown',e=>{
    if(e.repeat)return;
    if(isTyping(e))return;
    if(document.querySelector('dialog[open]'))return;
    const key=e.key.toLowerCase(),ctrl=e.ctrlKey||e.metaKey;
    if(ctrl && key==='3'){e.preventDefault();zoom();return;}
    if(ctrl && key==='s'){e.preventDefault();$('goto-dialog').showModal();$('goto-input').value='';$('goto-input').focus();return;}
    if(ctrl && key==='l'){e.preventDefault();setSpot(!spot);return;}
    if(ctrl && key==='z' && ink){e.preventDefault();$('ink-undo').click();return;}
    if(ctrl||e.altKey)return;
    switch(key){
      case 'z':e.preventDefault();zoom();break;
      case 'l':e.preventDefault();setLight(!light);break;
      case 'n':e.preventDefault();setInk(!ink);break;
      case 'p':$('show-notes').click();break;
      case 'f':fullscreen();break;
      case 'b':black=!black;$('blackout-overlay').hidden=!black;break;
      case 'arrowright':case 'pagedown':case ' ':e.preventDefault();goTo(current+1);break;
      case 'arrowleft':case 'pageup':e.preventDefault();goTo(current-1);break;
      case 'home':e.preventDefault();goTo(0);break;
      case 'end':e.preventDefault();goTo(slides.length-1);break;
      case 'escape':finishText();setInk(false);setLight(false);setSpot(false);resetZoom();black=false;$('blackout-overlay').hidden=true;$('notes').hidden=true;break;
    }
  });
  let touchX=null;
  frame.addEventListener('touchstart',e=>{if(!ink&&!light&&e.touches.length===1)touchX=e.touches[0].clientX;},{passive:true});
  frame.addEventListener('touchend',e=>{if(touchX===null||ink||light)return;const diff=touchX-e.changedTouches[0].clientX;touchX=null;if(Math.abs(diff)>60)goTo(current+(diff>0?1:-1));},{passive:true});
  document.querySelectorAll('.copy').forEach(b=>b.onclick=async()=>{const text=b.parentElement.querySelector('pre').textContent;try{await navigator.clipboard.writeText(text);b.textContent='Copiado';}catch{const range=document.createRange();range.selectNodeContents(b.parentElement.querySelector('pre'));getSelection().removeAllRanges();getSelection().addRange(range);b.textContent='Texto seleccionado';}setTimeout(()=>b.textContent='Copiar prompt',1800);});
  window.addEventListener('resize',()=>{updateLight();updateSpot();});
  const setupText=document.querySelector('#timer-setup p');if(setupText)setupText.textContent=`${SESSION_MIN} minutos de sesión + ${QA_MIN} de preguntas`;$('timer-display').textContent=`${SESSION_MIN} + ${QA_MIN} min`;
  const initial=Number(location.hash.match(/slide=(\d+)/)?.[1]||1)-1;
  goTo(Math.max(0,Math.min(slides.length-1,initial)));chooseTool('pen');
})();
