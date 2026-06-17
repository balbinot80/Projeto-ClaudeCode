import streamlit as st

_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Jost:wght@300;400;600&display=swap" rel="stylesheet">
<style>
:root {
  --au-rosa: #AB6774;
  --au-rosa-light: #C89199;
  --au-rosa-pale: #F5EBEC;
  --au-white: #FFFFFF;
  --au-cream: #FAF7F4;
  --au-gold: #C4985A;
  --au-gold-light: #E8D5A3;
  --au-ink: #2A1A1F;
  --au-ink-muted: #7A6068;
  --au-border: rgba(171,103,116,.15);
  --au-perola: #EDE8E3; --au-perola-t: #6b5d4f;
  --au-ouro: #C4985A;  --au-ouro-t: #fff;
  --au-diamante: #AB6774; --au-diamante-t: #fff;
}

/* ── Brand header ─────────────────────────────────────────────── */
.au-header {
  background: linear-gradient(135deg, var(--au-rosa) 0%, #8E4F5C 100%);
  border-radius: 16px; padding: 22px 28px; color: #fff; margin-bottom: 22px;
}
.au-header-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 26px; font-weight: 400; letter-spacing: .04em; margin: 0 0 3px;
}
.au-header-sub {
  font-family: 'Jost', sans-serif; font-weight: 300; font-size: 11px;
  letter-spacing: .1em; text-transform: uppercase; opacity: .75; margin: 0;
}

/* ── KPI card ──────────────────────────────────────────────────── */
.au-kpi {
  background: var(--au-white); border-radius: 14px; padding: 16px 20px;
  border-left: 4px solid var(--au-rosa);
  box-shadow: 0 2px 8px rgba(171,103,116,.08); height: 100%;
}
.au-kpi-label {
  font-family: 'Jost', sans-serif; font-weight: 300; font-size: 10px;
  letter-spacing: .09em; text-transform: uppercase; color: var(--au-ink-muted); margin: 0 0 5px;
}
.au-kpi-value {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 26px; font-weight: 600; color: var(--au-ink); margin: 0; line-height: 1.1;
}
.au-kpi-delta {
  font-family: 'Jost', sans-serif; font-size: 10px; color: var(--au-ink-muted); margin-top: 4px;
}
.au-kpi-alert { border-left-color: #D1473A; }

/* ── Section title ─────────────────────────────────────────────── */
.au-section-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 20px; font-weight: 400; letter-spacing: .03em; color: var(--au-ink); margin: 0 0 2px;
}
.au-section-sub {
  font-family: 'Jost', sans-serif; font-weight: 300; font-size: 10px;
  letter-spacing: .09em; text-transform: uppercase; color: var(--au-ink-muted); margin: 0 0 14px;
}

/* ── Revendedora card ──────────────────────────────────────────── */
.au-rev-card {
  background: var(--au-white); border-radius: 12px; padding: 12px 16px;
  border: 1px solid var(--au-border); box-shadow: 0 1px 4px rgba(171,103,116,.06);
  display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.au-rev-card:hover {
  transform: translateX(3px); box-shadow: 0 4px 12px rgba(171,103,116,.12);
  border-color: var(--au-rosa-light);
}
.au-avatar {
  width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, var(--au-rosa-pale), var(--au-rosa-light));
  display: flex; align-items: center; justify-content: center;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 14px; font-weight: 600; color: var(--au-rosa);
}
.au-rev-nome {
  font-family: 'Jost', sans-serif; font-weight: 600; font-size: 13px; color: var(--au-ink);
}
.au-rev-meta {
  font-family: 'Jost', sans-serif; font-size: 11px; color: var(--au-ink-muted); margin-top: 2px;
}
.au-rev-valor {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 16px; font-weight: 600; color: var(--au-rosa); margin-left: auto; text-align: right; white-space: nowrap;
}

