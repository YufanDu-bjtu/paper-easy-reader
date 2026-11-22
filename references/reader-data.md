# 排版数据与核对方法

把论文内容整理为 UTF-8 JSON。这里的文件由执行 skill 的助手在临时工作目录准备。用户只需提供论文或可访问的来源。排版器使用 Python 3.9+ 标准库，字体、样式、脚本自动内嵌。读取本地 PDF 的辅助程序使用 PyMuPDF，HTML/XML 使用 lxml；也可用其他可靠的来源阅读工具。

## 从原件到段落

- 本地 PDF 可运行 `python scripts/source_material.py inspect paper.pdf work/raw.json`。按一基页码查看文本块、坐标和候选位图。多栏 PDF 需对照可见原页重建阅读顺序。公式与矢量图可能完全没有独立位图，扫描页须 OCR 后对着原图校对。
- 需要核图时运行 `python scripts/source_material.py page paper.pdf 4 work/figure-2.png --rect 47 61 510 335`。坐标是当前页显示坐标中的 PDF 点。旋转页先看不带 `--rect` 的整页。多个面板、共享图例、跨页表格宜保留完整区域或多个原页。
- 出版社 HTML 或 JATS XML 同样可以用 `inspect` 抽取标题、段落及 MathML。裸 DOI/题名先在浏览器或正常学术渠道解析，记下原始页面 URL、版本、补充材料入口及实际取得的文件；只有摘要时保留候选状态。内嵌图与正文的编号、分面、图注须相互吻合。
- 对原件单独记下正文、附录和附件中的段落范围与对象编号。特别核对 A.1、C1、S1 等编号、子公式与跨页续表，同一图的多个分面合为一个对象。无编号的重要方程照原式录入，使用可区分的阅读标签。将这份清单逐项与成品对照。

## 最小有效结构

下例仅示意字段和一组对应句，不作论文及来源证据。实际任务应覆盖约定的全文范围，依据实读填写所有内容。

```json
{
  "meta": {
    "title_en": "Example title", "title_zh": "示例题名", "journal": "示例刊物", "date": "出版日期待核",
    "authors": [{"name": "作者署名", "aff": ["1"]}], "affiliations": [{"id": "1", "name": "已核实的署名单位"}],
    "metrics": []
  },
  "source": {"scope":"excerpt", "version": "用户提供的正式稿", "formal_pdf": "verified", "coverage": "正文及随文附录，附件状态按实际填写。", "doi": "", "url": ""},
  "framework": [{"title": "观测", "text": "写出采集的实际信号。"}, {"title": "推断", "text": "说明信号如何支持目标结论。"}],
  "sections": [{
    "id": "methods", "level": 1, "number": "2", "en": "Methods", "zh": "方法",
    "blocks": [{
      "loc": "原稿第 3 页，方法第 1 段",
      "pairs": [{"en": ["We measured ", {"text": "flow rate", "role": "concept"}, "."], "zh": "研究测量了流量。"}],
      "notes": [{"label": "这个量怎样取得", "text": "指明仪器、采样位置及归一化处理，并说明该观测能约束的结论。"}]
    }, {"object": "eq1"}]
  }],
  "objects": [{"id":"eq1","kind":"equation","label":"式（1）","loc":"原稿第 3 页","status":"verified","mathml":"<math><mi>Q</mi><mo>=</mo><mi>A</mi><mi>v</mi></math>","tex":"Q=Av","note":"在真实任务中按原文给出变量、单位和条件。"}],
  "prior": [],
  "argument": {"chain":["提出问题","给出可量化的对应关系","用对照检验"],"claim":"核心主张","strong":"证据最有判别力的环节及理由","weak":"最薄弱的证据环节及其影响"}
}
```

## 正文、数学和图表

