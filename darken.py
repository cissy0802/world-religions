#!/usr/bin/env python3
"""睡前读物深色化。

把页面自带的内联配色按 HSL 翻转亮度、保留色相和彩度——琥珀还是琥珀、紫还是紫，
只换明暗，所以每篇文章原来的设计个性不会被抹平成同一套黑。

翻转不保对比度：浅紫底配白字（原本就只有 2.2:1）翻到暗端会变成深紫底配近黑字，
糊成一块。所以翻完还要修对比度，而且要分三种情况——CSS 的级联经常把
「底色」和「字色」拆在两条规则里（`.tradition` 定字色、`.tradition.east` 只覆盖底色），
只看单条规则会漏掉一半。

幂等：转换过的 <style> 顶部有 MARK 标记，重复运行直接跳过，可以放心挂 CI。

用法：
    python3 darken.py                # 仓内所有 *.html
    python3 darken.py a.html b.html  # 指定文件
"""

import colorsys
import glob
import re
import sys

MARK = "/* bigcat-dark v1 */"
MIN_CONTRAST = 4.0

# 本站的底色身份。四个睡前读物仓的原始底色都是近白的米色，几乎不带彩度
# （#f5f1eb 的 chroma 只有 0.039），照原色相推暗会全部收敛成同一种暖黑——
# 四个站长得一模一样。所以「接近中性」的面改用本站色相重新上色；
# 真正有颜色的元素（chroma > NEUTRAL）保持自己的颜色不动。
TINT_HUE = 282          # 度：本仓的身份色相（深紫罗兰）
TINT_CHROMA = 0.10     # 面积大的底色目标彩度
NEUTRAL = 0.09         # 低于这个彩度就算「中性面」，可以重新上色

COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\([^)]*\)")
SHADOW_RE = re.compile(r"\b(box-shadow|text-shadow)\s*:\s*([^;}\"]*)", re.I)
RULE_RE = re.compile(r"([^{}]*)\{([^{}]*)\}")
DECL_RE = re.compile(r"(^|[;{])\s*([-a-zA-Z]+)\s*:\s*([^;}]*)")
VAR_DEF_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]*)")
VAR_USE_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,[^()]*)?\)")


# ---------- 颜色 ----------

def _parse(c):
    """'#f5f1eb' / 'rgba(1,2,3,.5)' -> (r, g, b, alpha_str_or_None)"""
    c = c.strip()
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), None
    try:
        parts = [p.strip() for p in c[c.index("(") + 1: c.rindex(")")].split(",")]
        r, g, b = (int(float(p)) for p in parts[:3])
    except (ValueError, IndexError):
        return None
    return r, g, b, (parts[3] if len(parts) > 3 else None)


def _fmt(r, g, b, alpha=None):
    r, g, b = (max(0, min(255, int(round(v)))) for v in (r, g, b))
    if alpha is None:
        return "#%02x%02x%02x" % (r, g, b)
    return "rgba(%d,%d,%d,%s)" % (r, g, b, alpha)


def _rel_lum(r, g, b, *_):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(c1, c2):
    a, b = _rel_lum(*c1), _rel_lum(*c2)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


BG_PROPS = ("background", "background-color", "background-image")
FG_PROPS = ("color", "fill", "-webkit-text-fill-color")