/* ── Tier badges ───────────────────────────────────────────────── */
.au-badge {
  display: inline-block; font-family: 'Jost', sans-serif;
  font-size: 9px; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
  padding: 2px 8px; border-radius: 999px;
}
.au-badge-perola   { background: var(--au-perola);   color: var(--au-perola-t); }
.au-badge-ouro     { background: var(--au-ouro);     color: var(--au-ouro-t); }
.au-badge-diamante { background: var(--au-diamante); color: var(--au-diamante-t); }
.au-badge-sem      { background: #EEE; color: #999; }

/* ── Pódio ─────────────────────────────────────────────────────── */
.au-podio {
  display: flex; align-items: flex-end; justify-content: center; gap: 10px; padding: 16px 0 0;
}
.au-podio-lugar {
  display: flex; flex-direction: column; align-items: center;
  background: var(--au-white); border-radius: 14px 14px 0 0; padding: 16px 14px 10px;
  box-shadow: 0 4px 14px rgba(171,103,116,.1); min-width: 105px;
}
.au-podio-1 { padding-top: 26px; transform: translateY(-10px); order: 2; }
.au-podio-2 { order: 1; }
.au-podio-3 { order: 3; }
.au-podio-avatar {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, var(--au-rosa-pale), var(--au-rosa-light));
  display: flex; align-items: center; justify-content: center;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 15px; font-weight: 600; color: var(--au-rosa);
}
.au-podio-1 .au-podio-avatar { width: 54px; height: 54px; font-size: 18px; border: 2px solid var(--au-gold); }
.au-podio-nome {
  font-family: 'Jost', sans-serif; font-size: 11px; font-weight: 600;
  color: var(--au-ink); margin-top: 7px; text-align: center;
}
.au-podio-valor {
  font-family: 'Cormorant Garamond', Georgia, serif; font-size: 13px; font-weight: 600; color: var(--au-rosa);
}
.au-podio-pos {
  font-family: 'Jost', sans-serif; font-size: 9px; font-weight: 600;
  letter-spacing: .06em; color: var(--au-ink-muted); margin-top: 3px;
}
.au-podio-1 .au-podio-pos { color: var(--au-gold); }
.au-coroa { font-size: 14px; color: var(--au-gold); }

/* ── Rank item com barra ───────────────────────────────────────── */
.au-rank-item {
  display: flex; align-items: center; gap: 10px;
  background: var(--au-white); border-radius: 10px; padding: 9px 14px;
  border: 1px solid var(--au-border); margin-bottom: 6px;
  transition: transform .15s ease;
}
.au-rank-item:hover { transform: translateX(3px); }
.au-barra-wrap {
  background: rgba(171,103,116,.1); border-radius: 999px; height: 4px; overflow: hidden; flex: 1;
}
.au-barra-fill {
  height: 100%; background: linear-gradient(90deg, var(--au-gold-light), var(--au-gold));
  border-radius: 999px; transition: width .8s cubic-bezier(.22,1,.36,1);
}

/* ── Divider ───────────────────────────────────────────────────── */
.au-divider { border: none; border-top: 1px solid var(--au-border); margin: 18px 0; }

/* ── Skeleton ──────────────────────────────────────────────────── */
.au-skeleton {
  background: linear-gradient(90deg, #ECE7DD 25%, #F5F0E8 50%, #ECE7DD 75%);
  background-size: 200% 100%; animation: au-shimmer 1.4s ease-in-out infinite; border-radius: 8px;
}
@keyframes au-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* ── Tag de preview ────────────────────────────────────────────── */
.au-preview-tag {
  display: inline-block; background: rgba(171,103,116,.12); color: var(--au-rosa);
  font-family: 'Jost', sans-serif; font-size: 10px; font-weight: 600;
  letter-spacing: .08em; text-transform: uppercase; padding: 3px 10px;
  border-radius: 999px; margin-bottom: 12px;
}
</style>
"""


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


def kpi_html(label: str, valor: str, delta: str = "", alerta: bool = False) -> str:
    cls = "au-kpi au-kpi-alert" if alerta else "au-kpi"
    delta_html = f'<p class="au-kpi-delta">{delta}</p>' if delta else ""
    return f"""
    <div class="{cls}">
      <p class="au-kpi-label">{label}</p>
      <p class="au-kpi-value">{valor}</p>
      {delta_html}
    </div>
    """


def rev_card_html(nome: str, meta: str, valor: str, tier: str = "") -> str:
    iniciais = "".join(w[0].upper() for w in nome.split()[:2]) if nome else "—"
    badge = f'<span class="au-badge au-badge-{tier.lower()}">{tier}</span>' if tier else ""
    return f"""
    <div class="au-rev-card">
      <div class="au-avatar">{iniciais}</div>
      <div style="flex:1;min-width:0">
        <div class="au-rev-nome">{nome}</div>
        <div class="au-rev-meta">{meta} {badge}</div>
      </div>
      <div class="au-rev-valor">{valor}</div>
    </div>
    """


def empty_state(titulo: str, texto: str, icone: str = "✦") -> str:
    return f"""
    <div style="text-align:center;padding:36px 20px;color:var(--au-rosa)">
      <div style="font-size:26px;margin-bottom:10px;opacity:.5">{icone}</div>
      <p style="font-family:'Cormorant Garamond',Georgia,serif;font-size:18px;
               font-weight:600;color:#2A1A1F;margin:0 0 6px">{titulo}</p>
      <p style="font-family:'Jost',sans-serif;font-size:12px;font-weight:300;
               color:#7A6068;margin:0">{texto}</p>
    </div>
    """