- `sections` 是按阅读次序排列的平面列表。层级使用 `level` 1–6。`en` 与 `zh` 写标题正文，将印刷编号仅放入 `number`。原文无编号时可加 `"editorial":true` 和阅读序号，避免与印刷章号混淆。摘要、附录、参考文献和声明等按实际来源处理。每一 `blocks` 项是一个有页码或节段定位的段落，或一个指向图、表、公式的对象引用。
- `pairs` 的每一项是一次联动的语义单元，容许一对多、多对一。译文完整保留限定词、对照基准和数量级。同一标记组不能跨原文段落。富文本可以是字符串，或由字符串、`{"text":"…","role":"claim"}`、`{"mathml":"<math>…</math>"}` 组成的数组。`role` 为 `claim/result/method/concept/limit` 之一，只高亮原文语言。正文、译文、批注、图注和表格内的上下标与复杂数学优先用同行 MathML；直接放入 TeX 的普通字符串会按文字显示。
- `notes` 的元素可写为 `{"kind":"编者 · 推导练习","label":"为什么多出一个长度因子？","text":"…"}`。可选字段 `kind` 标明作者观点、作者局限或编者的解释、例算和延伸设想。为这一段选真正值得解释的内容。例如测量量与反演量如何区分、公式需要哪些边界条件、看同一张图为什么可能得到两种解释。指明相关图、式、页与结论，分别标明原文、独立解读、待验证设想。避免逐段重复同一句批评。
- 对象 `id` 采用以英文字母开头的稳定标识，每个对象只放置一次，可作为独立的 `blocks` 项，或在引导该式的句组中使用 `equations_after`，其他正文可正常引用其印刷编号。对象要有 `kind`（`figure/table/equation`）、`label`、`loc`、`status`；可带 `url`、`caption_en`、`caption_zh`、`note`。补充材料放入独立双语章节，用 `loc` 和 `label` 区分与正文重号的对象。
- 公式优先用出版社的原生 MathML。没有机器可读公式时，对照排印逐项转写为展示 MathML；有 LaTeX 可用本地可靠的数学工具转换，亦可直接编写等价 MathML。检查积分上下限、负号、分式、向量、矩阵和条件分支。单行公式用 `mathml`，多个原排版行可用 `lines`（每项均为完整 MathML）。`tex` 是可复制的原义 LaTeX；仅有 MathML 时，成品直接显示该源码。
- 图像采用 `"images":[{"file":"figure-2.png","alt":"图 2，含 a–d 分面"}]`。相对路径以 JSON 为基准。多张图像或跨页原表须按顺序列全，图号、坐标、单位、图例均应清晰。可以只保留一张完整原页并注明页码。表格可用 `table` 表示二维行数组。单元格是字符串或 `{"text":富文本,"head":true,"rowspan":2,"colspan":1}`。表注放在 `note`，表格和原页也可同时提供。图注译文与图件逐一对应。
- 缺件使用 `"status":"pending","reason":"只有图注，原图待核"`，尽可能保留图号、已核图注和 DOI。阅读版本 `source.formal_pdf` 取 `verified`、`pending`、`preprint` 或 `not-applicable`。正式刊发、当前只能读作者稿时选 `pending`，写明作者稿记录。只有预印本时选 `preprint` 并注明评审状态；电子期刊本来就只提供 HTML 时按原件事实填写。
- 期刊指标各为 `{"name":"影响因子","value":"实际核验值","basis":"具体年份、统计口径、来源名称","url":"权威来源 URL"}`。其余三个字段名为“中科院分区”“新锐分区”“年发文量”。缺省显示待核验，预印本使用不适用。作者多重单位以数组关联，中国高校按发表时署名使用经核验的正式中文校名。
- `prior` 记录最相关作者/团队研究及前序对照，每条填 `title`（含年份）、`url`、`status`（全文、部分、仅书目）、`comparison`（团队身份依据、延续/变化和证据）。没有可核实工作时可用一条写明已检查的范围及比较缺口，不虚构出处。
- 仅在已有周报或合集中集成单篇时，填写顶层 `home`、`issue` 为从成品到既有首页、当期总览的相对路径，可加期次锚点。独立论文省略。原始论文入口用 HTTP(S) URL，离线正文与图表可独立阅读。

