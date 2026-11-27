"""Render a source-checked, annotated paper manifest as a self-contained UTF-8 HTML file."""

import argparse
import base64
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MATH = "http://www.w3.org/1998/Math/MathML"
ET.register_namespace("", MATH)
MATH_TAGS = set(
    """math semantics annotation mrow mi mn mo mtext mspace ms mfrac msqrt mroot
mstyle merror mpadded mphantom mfenced menclose msub msup msubsup munder mover munderover
mmultiscripts mprescripts none mtable mlabeledtr mtr mtd maligngroup malignmark maction""".split()
)
MATH_ATTRS = set(
    """display mathvariant mathsize displaystyle scriptlevel stretchy symmetric
maxsize minsize fence separator separators form accent accentunder movablelimits largeop lspace rspace
linethickness bevelled columnalign rowalign columnspacing rowspacing columnspan rowspan columnlines
rowlines frame framespacing equalrows equalcolumns columnwidth width height depth voffset open close
notation subscriptshift superscriptshift lquote rquote encoding side align mathcolor""".split()
)
CATEGORIES = {
    "claim": "关键论点／观点",
    "result": "关键结论",
    "method": "采用的方法",
    "concept": "重要概念",
    "limit": "不足与待改进",
    "data": "支撑数据",
}
# Keep earlier role names usable when regenerating a reader.
LEGACY_ROLES = {"thesis": "claim", "term": "concept", "caveat": "limit"}


def highlight_role(value):
    role = LEGACY_ROLES.get(value, value)
    if role and role not in CATEGORIES:
        raise ValueError(f"未知高亮类型 {role}")
    return role


METRICS = ("中科院分区", "新锐分区", "影响因子", "年发文量")
KINDS = {"figure": "图", "table": "表", "equation": "式"}
STATUS = {"verified": "已核对", "pending": "待核验"}
esc = html.escape


