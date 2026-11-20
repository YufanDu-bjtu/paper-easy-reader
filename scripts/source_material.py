"""Extract local source material for editorial review, or render a complete PDF page / checked rectangle."""

import argparse
import json
from pathlib import Path


def pdf_module():
    try:
        import fitz

        return fitz
    except ImportError:
        raise SystemExit(
            "读取 PDF 需 PyMuPDF，也可用现有 PDF 阅读工具提取原件后直接使用排版脚本。"
        )


def inspect_pdf(path):
    lib = pdf_module()
    with lib.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("需要用户可阅读的解密版本")
        pages = []
        for pg in doc:
            blocks = [
                {"bbox": list(b[:4]), "text": b[4]}
                for b in pg.get_text("blocks", flags=lib.TEXTFLAGS_TEXT, sort=True)
                if b[4].strip()
            ]
            images = [
                {"bbox": list(b["bbox"]), "width": b["width"], "height": b["height"]}
                for b in pg.get_image_info()
            ]
            pages.append(
                {
                    "page": pg.number + 1,
                    "size": list(pg.rect),
                    "rotation": pg.rotation,
                    "blocks": blocks,
                    "image_candidates": images,
                    "text_extracted": bool(blocks),
                }
            )
        return {
            "type": "PDF",
            "metadata": doc.metadata,
            "bookmarks": doc.get_toc(),
            "pages": pages,
        }


def inspect_html(path):
    try:
        from lxml import etree, html
    except ImportError:
        raise SystemExit(
            "读取 HTML/XML 需 lxml，也可在浏览器中直接阅读来源并整理材料。"
        )
    raw = path.read_bytes()
    if path.suffix.lower() in (".xml", ".nxml", ".xhtml"):
        root = etree.fromstring(
            raw, etree.XMLParser(resolve_entities=False, no_network=True)
        )
    else:
        root = html.fromstring(
            raw,
            parser=html.HTMLParser(
                encoding="utf-8" if b"charset" not in raw[:2000].lower() else None
            ),
        )

    def tag(e):
        return etree.QName(e).localname.lower() if isinstance(e.tag, str) else ""

    accepted = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "title",
        "article-title",
        "p",
        "fig",
        "figure",
        "table",
        "table-wrap",
        "disp-formula",
        "math",
        "img",
    }
    scopes = [e for e in root.iter() if tag(e) in ("article", "main")]
    start = next(
        (e for e in scopes if tag(e) == "article"), scopes[0] if scopes else root
    )
    blocks = []
    for e in start.iter():
        typ = tag(e)
        if typ not in accepted:
            continue
        if any(
            tag(a) in ("nav", "script", "style", "footer") for a in e.iterancestors()
        ):
            continue
        if typ in ("math", "table", "img", "p") and any(
            tag(a) in ("figure", "fig", "disp-formula", "table-wrap", "table")
            for a in e.iterancestors()
        ):
            continue
        text = " ".join("".join(e.itertext()).split())
        blocks.append(
            {
                "type": typ,
                "anchor": e.get("id"),
                "text": text,
                "markup": etree.tostring(e, encoding="unicode", with_tail=False),
            }
        )
    return {"type": "HTML/XML", "blocks": blocks}


def main():
    a = argparse.ArgumentParser(description=__doc__)
    sub = a.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p = sub.add_parser("page")
    p.add_argument("input", type=Path)
    p.add_argument("number", type=int)
    p.add_argument("output", type=Path)
    p.add_argument(
        "--rect", nargs=4, type=float, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM")
    )
    p.add_argument("--scale", type=float, default=2.5)
    args = a.parse_args()
    dest = args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    if args.cmd == "inspect":
        result = (
            inspect_pdf(args.input)
            if args.input.suffix.lower() == ".pdf"
            else inspect_html(args.input)
        )
        data = json.dumps(result, ensure_ascii=False, indent=1).encode("utf8")
    else:
        lib = pdf_module()
        if dest.suffix.lower() != ".png" or not 0 < args.scale <= 6:
            a.error("请使用 PNG 和 0 至 6 范围内的正倍率")
        with lib.open(args.input) as doc:
            if not 1 <= args.number <= len(doc):
                a.error("页码超出源文件")
            pg = doc[args.number - 1]
            rect = lib.Rect(args.rect) if args.rect else pg.rect
            if rect.is_empty or not pg.rect.contains(rect):
                a.error("裁切区域应在原页内")
            data = pg.get_pixmap(
                matrix=lib.Matrix(args.scale, args.scale), clip=rect, alpha=False
            ).tobytes("png")
    with dest.open("xb") as f:
        f.write(data)
    print(dest)


if __name__ == "__main__":
    main()