def flip(c, kind="accent"):
    """把一个颜色推到深色页面该在的位置。色相和彩度不动。

    注意这不是镜像翻转。原设计里本来就深的盒子（psychology 的 `.eng`
    底色 #2a1f2e）如果照着翻，会在深色页面上变成一块刺眼的亮板——
    而"别刺眼"正是睡前读物要的。所以背景只许变暗，本来就浅的字保持浅。
    """
    p = _parse(c)
    if p is None:
        return c
    r, g, b, alpha = p
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    # 用绝对彩度（max-min），不要用 HLS 的 s。近白色如 #fffdf8 只差 7/255，
    # 眼睛看是白的，HLS 却算出 s=1.0——照着它翻转会得到一块发闷的深棕。
    chroma = (max(r, g, b) - min(r, g, b)) / 255.0

    # 1 - l 是朴素翻转，但设计把 bg / 卡片 / 高亮三层都堆在 0.90~1.00 这一小段里，
    # 直接翻转会把它们压成几乎同一个黑。**0.85 把靠近白的那一段重新拉开。
    inv = 0.04 + ((1.0 - l) ** 0.85) * 0.86

    if kind == "bg" and chroma < NEUTRAL:
        # 越暗的面给越少彩度，免得深处发闷发脏
        h = TINT_HUE / 360.0
        chroma = max(chroma, TINT_CHROMA * min(1.0, (min(inv, l, 0.38)) / 0.10))

    if kind == "bg":
        # 封顶 0.38 而不是更高：亮块压暗以后，压在上面的白字对比度自然就够了。
        # 有些底色由 inline style 给、字色由 class 规则给，静态分析配不上对，
        # 修不了的那些就靠这个上限兜住。
        l2 = min(inv, l, 0.38)          # 只许变暗，且封顶，免得留下亮板
    elif kind == "fg":
        l2 = l if l > 0.5 else inv      # 已经是浅色的字不用动
    else:
        l2 = inv                        # 描边、分隔线这类细元素照翻

    # C = (1 - |2L - 1|) * S，反解出在新亮度下保持同样彩度所需的饱和度。
    denom = 1.0 - abs(2.0 * l2 - 1.0)
    s2 = min(1.0, chroma / denom) if denom > 1e-6 else 0.0

    r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s2)
    return _fmt(r2 * 255, g2 * 255, b2 * 255, alpha)


def _shadow(c):
    """阴影一律压成黑色，只留透明度。翻转会把深色阴影变成浅色，
    在深底上就成了一圈发光的边。"""
    p = _parse(c)
    alpha = p[3] if p and p[3] is not None else "0.5"
    return "rgba(0,0,0,%s)" % alpha


def push_apart(fg, bg, target=MIN_CONTRAST, lighten=None):
    """沿亮度方向推开字色，直到对比度够。够不到就返回能推到的最好结果。

    lighten=None 时按底色深浅自动选方向；调用方发现这个方向有别的副作用
    （比如推暗以后文字在深色页面上反而看不见）可以指定另一个方向重试。
    """
    h, l, s = colorsys.rgb_to_hls(fg[0] / 255, fg[1] / 255, fg[2] / 255)
    if lighten is None:
        lighten = _rel_lum(*bg) < 0.18
    step = 0.04 if lighten else -0.04
    best = fg
    for _ in range(25):
        l = min(0.97, max(0.03, l + step))
        cand = tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s)) + (fg[3],)
        best = cand
        if contrast(bg, cand) >= target:
            break
    return _fmt(*best)


# ---------- 规则级修复 ----------

def _decls(text):
    """{'color': ('#fff', span), ...}，只留有颜色值的声明。"""
    out = {}
    for m in DECL_RE.finditer(text):
        prop, val = m.group(2).lower(), m.group(3)
        c = COLOR_RE.search(val)
        if c:
            out[prop] = (c.group(0), (m.start(3) + c.start(), m.start(3) + c.end()))
    return out


def _bg_of(d):
    for p in ("background", "background-color"):
        if p in d:
            return d[p][0]
    return None


def _replace(text, span, new):
    return text[:span[0]] + new + text[span[1]:]


def _sweep(css, page_bg, cases):
    rules = [(m.group(1).strip(), m.group(2), m.span(2)) for m in RULE_RE.finditer(css)]
    colored = {sel: _decls(body).get("color", (None,))[0] for sel, body, _ in rules}
    edits = []

    for sel, body, span in rules:
        d = _decls(body)
        bg, fg = _bg_of(d), d.get("color", (None, None))[0]
        new_body = body

        if 1 in cases and bg and fg:
            pb, pf = _parse(bg), _parse(fg)
            if pb and pf and contrast(pb, pf) < MIN_CONTRAST:
                new_body = _replace(new_body, d["color"][1], push_apart(pf, pb))

        elif 2 in cases and fg and not bg:
            pf, pb = _parse(fg), _parse(page_bg)
            if pf and pb and contrast(pb, pf) < MIN_CONTRAST:
                new_body = _replace(new_body, d["color"][1], push_apart(pf, pb))

        elif 3 in cases and bg and not fg:
            base = next((c for s, c in colored.items()
                         if c and s != sel and sel.startswith(s)), None)
            if base:
                pb, pf = _parse(bg), _parse(base)
                if pb and pf and contrast(pb, pf) < MIN_CONTRAST:
                    new_body = new_body.rstrip().rstrip(";") + \
                        ";color:%s" % push_apart(pf, pb)

        if new_body != body:
            edits.append((span, new_body))

    for (a, b), new in reversed(edits):
        css = css[:a] + new + css[b:]
    return css