def need(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少文本字段 {key}")
    return value


def url(value, local=False):
    if any(ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError(f"无效链接 {value!r}")
    parts = urlsplit(value)
    if parts.scheme.lower() in ("https", "http") and parts.hostname:
        return esc(value, quote=True)
    if (
        local
        and not parts.scheme
        and not parts.netloc
        and not value.startswith(("/", "#"))
        and parts.path
    ):
        return esc(value, quote=True)
    raise ValueError(f"无效来源或导航链接 {value!r}")


def link(href, label, local=False):
    return f'<a href="{url(href, local)}">{esc(label)}</a>'


def mathml(source, display):
    if "<!" in source or "<?" in source:
        raise ValueError("MathML 仅接受公式元素")
    m = ET.fromstring(source)
    if m.tag not in ("math", f"{{{MATH}}}math"):
        raise ValueError("公式根元素应为 math")
    for node in m.iter():
        tag = node.tag.removeprefix("{" + MATH + "}")
        if tag not in MATH_TAGS or tag == "merror":
            raise ValueError(f"请核对数学元素 {tag}")
        node.tag = "{" + MATH + "}" + tag
        for key in list(node.attrib):
            if key not in MATH_ATTRS:
                del node.attrib[key]
    m.set("display", display)
    return ET.tostring(m, encoding="unicode", short_empty_elements=False)


def rich(value, highlight=False):
    if isinstance(value, str):
        return esc(value)
    if not isinstance(value, list):
        raise ValueError("正文应为文本或文本与数学片段数组")
    output = []
    for token in value:
        if isinstance(token, str):
            output.append(esc(token))
        elif "sup" in token or "sub" in token:
            tag = "sup" if "sup" in token else "sub"
            output.append(f"<{tag}>{esc(need(token, tag))}</{tag}>")
        elif "ref" in token:
            anchor = "obj-" + safe_id(token["ref"])
            output.append(f'<a href="#{anchor}">{esc(need(token, "text"))}</a>')
        elif "mathml" in token:
            output.append(mathml(token["mathml"], "inline"))
        else:
            phrase = esc(need(token, "text"))
            role = highlight_role(token.get("role"))
            output.append(
                f'<mark class="{role}" title="{CATEGORIES[role]}">{phrase}</mark>'
                if role and highlight
                else phrase
            )
    return "".join(output)


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][\w.-]*", value):
        raise ValueError(f"无效 ID {value!r}")
    return value


def font_css():
    rules = []
    for font, family, license_name in [
        ("Lora", "Lora", "lora"),
        ("Plex", "IBM Plex Sans", "plex"),
    ]:
        binary = base64.b64encode((ASSETS / (font + ".ttf")).read_bytes()).decode(
            "ascii"
        )
        license_text = (ASSETS / (license_name + ".license")).read_text("utf-8-sig")
        rules.append(
            f'/* {license_text.replace("*/", "* /")} */\n@font-face{{font-family:"{family}";src:url(data:font/ttf;base64,{binary}) format("truetype");font-weight:100 900;font-display:swap}}'
        )
    return "\n".join(rules)


def picture(base, item, fallback):
    raw = (base / need(item, "file")).read_bytes()
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    elif raw.startswith(b"\xff\xd8\xff"):
        kind = "jpeg"
    elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        kind = "webp"
    elif raw[:6] in (b"GIF87a", b"GIF89a"):
        kind = "gif"
    else:
        raise ValueError("请提供已核对的 PNG、JPEG、WebP 或 GIF 原图或原页")
    data = base64.b64encode(raw).decode("ascii")
    return f'<button type="button" class="open-image" aria-label="放大{esc(fallback)}"><img loading="lazy" decoding="async" src="data:image/{kind};base64,{data}" alt="{esc(item.get("alt") or fallback)}"></button>'


def link_citations(text, numbers):
    if not numbers:
        return text

    def group(match):
        def number(n):
            if n[0] in numbers:
                return f'<a class="cite" href="#ref-{n[0]}">{n[0]}</a>'
            return n[0]
        return re.sub(r"\d+", number, match[0])

    return re.sub(r"\[\d+(?:\s*[,，–−-]\s*\d+)*\]", group, text)


def table_html(rows, cite_numbers):
    cells = []
    for row in rows:
        if not row:
            raise ValueError("表格存在空行")
        line = []
        for cell in row:
            c = cell if isinstance(cell, dict) else {"text": cell}
            tag = "th" if c.get("head") else "td"
            attrs = ""
            for key in ("rowspan", "colspan"):
                if key in c:
                    val = int(c[key])
                    if val < 1:
                        raise ValueError(key)
                    attrs += f' {key}="{val}"'
            line.append(f"<{tag}{attrs}>{link_citations(rich(c['text']), cite_numbers)}</{tag}>")
        cells.append("<tr>" + "".join(line) + "</tr>")
    return (
        '<div tabindex="0" class="table-scroll"><table>'
        + "".join(cells)
        + "</table></div>"
    )


def render_object(o, base, source_url, cite_numbers):
    kind, status = o["kind"], o["status"]
    if kind not in KINDS or status not in STATUS:
        raise ValueError(f"原件类型或核验状态无效 {o.get('id')}")
    label, loc = need(o, "label"), need(o, "loc")
    ident = "obj-" + safe_id(o["id"])
    source = o.get("url") or source_url
    head = f'<div class="obj-head"><b>{esc(label)}</b><span>{esc(loc)}'
    if source:
        head += " · " + link(source, "来源")
    head += "</span></div>"
    content = []
    if status == "pending":
        content.append('<p class="pending">' + esc(need(o, "reason")) + "</p>")
        if kind in ("figure", "table"):
            if o.get("table"):
                content.append(table_html(o["table"], cite_numbers))
            content.extend(picture(base, img, label) for img in o.get("images", []))
    elif kind == "equation":
        lines = o.get("lines") or [need(o, "mathml")]
        for s in lines:
            content.append(
                '<div class="formula-line" tabindex="0">'
                + mathml(s, "block")
                + "</div>"
            )
        code = o.get("tex") or "\n".join(lines)
        fmt = "LaTeX" if o.get("tex") else "MathML"
        content.append(
            f'<details class="tex-source"><summary>查看 {fmt} 源码</summary><pre>{esc(code)}</pre></details>'
        )
    else:
        if o.get("table"):
            content.append(table_html(o["table"], cite_numbers))
        content.extend(picture(base, img, label) for img in o.get("images", []))
        if not content:
            raise ValueError(f"{label} 已标为核对，却无图像或表格内容")
    for key, lang in (("caption_en", "en"), ("caption_zh", "zh"), ("note", "zh")):
        if o.get(key):
            content.append(f'<p class="caption" lang="{lang}">{rich(o[key])}</p>')
    cls = "equation-panel" if kind == "equation" and status == "verified" else "object"
    return f'<figure id="{ident}" class="{cls}">{head}{"".join(content)}</figure>'


def paragraph(p, index, original="en", cite_numbers=(), page_numbers=(), render_equation=None):
    en_label, zh_label = (
        ("英文译文", "中文原文") if original == "zh" else ("英文原文", "中文意译")
    )
    sentences = p["pairs"]
    notes=p.get("notes",[])
    summary=p.get("summary") or next((n["text"] for n in notes if n.get("label") in ("本段小结","段落小结")),None)
    if not sentences or not isinstance(summary,str) or not summary.strip():
        raise ValueError(f"第 {index} 段缺少可见中文小结 summary")
    require_zh=lambda v: bool(re.search(r"[\u3400-\u9fff]",v))
    if not require_zh(summary):raise ValueError(f"第 {index} 段的小结需使用中文说明")
    en, zh = [], []
    for i, pair in enumerate(sentences, 1):
        for field, target in ((("zh",zh),) if original=="zh" else (("en", en), ("zh", zh))):
            s = rich(pair[field], field == original)
            s = link_citations(s, cite_numbers)
            if not s.strip():
                raise ValueError(f"空句对 {index}.{i}")
            target.append(f'<span tabindex="0" data-pair="{index}-{i}">{s}</span>')
        equation_keys = pair.get("equations_after", [])
        if not isinstance(equation_keys, list) or not all(isinstance(key, str) for key in equation_keys):
            raise ValueError("equations_after 应为公式对象 ID 数组")
        for key in equation_keys:
            if render_equation is None:
                raise ValueError("段内公式缺少对象清单")
            (en if original == "en" else zh).append(render_equation(key))
    annotations = []
    for n in notes:
        if n.get("label") in ("本段小结","段落小结") and n["text"]==summary:continue
        byline = ""
        if n.get("kind"):
            byline = f'<span class="note-kind">{esc(need(n, "kind"))}</span>'
        annotations.append(
            f'<div class="annotation">{byline}<strong>{esc(need(n, "label"))}</strong><p>{rich(n["text"])}</p></div>'
        )
    role = highlight_role(p.get("role"))
    reading = ""
    if p.get("logic"):
        reading = f'<details class="logic"><summary>段落功能与论证位置</summary><b>{CATEGORIES.get(role,"")}</b><p>{rich(p["logic"])}</p></details>'
    pages = "".join(f'<a href="#page-{i}">原稿第 {i} 页</a> ' for i in p.get("pages", []) if i in page_numbers)
    evidence = "".join(f'<a href="#obj-{safe_id(r["id"])}">{esc(need(r,"label"))}</a> ' for r in p.get("evidence", []))
    return (
        f'<article class="row" id="para-{index}"><div class="loc">{pages or esc(need(p, "loc"))}'
        + (f'<button class="note-toggle" type="button" aria-expanded="false" aria-controls="detail-{index}">展开解读</button>' if annotations or evidence or reading else '')+'</div>'
        + (f'<div class="en" lang="en"><span class="mobile-label">{en_label}</span>{" ".join(en)}</div>' if original!="zh" else '')
        + f'<div class="zh"><span class="mobile-label">{zh_label}</span>{"".join(zh)}</div>'
        + f'<aside class="notes"><p class="brief" aria-label="本段小结">{esc(summary)}</p>'
        + (f'<div hidden id="detail-{index}" class="deep-panel">{"".join(annotations)}<div class="evidence">{evidence}</div>{reading}</div>' if annotations or evidence or reading else '')
        + '</aside></article>'
    )


def header(m, legend, doi_url, nav):
    authors, affiliations = m["authors"], m["affiliations"]
    if not authors:
        raise ValueError("请填写作者或原文署名状态")
    marks = {str(a["id"]) for a in affiliations}
    if len(marks) != len(affiliations):
        raise ValueError("单位编号重复")
    names = []
    for a in authors:
        refs = [str(v) for v in a.get("aff", [])]
        if not set(refs) <= marks:
            raise ValueError("作者单位编号无对应单位")
        sup = f"<sup>{esc(','.join(refs))}</sup>" if refs else ""
        names.append(esc(need(a, "name")) + sup)
    institution = "　".join(
        f"<sup>{esc(str(a['id']))}</sup> {esc(need(a, 'name'))}" for a in affiliations
    ) or esc(m.get("affiliation_status", "单位待核验"))
    metrics = {v["name"]: v for v in m.get("metrics", [])}
    metric_html = []
    for key in METRICS:
        item = metrics.get(key, {})
        value = esc(item.get("value", "待核验"))
        if item.get("url"):
            value += " · " + link(item["url"], need(item, "basis"))
        elif item.get("basis"):
            value += " · " + esc(item["basis"])
        elif item.get("value") and item["value"] not in ("待核验", "不适用"):
            raise ValueError(f"{key} 需注明版次、统计口径和依据")
        metric_html.append(f"<div><dt>{key}</dt><dd>{value}</dd></div>")
    doi_link = link(doi_url, "DOI ↗") if doi_url else ""
    heading=(f'<h1>{esc(need(m,"title_zh"))}</h1>' if m.get("original_language")=="zh" else f'<h1 lang="en">{esc(need(m,"title_en"))}</h1><p class="title-zh">{esc(need(m,"title_zh"))}</p>')
    return (
        f'<header><div class="mast-line"><span>{nav or "论文精读"}</span><a href="#framework">技术路线图 ↓</a></div>'
        +heading
        + f'<p class="authors">{" · ".join(names)}</p><p class="affiliations">{institution}</p>'
        f'<p class="pubdate">{esc(need(m, "date"))}　{doi_link}</p>'
        f'<dl class="metrics"><div><dt>期刊</dt><dd>{esc(need(m,"journal"))}</dd></div>{"".join(metric_html)}</dl>'
        f'<div class="legend">{legend}</div></header>'
    )


def framework_html(steps, question=""):
    stages = []
    levels = {}
    lookup = {}
    branched = any("from" in step for step in steps)
    for i, step in enumerate(steps):
        key = safe_id(step.get("id", f"step-{i + 1}"))
        parents = (
            step.get("from", [])
            if branched
            else ([next(reversed(levels))] if i else [])
        )
        if (
            key in levels
            or not isinstance(parents, list)
            or any(p not in levels for p in parents)
        ):
            raise ValueError("技术路线的节点 ID 需唯一，前驱节点须先列出")
        level = max((levels[p] for p in parents), default=-1) + 1
        if len(stages) <= level:
            stages.append([])
        levels[key] = level
        lookup[key] = need(step, "title")
        ancestry = "，".join(lookup[p] for p in parents)
        stages[level].append(
            f'<li class="flow-node" id="flow-{key}" data-from="{esc(" ".join(parents))}"><b>{esc(lookup[key])}</b><p>{rich(step["text"])}</p><span class="sr-only">{esc("依据：" + ancestry) if ancestry else ""}</span></li>'
        )
    columns = "".join(
        '<ul class="stage">' + "".join(nodes) + "</ul>" for nodes in stages
    )
    return f'<section id="framework"><h2>技术路线图</h2><p class="route-question">{esc(question)}</p><div class="diagram"><svg aria-hidden="true" class="connect"><defs><marker id="arrowend" markerWidth="5" markerHeight="5" refX="4.6" refY="2.5" orient="auto"><path d="M0 0L5 2.5L0 5Z" fill="#65816a"></path></marker></defs></svg><div class="flow-stages">{columns}</div></div></section>'


def bibliography_entries(section, original):
    if "entries" in section:
        return section["entries"]
    # Older manifests grouped bibliography entries as aligned sentence pairs.
    entries = []
    for block in section.get("blocks", []):
        for pair in block.get("pairs", []):
            citation = pair[original]
            match = re.match(r"^\s*\[?(\d+)(?:\]|\.)\s+(.*)", citation) if isinstance(citation, str) else None
            entries.append({"label": match[1] if match else str(len(entries) + 1),
                            "citation": match[2] if match else citation})
    return entries


def render(data, base):
    from reading_units import validate_units
    validate_units(data)
    source = data["source"]
    original = data["meta"].get("original_language", "en")
    mono=original=='zh'
    if original not in ("en", "zh"):
        raise ValueError("本读本支持英中双语，请明确原文语言")
    en_label, zh_label = (
        ("英文译文", "中文原文") if original == "zh" else ("英文原文", "中文意译")
    )
    scope_name = source.get("scope")
    argument_heading = {
        "full": "全文论证结构",
        "excerpt": "节选论证结构",
        None: "论证结构",
    }[scope_name]
    claim_heading = "本节主张" if scope_name == "excerpt" else "作者核心主张"

    source_url = source.get("url")
    doi = source.get("doi")
    doi_url = "https://doi.org/" + doi if doi else ""
    sources = []
    if doi_url:
        sources.append(link(doi_url, "DOI · " + doi))
    if source_url and source_url != doi_url:
        sources.append(link(source_url, "原文入口"))
    for href_value, caption in (
        (data.get("home"), "返回周报列表"),
        (data.get("issue"), "本期周报"),
    ):
        if href_value:
            sources.append(link(href_value, caption, True))
    version = esc(need(source, "version"))
    scope = esc(need(source, "coverage"))
    status = ""
    if source.get("formal_pdf") == "pending":
        status = '<strong class="pending">待补正式 PDF</strong> · '
    elif source.get("formal_pdf") not in ("verified", "preprint", "not-applicable"):
        raise ValueError("请注明正式 PDF 的状态")
    if source.get("formal_pdf") == "preprint":
        status = "<strong>预印本</strong> · "
    version_box = f'<section class="source"><p>{status}{scope}</p><details><summary>阅读版本、原件与许可</summary><p>{version}</p><p>{"　".join(sources)}</p></details></section>'
    objects = {}
    for item in data["objects"]:
        key = safe_id(item["id"])
        if key in objects:
            raise ValueError(f"重复原件 {key}")
        objects[key] = item
    flow = data["framework"]
    if not flow:
        raise ValueError("缺少论文技术路线")
    framework = framework_html(flow, data.get("question", ""))
    toc = ['<a href="#framework">技术路线图<span>Research framework</span></a>']
    bib = {s["id"]: bibliography_entries(s, original) for s in data["sections"]
           if s.get("kind") == "bibliography" or s["en"].strip().casefold() in ("references", "bibliography") or s["zh"].strip()=="参考文献"}
    cite_numbers = {str(e["label"]) for entries in bib.values() for e in entries}
    pages = data.get("pages", [])
    page_numbers = {int(p["number"]) for p in pages}
    sections = []
    used = set()
    ids = set()
    index = 0
    if not data["sections"]:
        raise ValueError("缺少论文章节")
    def place_equation(key):
        if key not in objects or objects[key]["kind"] != "equation" or key in used:
            raise ValueError(f"段内公式未登记、类型错误或重复放置 {key}")
        used.add(key)
        return render_object(objects[key], base, source_url or doi_url, cite_numbers)

    for sec in data["sections"]:
        key = safe_id(sec["id"])
        if key in ids:
            raise ValueError(f"重复章节 {key}")
        ids.add(key)
        level = int(sec.get("level", 1))
        if not 1 <= level <= 6:
            raise ValueError("目录层级需为 1–6")
        en, zh = esc(need(sec, "en")), esc(need(sec, "zh"))
        num = esc(str(sec.get("number", "")))
        if sec.get("editorial") and not num:
            raise ValueError("请填写阅读序号")
        number = (
            f"<small>{'阅读序号 ' if sec.get('editorial') else ''}{num}</small>"
            if num
            else ""
        )
        toc.append(
            f'<a class="toc-link" style="--level:{level}" href="#sec-{key}">{number}{zh}{"" if mono else "<span lang=en>"+en+"</span>"}</a>'
        )
        tag = "h" + str(min(level + 1, 6))
        blocks = [
            f'<{tag} class="sec-title">{number}{zh}{"" if mono else "<span lang=en>"+en+"</span>"}</{tag}>'
        ]
        if key in bib:
            items = []
            for entry in bib[key]:
                label = str(entry["label"])
                anchor = safe_id("ref-" + label)
                doi = link("https://doi.org/" + entry["doi"], "DOI ↗") if entry.get("doi") else ""
                items.append(f'<li id="{anchor}"><span class="bib-label">[{esc(label)}]</span><span>{rich(entry["citation"])} {doi}</span></li>')
            blocks.append(f'<details class="bib-list"><summary>查看 {len(items)} 条参考文献</summary><ol class="bibliography">' + "".join(items) + '</ol></details>')
            sections.append(f'<section class="bibliography-section" id="sec-{key}">{"".join(blocks)}</section>')
            continue
        for p in sec["blocks"]:
            if "object" in p:
                obj = p["object"]
                if obj in used or obj not in objects:
                    raise ValueError(f"原件位置重复或未登记 {obj}")
                used.add(obj)
                blocks.append(render_object(objects[obj], base, source_url or doi_url, cite_numbers))
            else:
                index += 1
                blocks.append(paragraph(p, index, original, cite_numbers, page_numbers, place_equation))
        sections.append(
            f'<section class="paper-section" id="sec-{key}">{"".join(blocks)}</section>'
        )
    if used != set(objects):
        raise ValueError(
            "有原件未放入正文或附件：" + ", ".join(sorted(set(objects) - used))
        )
    if index == 0:
        raise ValueError("缺少双语正文")
    if objects:
        items = "".join(
            f'<a href="#obj-{key}">{esc(o["label"])}{" · 待核" if o["status"] == "pending" else ""}</a>'
            for key, o in objects.items()
        )
        toc.insert(0, f'<details><summary>图表与公式索引</summary><div class="object-links">{items}</div></details>')
    originals = ""
    if pages:
        originals = '<section id="originals"><h2>原页索引</h2>'
        for p in pages:
            num = int(p["number"])
            originals += f'<details id="page-{num}"><summary>第 {num} 页 · 原稿</summary>{picture(base,p,"PDF 第 "+str(num)+" 页")}</details>'
        originals += '</section>'
        toc.append('<a href="#originals">原页索引<span>Original pages</span></a>')
    study = ""
    if data.get("study"):
        toc.append('<a href="#study">精读与证据核验<span>Critical reading</span></a>')
        study = '<section id="study"><h2>精读与证据核验</h2>' + "".join(
            f'<article><h3>{esc(need(item,"title"))}</h3><p>{rich(item["text"])}</p></article>'
            for item in data["study"]) + '</section>'
    conclusion = data["argument"]
    lineage = ""
    if data.get("prior"):
        rows = []
        for item in data["prior"]:
            detail = rich(item["comparison"])
            title = (
                link(item["url"], need(item, "title"))
                if item.get("url")
                else esc(need(item, "title"))
            )
            rows.append(
                f"<li><b>{title}</b> · {esc(need(item, 'status'))}<p>{detail}</p></li>"
            )
        lineage = (
            '<section id="lineage"><h2>作者与前序研究</h2><ul>'
            + "".join(rows)
            + "</ul></section>"
        )
        toc.append('<a href="#lineage">作者与前序研究</a>')
    toc.append(f'<a href="#argument">{argument_heading}</a>')
    claim = rich(conclusion["claim"])
    chain = "".join(f"<li>{rich(x)}</li>" for x in conclusion["chain"])
    if not chain:
        raise ValueError("缺少论证链")
    argument = f'<section id="argument"><h2>{argument_heading}</h2><ol>{chain}</ol><div class="syn"><h3>{claim_heading}</h3><p>{claim}</p></div><div class="compare"><div><h3>论证最强处</h3><p>{rich(conclusion["strong"])}</p></div><div><h3>论证最弱处</h3><p>{rich(conclusion["weak"])}</p></div></div></section>'
    if data.get("related"):
        links=[]
        for peer in data['related']:
            links.append('<li>'+link(peer['href'],need(peer,'title'),True)+'<p>'+rich(peer['comparison'])+'</p></li>')
        sections.append('<section id="related"><h2>相似研究</h2><ul>'+''.join(links)+'</ul></section>')
        toc.append('<a href="#related">相似研究</a>')
    roles = {highlight_role(token.get("role")) for sec in data["sections"] if sec["id"] not in bib
             for block in sec.get("blocks", []) for pair in block.get("pairs", [])
             if isinstance(pair[original], list) for token in pair[original] if isinstance(token, dict)}
    legend = "".join(f'<span><i class="{c}"></i>{v}</span>' for c,v in CATEGORIES.items() if c in roles)
    style = font_css() + (ASSETS / "reader.css").read_text("utf8")
    script = (
        (ASSETS / "reader.js").read_text("utf8")
        + "\n"
        + (ASSETS / "math-fit.js").read_text("utf8")
    )
    nav = (
        "　".join(sources[-int(bool(data.get("home")) + bool(data.get("issue"))) :])
        if data.get("home") or data.get("issue")
        else ""
    )
    pair_hint = '<p class="pair-hint">悬停或点选中英文句子可查看对应译文。键盘可用 Tab 聚焦。</p>' if original == "en" else ""
    extra=(ASSETS / "reading-units.html").read_text("utf8")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data["meta"]["title_zh"])}</title><style>{style}</style>{extra}</head><body id="top" class="{'mono' if original=='zh' else 'bilingual'}" data-source-language="{original}">
