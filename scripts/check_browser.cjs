/* Optional offline UI check. Uses the caller's Playwright and installed Chromium. */
const fs = require("node:fs");
const path = require("node:path");
const {pathToFileURL} = require("node:url");
const {chromium} = require("playwright");

async function check(browser, file, width) {
  const mobile = width === 390;
  const page = await browser.newPage({viewport:{width, height:900}, hasTouch:mobile});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route(/^https?:\/\//, route => {
    errors.push("试图加载外部资源 "+route.request().url());
    return route.abort();
  });
  try {
    await page.goto(pathToFileURL(file).href, {waitUntil:"load"});
    await page.evaluate(async () => {
      await document.fonts.ready;
      window.dispatchEvent(new Event("resize"));
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });
    const summary = await page.evaluate(async mobile => {
      const defects = [];
      const elements = sel => [...document.querySelectorAll(sel)];
      if (document.documentElement.scrollWidth > innerWidth + 1) defects.push("整页横向溢出");
      for (const frame of elements(".formula-line")) {
        const m = frame.querySelector("math");
        const rect = m.getBoundingClientRect(), area = frame.getBoundingClientRect();
        if (m.namespaceURI !== "http://www.w3.org/1998/Math/MathML" || rect.height < 5 ||
            rect.top < area.top - 2 || rect.bottom > area.bottom + 2 ||
            frame.scrollWidth > frame.clientWidth + 2) defects.push("公式显示 "+frame.closest("figure").id);
      }
      for (const image of elements(".open-image img")) {
        image.loading="eager";
        try {await image.decode();} catch {defects.push("图像解码 "+image.alt);}
      }
      const node = document.querySelector(".row");
      const marks = elements(".row mark");
      const tones = new Map(marks.map(mark => [mark.className, getComputedStyle(mark).backgroundColor]));
      if ([...tones.values()].some(color => color === "rgba(0, 0, 0, 0)") ||
          new Set(tones.values()).size !== tones.size) defects.push("原文着色缺失或类别颜色重复");
      if (document.querySelector(".bibliography .row, .bibliography [data-pair]")) defects.push("书目混入三栏正文");
      const en=node.querySelector(".en")?.getBoundingClientRect(), zh=node.querySelector(".zh").getBoundingClientRect(), notes=node.querySelector(".notes").getBoundingClientRect();
      const mono=document.body.dataset.sourceLanguage==='zh';
      const visible=mono?[zh,notes]:[en,zh,notes];
      const horizontal=visible.slice(1).every((cell,i)=>cell.left>=visible[i].right-1);
      for(const r of elements('article.row')){
        if(!r.querySelector(':scope>.notes>.brief')?.textContent.trim())defects.push('正文缺少可见小结');
        const side=r.querySelector(':scope>.notes').getBoundingClientRect();
        const texts=[...r.querySelectorAll(':scope>.en,:scope>.zh')];
        if(!mobile&&side.height>Math.max(...texts.map(c=>c.getBoundingClientRect().height))+30)defects.push('默认右栏显著超高');
      }
      const stacked=visible.slice(1).every((cell,i)=>cell.top>=visible[i].bottom-1);
      const columns=horizontal?visible.length:(stacked?1:0);
      let columnWidths, contentHeights;
      if (horizontal) {
        const header = elements(".column-head > span");
        const cells = visible;
        if (header.some((cell, i) => Math.abs(cell.getBoundingClientRect().left - cells[i].left) > 1))
          defects.push("栏头与正文错位");
        columnWidths = cells.map(cell => Math.round(cell.width));
        contentHeights = (mono?[".zh",".notes"]:[".en",".zh",".notes"]).map(selector => Math.round(
          elements(".row > " + selector).reduce((height, cell) => height + cell.getBoundingClientRect().height, 0)
        ));
      }
      return {columns, columnWidths, contentHeights, highlights:marks.length, highlightColors:tones.size,
              references:elements(".bibliography > li").length,
              graphConnections:elements(".diagram path.edge").length,
              eqLines:elements(".formula-line").length, images:elements(".open-image").length, defects};
    }, mobile);
    errors.push(...summary.defects);
    if (summary.columns !== (mobile ? 1 : (await page.locator("body").getAttribute("data-source-language")==="zh"?2:3))) errors.push("列数异常");
    const citation = page.locator(".row .cite").first();
    if (await citation.count()) {
      const href = await citation.getAttribute("href");
      await citation.click();
      if (await page.evaluate(() => location.hash) !== href || !await page.locator(href).isVisible())
        errors.push("正文引文未定位到书目");
    }
    const pair = page.locator(".row .en [data-pair]").first();
    if(await pair.count()){
    const key = await pair.getAttribute("data-pair");
    const translation = page.locator('.zh [data-pair="'+key+'"]');
    if(mobile)await pair.tap(); else await pair.hover();
    if(!await translation.evaluate(e=>e.classList.contains("is-paired")))errors.push("英中联动");
    await translation.focus();
    if(!await pair.evaluate(e=>e.classList.contains("is-paired")))errors.push("中英键盘联动");
    }
    if(mobile)await page.locator("#menu").click();
    const target = page.locator(".toc-link").last();
    const hash = await target.getAttribute("href");
    await target.click();
    if(await page.evaluate(()=>location.hash)!==hash)errors.push("章节跳转失效");
    const picture = page.locator(".open-image").first();
    if(await picture.count()) {
      await picture.click();
      await page.locator("#zoom[open]").waitFor();
      await page.locator("#size").click();
      if(!await page.locator(".zoom-pan.native").count())errors.push("原图缩放");
      await page.locator("#close").click();
    }
    const wide = page.locator(".math-size:visible").first();
    if(await wide.count()){
      const panel = wide.locator("..");
      await wide.click();
      const reachable=await panel.evaluate(e=>[...e.querySelectorAll(".formula-line")].every(line=>{
        line.scrollLeft=line.scrollWidth;
        return line.querySelector("math").getBoundingClientRect().right <= line.getBoundingClientRect().right+2;
      }));
      if(!reachable || await panel.getAttribute("data-math-size")!=="full")errors.push("原字号公式末端不可达");
      await wide.click();
    }
    return {width,...summary,errors};
  } finally {
    await page.close();
  }
}

(async () => {
  const file=process.argv[2]&&path.resolve(process.argv[2]);
  if(!file||!fs.existsSync(file))throw new Error("用法：node check_browser.cjs <读本.html>");
  const executablePath=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{})});
  try{
    const results=[];
    for(const size of [1200,1440,390])results.push(await check(browser,file,size));
    console.log(JSON.stringify(results,null,2));
    if(results.some(r=>r.errors.length))process.exitCode=1;
  }finally{
    await browser.close();
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
