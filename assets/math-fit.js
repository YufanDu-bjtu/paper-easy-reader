(()=>{
  const panels=[...document.querySelectorAll('.equation-panel')];
  const canFit=CSS.supports('zoom','0.8');
  function fit(panel){
    const lines=[...panel.querySelectorAll('.formula-line')];
    const full=panel.dataset.mathSize==='full';
    let wide=false;
    for(const line of lines){
      const math=line.querySelector('math'),cs=getComputedStyle(line);
      const available=line.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight)-2;
      if(available<=0)continue;
      math.style.zoom='1';
      const content=math.getBoundingClientRect().width;
      const overflow=line.scrollWidth>line.clientWidth+1 ? line.scrollWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight) : 0;
      const natural=Math.max(content,math.scrollWidth,overflow);
      const ratio=Math.min(1,available/Math.max(natural,1));
      wide||=ratio<.995;
      if(canFit)math.style.zoom=full?'1':String(ratio);
      if(!full){
        if(canFit)for(let i=0;i<8&&line.scrollWidth>line.clientWidth+1;i++){
          const painted=math.getBoundingClientRect().width;
          const shrink=Math.min(.94,available/Math.max(line.scrollWidth,painted));
          math.style.zoom=String((parseFloat(math.style.zoom)||1)*shrink);
          wide=true;
        }
        line.scrollLeft=0;
      }
    }
    let toggle=panel.querySelector('button.math-size');
    if(wide&&canFit){
      if(!toggle){
        toggle=document.createElement('button');toggle.type='button';toggle.className='math-size';
        panel.querySelector('.tex-source').before(toggle);
        toggle.addEventListener('click',()=>{panel.dataset.mathSize=panel.dataset.mathSize==='full'?'fit':'full';fit(panel)});
      }
      toggle.hidden=false;toggle.textContent=full?'整式适宽显示':'按原字号横向阅读';
      toggle.setAttribute('aria-pressed',String(full));
    }else if(toggle)toggle.hidden=true;
  }
  function fitAll(){panels.forEach(fit)}
  document.addEventListener('readercolumnchange', fitAll);
  document.fonts.ready.then(fitAll);requestAnimationFrame(fitAll);
  let tick=0;addEventListener('resize',()=>{cancelAnimationFrame(tick);tick=requestAnimationFrame(fitAll)});
})();
