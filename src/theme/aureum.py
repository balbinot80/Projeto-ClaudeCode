import streamlit as st

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond'
    ':ital,wght@0,400;0,600;1,400&family=Jost:wght@300;400;600&display=swap" rel="stylesheet">'
)

# CSS apenas para elementos que não podem usar inline styles: hover, animações, pseudo-seletores
_CSS_EXTRA = """
<style>
:root {
  --au-rosa:#AB6774; --au-rosa-light:#C89199; --au-rosa-pale:#F5EBEC;
  --au-gold:#C4985A; --au-gold-light:#E8D5A3;
  --au-ink:#2A1A1F; --au-ink-muted:#7A6068;
  --au-border:rgba(171,103,116,.15);
  --au-font-display:'Cormorant Garamond',Georgia,serif;
  --au-font-body:'Jost',sans-serif;
}
.au-hover:hover { transform:translateX(3px); box-shadow:0 4px 12px rgba(171,103,116,.12) !important; }
.au-shimmer {
  background:linear-gradient(90deg,#ECE7DD 25%,#F5F0E8 50%,#ECE7DD 75%);
  background-size:200% 100%; animation:_shimmer 1.4s ease-in-out infinite; border-radius:8px;
}
@keyframes _shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
</style>
"""


def inject():
    st.html(_FONTS + _CSS_EXTRA)


# ── Componentes totalmente inline (não dependem de CSS externo) ───────────────

def kpi_html(label: str, valor: str, delta: str = "", alerta: bool = False) -> str:
    cor = "#D1473A" if alerta else "#AB6774"
    d = (
        '<p style="font-family:Jost,sans-serif;font-size:10px;color:#7A6068;margin:4px 0 0">'
        + delta + "</p>"
    ) if delta else ""
    return (
        '<div style="background:#fff;border-radius:14px;padding:16px 20px;'
        "border-left:4px solid " + cor + ";"
        'box-shadow:0 2px 8px rgba(171,103,116,.08)">'
        '<p style="font-family:Jost,sans-serif;font-weight:300;font-size:10px;'
        'letter-spacing:.09em;text-transform:uppercase;color:#7A6068;margin:0 0 5px">'
        + label + "</p>"
        '<p style="font-family:Georgia,serif;font-size:26px;font-weight:600;'
        'color:#2A1A1F;margin:0;line-height:1.1">'
        + valor + "</p>"
        + d +
        "</div>"
    )


def rev_card_html(nome: str, meta: str, valor: str, tier: str = "") -> str:
    iniciais = "".join(w[0].upper() for w in nome.split()[:2]) if nome else "—"
    if tier:
        cor_badge = {"Ouro": "#C4985A", "Diamante": "#AB6774"}.get(tier, "#EDE8E3")
        cor_text  = "#fff" if tier in ("Ouro", "Diamante") else "#6b5d4f"
        badge = (
            '<span style="background:' + cor_badge + ';color:' + cor_text + ';'
            'font-family:Jost,sans-serif;font-size:9px;font-weight:600;'
            'letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border-radius:999px">'
            + tier + "</span>"
        )
    else:
        badge = ""
    return (
        '<div class="au-hover" style="display:flex;align-items:center;gap:12px;'
        'background:#fff;border-radius:12px;padding:12px 16px;'
        'border:1px solid rgba(171,103,116,.15);'
        'box-shadow:0 1px 4px rgba(171,103,116,.06);margin-bottom:8px;'
        'transition:transform .15s ease,box-shadow .15s ease">'
        '<div style="width:40px;height:40px;border-radius:50%;flex-shrink:0;'
        'background:linear-gradient(135deg,#F5EBEC,#C89199);'
        'display:flex;align-items:center;justify-content:center;'
        'font-family:Georgia,serif;font-size:14px;font-weight:600;color:#AB6774">'
        + iniciais + "</div>"
        '<div style="flex:1;min-width:0">'
        '<div style="font-family:Jost,sans-serif;font-weight:600;font-size:13px;color:#2A1A1F">'
        + nome + "</div>"
        '<div style="font-family:Jost,sans-serif;font-size:11px;color:#7A6068;margin-top:2px">'
        + meta + (" " + badge if badge else "") + "</div>"
        "</div>"
        '<div style="font-family:Georgia,serif;font-size:16px;font-weight:600;'
        'color:#AB6774;margin-left:auto;text-align:right;white-space:nowrap">'
        + valor + "</div>"
        "</div>"
    )


def section_header(titulo: str, subtitulo: str = "") -> str:
    sub = (
        '<p style="font-family:Jost,sans-serif;font-weight:300;font-size:10px;'
        'letter-spacing:.09em;text-transform:uppercase;color:#7A6068;margin:0 0 14px">'
        + subtitulo + "</p>"
    ) if subtitulo else ""
    return (
        '<p style="font-family:Georgia,serif;font-size:20px;font-weight:400;'
        'letter-spacing:.03em;color:#2A1A1F;margin:0 0 2px">'
        + titulo + "</p>"
        + sub
    )


def empty_state(titulo: str, texto: str, icone: str = "✦") -> str:
    return (
        '<div style="text-align:center;padding:36px 20px">'
        '<div style="font-size:26px;margin-bottom:10px;opacity:.4;color:#AB6774">'
        + icone + "</div>"
        '<p style="font-family:Georgia,serif;font-size:18px;font-weight:600;'
        'color:#2A1A1F;margin:0 0 6px">'
        + titulo + "</p>"
        '<p style="font-family:Jost,sans-serif;font-size:12px;font-weight:300;'
        'color:#7A6068;margin:0">'
        + texto + "</p>"
        "</div>"
    )