<div class="mobile-bar"><button id="menu" aria-expanded="false" aria-controls="toc">章节目录</button>{nav}</div><div class="layout"><aside id="toc"><div class="toc-nav">{nav}</div><h2>论文章节目录</h2><nav>{"".join(toc)}</nav></aside>
<div class="paper-view">{header(data["meta"],legend,doi_url,nav)}<main>{version_box}{framework}{pair_hint}<div class="column-head">{'' if original=='zh' else '<span>'+en_label+'</span>'}<span>{zh_label}</span><span>本段小结与解读</span></div>{"".join(sections)}{originals}{study}{lineage}{argument}<footer>{nav}　<a href="#top" id="back-top">返回页首</a></footer></main></div></div>
<dialog id="zoom" aria-labelledby="zoom-title"><div class="dialog-bar"><b id="zoom-title">原图</b><button id="size">原始尺寸</button><button id="close">关闭</button></div><div class="zoom-pan" tabindex="0"><img alt=""></div></dialog><script>{script}</script></body></html>""".replace(
        "<body>", '<body id="top">', 1
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text("utf-8-sig"))
    result = render(data, args.manifest.resolve().parent).encode("utf8")
    dest = args.output.resolve()
    if dest.suffix.lower() != ".html":
        parser.error("输出文件应使用 .html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    candidate = dest
    version = 1
    while True:
        try:
            f = candidate.open("xb")
        except FileExistsError:
            version += 1
            candidate = dest.with_name(f"{dest.stem}_v{version}{dest.suffix}")
            continue
        try:
            with f:
                f.write(result)
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
        break
    print(candidate)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, ET.ParseError) as error:
        sys.exit(f"生成失败：{error}")