- 全文填写 `source.scope="full"`，指定节选填写 `"excerpt"`；未填时使用通用标题“论证结构”。中文原稿填写 `meta.original_language="zh"`，页面会标明英文译文和中文原文。正文富文本中可用 `{"ref":"eq1","text":"式（1）"}` 直接链接原件。
- 技术路线按来源决定拓扑。顺序流程只需逐步给标题和说明；有并行观测、不同方法或汇合节点时，给步骤设置唯一 `id` 和 `from` 数组（前驱 ID），将前驱列在它的下游之前。例如两个独立输入分别为 `scan` 和 `test`，对照节点可写 `{"id":"compare","from":["scan","test"],"title":"模型对照","text":"说明实际比较的同一输出。" }`。

## 周报式精读与文末书目

周报版可用顶层 `question` 提供技术路线的研究问题。`study` 是精读小节数组，每项写 `title`、`text`，正文可嵌入指向原件的 `ref`。有正式原稿且允许内嵌时，将各页转成清晰的本地图像，在 `pages` 中逐项填写 `number`、`file`、`alt`。对应段落用 `pages: [13, 14]` 连接跨页原稿。

正文原文的富文本数组中，把原样摘出的关键词组写作 `{"text":"time-averaged flow rate","role":"concept"}`。其余词句保留为相邻字符串。段落可指定主要 `role`，用 `logic` 说明它如何推进论证，用 `evidence: [{"id":"fig3","label":"图3"}]` 连接证据。原英文中的词序、标点和空格均需保留。标注关键结论时保留比较基准与适用范围。旧材料的 thesis 和 term 分别按 claim 和 concept 显示；旧 data 与 caveat 保留原文，重新阅读后可对属于关键结论或不足的短语重新标注。核验时分别清点实际 mark 元素和书目条目。

参考文献使用独立的 section，例如 `{"id":"refs","kind":"bibliography","en":"References","zh":"参考文献","entries":[{"label":"1","citation":"原文完整书目（不含前置编号）","doi":"原文所列 DOI"}]}`。无 DOI 时省略该字段。书目按原排列顺序输入，作者拼写、出版信息保持原样；独立参考文献不创建 `blocks` 或逐句对。使用其他引文体系时保留原始标识与引用文本；只有可确认的数字引文才自动跳转。

## 在推导中就地排公式

例如一段的 `pairs` 可写为：
```json
[{"en":"The balance is written as","zh":"平衡关系写作下式。","equations_after":["eq4a","eq4b"]},{"en":"Here Q denotes discharge.","zh":"这里 Q 为流量。"}]
```
两式按数组顺序出现在原文列的第一句组之后。对象仍在 `objects` 中登记一次，其他段落采用 `ref` 回引。旧材料的独立对象写法继续适用。跨页的定义使用段落的 `pages` 列出所有承接页。符号表沿用 `kind:"table"` 及富文本单元格；数学符号可用 `mathml`。编辑整理的索引在 `label` 中明示来源，不能当作作者的编号表。

## 浏览器核验

已具备 Node.js、Playwright 和 Chromium 时可运行 `node scripts/check_browser.cjs <成品.html>`；支持用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向本机 Edge/Chromium。它会阻断联网，解码图像，在手机和桌面检查公式边界、句对联动、目录和缩放。若环境只具备浏览器界面，亦可用相同操作检查。此检查不判断译文和图表的科学准确性。

在英中富文本中可用 {"sub":"eq"}、{"sup":"2"} 保留上下标。PDF 候选块含稳定的 source_block 和 bbox；坐标排序与文件存储顺序都须按原页复查。另从原稿独立写下已核公式对象 ID 的 JSON 数组，传给 check_reader.py 的 --equation-order 参数，可检出缺式、错序及错挂到文末的公式。公式的章内归属、变量含义和图表首引仍逐项人工核对。