def repair(css, page_bg):
    """三种情况分开修：

    1. 同一条规则既有底色又有字色 —— 直接按这对算。
    2. 只有字色 —— 它落在页面底色上（翻转后全是深色），按页面底色算。
    3. 只覆盖了底色（变体规则，如 `.tradition.east`）—— 字色来自前缀选择器那条规则，
       算不过就在这条规则里补一句显式的 color。

    情况 3 必须等 1、2 修完再跑：变体规则要拿的是**最终**生效的字色，
    照着修复前的原色算会得出「对比度够」的假结论。
    """
    css = _sweep(css, page_bg, {1, 2})
    return _sweep(css, page_bg, {3})


# ---------- 内联 SVG ----------
# 图表里的颜色写在 fill= / stroke= 这种 presentation attribute 上，不走 CSS，
# 光扫 <style> 和 style="" 会整块漏掉——leadership 有 114 篇带图表。

SVG_TAG_RE = re.compile(r'<([a-zA-Z][\w:-]*)((?:[^<>"]|"[^"]*")*?)(/?)>')
SVG_ATTR_RE = re.compile(r'\b(fill|stroke|stop-color)="([^"]*)"')


def _svg_kind(tag, attr, attrs):
    if attr != "fill":
        return "accent" if attr == "stroke" else "bg"
    if tag in ("text", "tspan"):
        return "fg"
    if tag in ("rect", "g", "svg", "foreignObject"):
        return "bg"
    if tag in ("circle", "ellipse"):
        # 半径小的是数据点、节点标记，不是面；当作描边一类处理才不会变得看不见
        m = re.search(r'\b(?:r|rx)="([\d.]+)"', attrs)
        return "bg" if m and float(m.group(1)) >= 20 else "accent"
    return "accent"          # path / polygon / polyline 基本都是箭头和连接线


def transform_svg(src):
    def tag(m):
        name, attrs, close = m.group(1).lower(), m.group(2), m.group(3)
        if not SVG_ATTR_RE.search(attrs):
            return m.group(0)
        new = SVG_ATTR_RE.sub(
            lambda a: '%s="%s"' % (a.group(1), COLOR_RE.sub(
                lambda c: flip(c.group(0), _svg_kind(name, a.group(1), attrs)),
                a.group(2))),
            attrs)
        return "<%s%s%s>" % (m.group(1), new, close)
    return SVG_TAG_RE.sub(tag, src)



def _num(attrs, key):
    m = re.search(r'\b%s="([\d.]+)"' % key, attrs)
    return float(m.group(1)) if m else 0.0


def repair_svg(src, page_bg):
    """修 SVG 里「文字压在色块上」的对比度。

    CSS 那套修复够不着这里：图表的底色和字色是 <rect fill> / <text fill>，
    没有规则可查，只能按文档顺序把文字归给它前面最近的那个大 rect。

    这一步**只会提高对比度**，所以幂等、可以单独对已经转过的页面再跑一遍。
    归属判断是启发式的，万一某段文字其实压在页面底色上，把它推向 rect 反而
    会推没——所以推完还要对页面底色复核一次，过不了就不动。
    """
    pbg = _parse(page_bg)

    def one(m):
        svg, edits, surface = m.group(0), [], None
        for t in re.finditer(r'<(rect|text|tspan)\b([^>]*)>', svg):
            tag, attrs = t.group(1), t.group(2)
            f = re.search(r'\bfill="(#[0-9a-fA-F]{3,6})"', attrs)
            if not f:
                continue
            if tag == "rect":
                if _num(attrs, "width") >= 40 and _num(attrs, "height") >= 20:
                    surface = f.group(1)
                continue
            if not surface:
                continue
            fg, bg = _parse(f.group(1)), _parse(surface)
            if not fg or not bg or contrast(bg, fg) >= MIN_CONTRAST:
                continue
            cand = push_apart(fg, bg)
            if pbg and contrast(pbg, _parse(cand)) < 3.0:
                # 这个方向把文字推进了页面底色里，换个方向再试
                cand = push_apart(fg, bg, lighten=_rel_lum(*bg) >= 0.18)
                if (contrast(bg, _parse(cand)) < MIN_CONTRAST
                        or contrast(pbg, _parse(cand)) < 3.0):
                    continue
            a = t.start(2) + f.start(1)
            edits.append((a, a + len(f.group(1)), cand))
        for a, b, new in reversed(edits):
            svg = svg[:a] + new + svg[b:]
        return svg

    return re.sub(r'<svg\b.*?</svg>', one, src, flags=re.S)


