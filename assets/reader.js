(() => {
  function revealSource(hash) {
    if (!/^#(?:page-|ref-)/.test(hash)) return;
    const target = document.getElementById(hash.slice(1));
    const details = target?.closest('details');
    if (details) details.open = true;
  }
  revealSource(location.hash);
  window.addEventListener('hashchange', () => revealSource(location.hash));
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#page-"], a[href^="#ref-"]');
    if (link) revealSource(link.hash);
  });
  const menu=document.getElementById('menu'), toc=document.getElementById('toc');
  function setMenu(open, restore=false){
    document.body.classList.toggle('menu-open',open);
    menu.setAttribute('aria-expanded',String(open));
    if(open)toc.querySelector('nav a')?.focus({preventScroll:true});
    else if(restore)menu.focus({preventScroll:true});
  }
  menu.addEventListener('click',()=>setMenu(menu.getAttribute('aria-expanded')!=='true'));
  toc.addEventListener('click',e=>{if(e.target.closest('a'))setMenu(false)});
  document.addEventListener('click',e=>{if(!menu.contains(e.target)&&!toc.contains(e.target))setMenu(false)});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('menu-open'))setMenu(false,true)});
  const links=[...toc.querySelectorAll('.toc-link')], targets=links.map(a=>document.getElementById(a.hash.slice(1)));
  function current(){
    const offset=window.innerWidth<=1100?80:48;
    let n=-1;
    for(let i=0;i<targets.length;i++){if(targets[i].getBoundingClientRect().top<=offset)n=i;else break}
    links.forEach((a,i)=>{if(n===i)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')});
  }
  let tick=0;
  window.addEventListener('scroll',()=>{if(!tick)tick=requestAnimationFrame(()=>{tick=0;current()})},{passive:true});current();
  let active=[],hovered=null,focused=null,tapped=null;
  const paired=e=>e instanceof Element?e.closest('[data-pair]'):null;
  function select(e){
    active.forEach(s=>s.classList.remove('is-paired'));active=[];
    if(!e)return;
    active=[...e.closest('.row').querySelectorAll('[data-pair]')].filter(s=>s.dataset.pair===e.dataset.pair);
    active.forEach(s=>s.classList.add('is-paired'));
  }
  document.addEventListener('pointerover',e=>{if(e.pointerType!=='touch'){hovered=paired(e.target);select(hovered||focused||tapped)}});
  document.addEventListener('pointerout',e=>{if(e.pointerType!=='touch'){hovered=paired(e.relatedTarget);select(hovered||focused||tapped)}});
  document.addEventListener('focusin',e=>{focused=paired(e.target);select(focused||hovered||tapped)});
  document.addEventListener('focusout',e=>{focused=paired(e.relatedTarget);select(focused||hovered||tapped)});
  document.addEventListener('click',e=>{tapped=paired(e.target);select(tapped||focused||hovered)});
  const diagram=document.querySelector('.diagram'), graphic=diagram.querySelector('svg');
  function draw(){
    const box=diagram.getBoundingClientRect();
    const vertical=getComputedStyle(diagram.querySelector('.flow-stages')).flexDirection==='column';
    graphic.setAttribute('viewBox','0 0 '+box.width+' '+box.height);
    graphic.querySelectorAll('.edge').forEach(p=>p.remove());
    for(const node of diagram.querySelectorAll('.flow-node')){
      for(const key of node.dataset.from.split(' ').filter(Boolean)){
        const a=document.getElementById('flow-'+key).getBoundingClientRect(), b=node.getBoundingClientRect();
        const x1=(vertical?(a.left+a.right)/2:a.right)-box.left, x2=(vertical?(b.left+b.right)/2:b.left)-box.left;
        const y1=(vertical?a.bottom:(a.top+a.bottom)/2)-box.top, y2=(vertical?b.top:(b.top+b.bottom)/2)-box.top;
        const path=document.createElementNS('http://www.w3.org/2000/svg','path');
        path.setAttribute('class','edge');path.setAttribute('fill','none');path.setAttribute('stroke','#65816a');
        path.setAttribute('stroke-width','1.6');path.setAttribute('marker-end','url(#arrowend)');
        path.setAttribute('d',vertical?'M'+x1+' '+y1+'V'+((y1+y2)/2)+'H'+x2+'V'+(y2-2):'M'+x1+' '+y1+'H'+((x1+x2)/2)+'V'+y2+'H'+(x2-2));
        graphic.append(path);
      }
    }
  }
  new ResizeObserver(draw).observe(diagram);document.fonts.ready.then(draw);draw();
  const dialog=document.getElementById('zoom'),pan=dialog.querySelector('.zoom-pan'),full=pan.querySelector('img'),size=document.getElementById('size');let opener;
  function native(on){pan.classList.toggle('native',on);size.textContent=on?'适应窗口':'原始尺寸';size.setAttribute('aria-pressed',String(on));pan.scrollTo(0,0)}
  document.addEventListener('click',e=>{const b=e.target.closest('.open-image');if(!b)return;opener=b;const im=b.querySelector('img');full.src=im.src;full.alt=im.alt;document.getElementById('zoom-title').textContent=im.alt;native(false);dialog.showModal();document.getElementById('close').focus()});
  size.onclick=()=>native(!pan.classList.contains('native'));full.onclick=size.onclick;
  document.getElementById('close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{full.removeAttribute('src');opener?.focus({preventScroll:true})});
})();

// Use the rendered text, notes and equations of this paper to size its reading columns.
(() => {
  const head = document.querySelector('.column-head');
  const rows = [...document.querySelectorAll('article.row')];
  if (!head || !rows.length) return;
  const columns = ['.en', '.zh', '.notes'].map(selector =>
    rows.map(row => row.querySelector(':scope > ' + selector)).filter(Boolean));
  if (columns.some(cells => cells.length !== rows.length)) return;
  const main = head.closest('main');
  const sum = values => values.reduce((a, b) => a + b, 0);
  const clamp = (x, low, high) => Math.max(low, Math.min(x, high));

  // Allocate available width proportionally, reserving a readable measure for short columns.
  function allocate(weights, floors, width) {
    const result = floors.slice();
    let free = [0, 1, 2];
    let space = width;
    while (free.length) {
      const total = sum(free.map(i => weights[i]));
      const below = free.filter(i => space * weights[i] / total < floors[i]);
      if (!below.length) {
        for (const i of free) result[i] = space * weights[i] / total;
        break;
      }
      space -= sum(below.map(i => floors[i]));
      free = free.filter(i => !below.includes(i));
    }
    return result;
  }

  function setTracks(widths) {
    main.style.setProperty('--cols', widths.map(w => 'minmax(0,' + w.toFixed(2) + 'fr)').join(' '));
  }

  // A display equation following the last sentence belongs to both languages.
  // Share that line on desktop; keep it with its source sentence in the mobile reading order.
  const trailing = [];
  for (const row of rows) {
    for (const cell of [row.querySelector('.en'), row.querySelector('.zh')]) {
      const group = [];
      let last = cell.lastElementChild;
      while (last?.matches('figure.equation-panel')) {
        group.unshift(last);
        last = last.previousElementSibling;
      }
      if (group.length) trailing.push({row, cell, group});
    }
  }
  function positionEquations(shared) {
    let changed = false;
    for (const {row, cell, group} of trailing) {
      const target = shared ? row : cell;
      if (group[0].parentNode !== target) {
        target.append(...group);
        changed = true;
      }
    }
    return changed;
  }

  let lastWidth = 0;
  function balance() {
    if (getComputedStyle(head).display === 'none') {
      const moved = positionEquations(false);
      lastWidth = 0;
      main.style.removeProperty('--cols');
      if (moved) document.dispatchEvent(new Event('readercolumnchange'));
      return;
    }
    const box = head.getBoundingClientRect().width;
    if (!box || Math.abs(box - lastWidth) < 1) return;
    lastWidth = box;
    positionEquations(true);
    const available = box - 2 * parseFloat(getComputedStyle(head).columnGap);
    const font = parseFloat(getComputedStyle(main).fontSize);
    const floor = [12, 12, 10].map(ems => Math.min(ems * font, 0.25 * available));
    let widths = [...head.children].map(cell => cell.getBoundingClientRect().width);
    let bestWidths = widths.slice();
    let bestSpread = Infinity;
    for (let pass = 0; pass < 7; pass++) {
      const heights = columns.map(cells => sum(cells.map(cell => cell.getBoundingClientRect().height)));
      if (Math.min(...heights) <= 0) break;
      // A column at its readable minimum cannot donate further width.
      const donors = heights.filter((_, i) => widths[i] > floor[i] + 1);
      const spread = Math.max(...heights) / Math.min(...donors) - 1;
      if (spread < bestSpread) {
        bestSpread = spread;
        bestWidths = widths.slice();
      }
      if (spread < 0.018 || pass === 6) break;
      const proposed = allocate(widths.map((w, i) => w * heights[i]), floor, available);
      if (proposed.every((w, i) => Math.abs(w - widths[i]) < 0.8)) break;
      widths = proposed;
      setTracks(widths);
    }
    setTracks(bestWidths);
    document.dispatchEvent(new Event('readercolumnchange'));
  }

  let timer;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(balance, 90);
  }
  document.fonts.ready.then(balance);
  document.fonts.addEventListener('loadingdone', () => { lastWidth = 0; schedule(); });
  new ResizeObserver(schedule).observe(head);
})();
