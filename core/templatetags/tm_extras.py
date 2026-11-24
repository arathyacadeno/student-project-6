import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def md(text):
    """Tiny, safe Markdown -> HTML (headings, bold, bullet lists)."""
    out, in_list = [], False
    for raw in escape(text or "").splitlines():
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", raw.strip())
        line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", line)
        bullet = re.match(r"^[-*•]\s+(.*)", line)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{bullet.group(1)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        h = re.match(r"^(#{1,4})\s+(.*)", line)
        if h:
            lvl = min(len(h.group(1)) + 1, 5)
            out.append(f"<h{lvl}>{h.group(2)}</h{lvl}>")
        elif line:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return mark_safe("\n".join(out))


@register.filter
def inr(value):
    try:
        return "₹{:,}".format(int(value))
    except (TypeError, ValueError):
        return value


@register.filter
def stars(value):
    n = round(float(value or 0))
    return "★" * n + "☆" * (5 - n)


@register.filter
def get_item(d, key):
    return d.get(key, "")