# ---------- 页面 ----------

def collect_vars(css):
    """:root 里那些存了颜色的自定义属性。"""
    return {m.group(1): m.group(2).strip()
            for m in VAR_DEF_RE.finditer(css) if COLOR_RE.search(m.group(2))}


def transform_decl(prop, val, cssvars=None):
    prop = prop.lower()
    if prop in ("box-shadow", "text-shadow"):
        # 阴影一律压成黑色。翻转会把深色阴影变成浅色，在深底上就成了一圈发光的边。
        return COLOR_RE.sub(lambda c: _shadow(c.group(0)), val)
    if prop.startswith("--"):
        kind = "accent"          # 定义处不知道会拿去当什么用
    else:
        kind = "bg" if prop in BG_PROPS else "fg" if prop in FG_PROPS else "accent"
        if cssvars and kind in ("bg", "fg"):
            # 一个变量常常既当底色又当字色（world-religions 的 --slate 就是），
            # 在定义处只能二选一、必然坑一边。所以在**用到它的地方**先把值代入，
            # 让这里的属性来决定往哪边推。
            val = VAR_USE_RE.sub(
                lambda m: cssvars.get(m.group(1), m.group(0)), val)
    return COLOR_RE.sub(lambda c: flip(c.group(0), kind), val)


def transform_block(body, cssvars=None):
    out, last = [], 0
    for m in re.finditer(r"([-a-zA-Z-]+)\s*:\s*([^;}]*)", body):
        out.append(body[last:m.start(2)])
        out.append(transform_decl(m.group(1), m.group(2), cssvars))
        last = m.end(2)
    out.append(body[last:])
    return "".join(out)


def transform_css(css, cssvars=None):
    # RULE_RE 只吃得下最内层的 {}，@media 外壳会被自动跳过。
    return RULE_RE.sub(
        lambda m: m.group(1) + "{" + transform_block(m.group(2), cssvars) + "}", css)


def body_bg(css):
    m = re.search(r"(^|[},])\s*body\s*\{([^}]*)\}", css)
    if m:
        c = _decls(m.group(2))
        bg = _bg_of(c)
        if bg:
            return bg
    return "#111111"


def darken(path):
    src = open(path, encoding="utf-8").read()
    original = src

    if MARK not in src:
        styles = list(re.finditer(r"(<style[^>]*>)(.*?)(</style>)", src, re.S | re.I))
        if not styles:
            return False
        cssvars = collect_vars("".join(m.group(2) for m in styles))
        flipped = [transform_css(m.group(2), cssvars) for m in styles]
        bg = body_bg("".join(flipped))
        flipped = [repair(c, bg) for c in flipped]

        out, last = [], 0
        for i, m in enumerate(styles):
            head = "\n%s\n:root{color-scheme:dark}\n" % MARK if i == 0 else ""
            out.append(src[last:m.start()] + m.group(1) + head + flipped[i] + m.group(3))
            last = m.end()
        out.append(src[last:])
        src = "".join(out)

        src = transform_svg(src)

        # style="..." 是裸声明列表，没有 {}，走 transform_block 而不是 transform_css
        src = re.sub(r'style="([^"]*)"',
                     lambda m: 'style="%s"' % repair("{%s}" % transform_block(m.group(1), cssvars), bg)[1:-1],
                     src)

        # 手机状态栏跟着页面走，否则顶部会留一条白边
        tag = '<meta content="%s" name="theme-color"/>' % bg
        if re.search(r'<meta[^>]*name="theme-color"', src, re.I):
            src = re.sub(r'<meta[^>]*name="theme-color"[^>]*/?>', tag, src, flags=re.I)
        else:
            src = re.sub(r"(</title>)", r"\1\n" + tag, src, count=1, flags=re.I)
    else:
        bg = body_bg("".join(re.findall(r"<style[^>]*>(.*?)</style>", src, re.S | re.I)))

    # 只提高对比度，幂等——已经转过的页面也可以单独再跑这一步
    src = repair_svg(src, bg)

    if src == original:
        return False
    open(path, "w", encoding="utf-8").write(src)
    return True


def main(argv):
    files = argv or sorted(glob.glob("*.html"))
    print("darkened %d / %d" % (sum(1 for f in files if darken(f)), len(files)))


if __name__ == "__main__":
    main(sys.argv[1:])
