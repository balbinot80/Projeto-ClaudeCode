"""
Acompanhamento Semanal — D+3, D+7, D+20
Tela admin para controle do nível de atendimento das supervisoras.
"""
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from src.api.jueri_client import _get_lista_pedidos, get_pedidos_abertos
from src.logic.niveis import _qtd_original, nivel_por_pecas

# ── Constantes visuais ────────────────────────────────────────────────────────

ROSA  = "#AB6774"
GOLD  = "#C4985A"

TIPO_LABEL = {"D3": "D+3", "D7": "D+7", "D20": "D+20"}
TIPO_COR   = {"D3": "#3B82F6", "D7": "#8B5CF6", "D20": "#F59E0B"}

BADGE_NIVEL = {
    "Diamante":  ("💎", "#AB6774", "white"),
    "Ouro":      ("🥇", "#C4985A", "white"),
    "Pérola":    ("🔮", "#EDE8E3", "#2A1A1F"),
    "Sem nível": ("—",  "#E5E7EB", "#6B7280"),
}

TIPOS_DIAS = [("D3", 3), ("D7", 7), ("D20", 20)]


# ── Supabase ──────────────────────────────────────────────────────────────────

def _get_client():
    try:
        from supabase import create_client
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except (KeyError, FileNotFoundError):
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


@st.cache_data(ttl=30, show_spinner=False)
def _carregar_feitos_db() -> dict:
    """
    Retorna {(pedido_id, tipo): feito_em_iso_str} para todos os registros feito=True.
    """
    client = _get_client()
    if not client:
        return {}
    try:
        res = client.table("follow_ups_semana").select(
            "pedido_id,tipo,feito_em"
        ).eq("feito", True).execute()
        return {
            (r["pedido_id"], r["tipo"]): (r.get("feito_em") or "")
            for r in (res.data or [])
        }
    except Exception:
        return {}


def _get_feitos() -> dict:
    """
    Merge Supabase + overrides de session_state.
    Retorna {(pedido_id, tipo): feito_em_str}.
    """
    db = _carregar_feitos_db()
    local: dict = st.session_state.get("_fu_overrides", {})
    merged = dict(db)
    for key, val in local.items():
        if val is None:
            merged.pop(key, None)   # desfeito localmente
        else:
            merged[key] = val       # marcado localmente
    return merged


def _marcar_feito(pedido_id: int, tipo: str, feito: bool):
    """Grava no Supabase e atualiza session_state imediatamente."""
    agora = datetime.now(timezone.utc).isoformat() if feito else None

    # 1. Atualização local imediata (para o UI não travar)
    if "_fu_overrides" not in st.session_state:
        st.session_state["_fu_overrides"] = {}
    key = (pedido_id, tipo)
    st.session_state["_fu_overrides"][key] = agora if feito else None

    # 2. Persistência no Supabase
    client = _get_client()
    if not client:
        st.toast("⚠️ Salvo apenas localmente — Supabase não configurado.", icon="⚠️")
        return

    try:
        # Delete + insert é mais confiável que upsert com on_conflict
        client.table("follow_ups_semana").delete().eq(
            "pedido_id", pedido_id
        ).eq("tipo", tipo).execute()

        if feito:
            client.table("follow_ups_semana").insert({
                "pedido_id": pedido_id,
                "tipo":      tipo,
                "feito":     True,
                "feito_em":  agora,
            }).execute()

        _carregar_feitos_db.clear()
    except Exception as e:
        st.toast(f"⚠️ Erro ao salvar no Supabase: {e}", icon="⚠️")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _semana_str(inicio: date, fim: date) -> str:
    if inicio.month == fim.month:
        return f"{inicio.strftime('%d')} a {fim.strftime('%d/%m/%Y')}"
    return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m/%Y')}"


def _meses_na_equipe(primeira: date, hoje: date) -> int:
    return (hoje.year - primeira.year) * 12 + (hoje.month - primeira.month)


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_feito_em(iso: str) -> str:
    """Formata timestamp ISO para 'DD/MM às HH:MM'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        brt = dt.astimezone(timezone(timedelta(hours=-3)))
        return brt.strftime("%d/%m às %H:%M")
    except Exception:
        return ""


def _urgencia_txt(data_fu: date, hoje: date) -> str:
    delta = (data_fu - hoje).days
    if delta == 0:
        return "📌 Hoje"
    if delta < 0:
        return f"⚠️ {abs(delta)}d atraso"
    if delta == 1:
        return "⏰ Amanhã"
    return f"em {delta}d ({data_fu.strftime('%d/%m')})"


# ── Card individual ───────────────────────────────────────────────────────────

def _render_card(f: dict, feitos: dict, hoje: date):
    pid      = f["pedido_id"]
    tipo     = f["tipo"]
    feito_em = feitos.get((pid, tipo))
    feito    = feito_em is not None
    atras    = f["atrasado"] and not feito

    cls       = "feito" if feito else ("atrasado" if atras else "")
    emoji_n, bg_n, fg_n = BADGE_NIVEL.get(f["nivel"], ("—", "#E5E7EB", "#6B7280"))
    tipo_cor   = TIPO_COR[tipo]
    meses_txt  = f"{f['meses']} meses na equipe" if f["meses"] is not None else "—"
    preval_txt = _fmt_brl(f["preval"]) if f["preval"] > 0 else "—"
    data_ped_s = f["data_ped"].strftime("%d/%m")
    data_fu_s  = f["data_fu"].strftime("%d/%m")

    if feito:
        urgencia_html = (
            f"<span class='tag-status tag-feito'>✅ Feito"
            + (f" · {_fmt_feito_em(feito_em)}" if feito_em else "")
            + "</span>"
        )
    else:
        delta = (f["data_fu"] - hoje).days
        if delta < 0:
            cls_urg = "tag-atrasado"
            txt_urg = f"⚠️ {abs(delta)}d atraso"
        elif delta == 0:
            cls_urg = "tag-hoje"
            txt_urg = "📌 Hoje"
        elif delta == 1:
            cls_urg = "tag-futuro"
            txt_urg = "⏰ Amanhã"
        else:
            cls_urg = "tag-futuro"
            txt_urg = f"em {delta}d ({f['data_fu'].strftime('%d/%m')})"
        urgencia_html = f"<span class='tag-status {cls_urg}'>{txt_urg}</span>"

    col_card, col_btn = st.columns([6, 1])
    with col_card:
        st.markdown(
            f"<div class='fu-card {cls}'>"
            f"<div class='top-row'>"
            f"<span class='tag-tipo' style='background:{tipo_cor}'>{TIPO_LABEL[tipo]}</span>"
            f"<span class='nome-rev'>{f['nome']}</span>"
            f"<span class='badge-n' style='background:{bg_n};color:{fg_n}'>"
            f"{emoji_n} {f['nivel']}</span>"
            f"{urgencia_html}"
            f"</div>"
            f"<div class='meta-row'>"
            f"<span>📦 Pedido: {data_ped_s}</span>"
            f"<span>📅 Acomp.: {data_fu_s}</span>"
            f"<span>💰 Pré-baixa: {preval_txt}</span>"
            f"<span>🧩 {f['qtd']} peças</span>"
            f"<span>⏳ {meses_txt}</span>"
            + (f"<span class='tag-premiacao'>🏆 Premiação</span>" if tipo == "D3" else "")
            + (f"<span class='tag-vendas'>💬 Falar sobre vendas</span>" if tipo == "D7" else "")
            + (f"<span class='tag-acerto'>📅 Agendar acerto</span>" if tipo == "D20" else "")
            + f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        if feito:
            if st.button("↩ Desfazer", key=f"fu_{pid}_{tipo}",
                         use_container_width=True, type="secondary"):
                _marcar_feito(pid, tipo, False)
                st.rerun()
        else:
            if st.button("✅ Feito", key=f"fu_{pid}_{tipo}",
                         use_container_width=True, type="primary"):
                _marcar_feito(pid, tipo, True)
                st.rerun()


# ── Render principal ──────────────────────────────────────────────────────────

def render():
    st.markdown(
        """
        <style>
        .acomp-hero {
            background: linear-gradient(135deg, #AB6774 0%, #C4985A 100%);
            padding: 22px 28px; border-radius: 14px; margin-bottom: 18px; color: white;
        }
        .acomp-hero h1 { color: white; margin: 0; font-size: 1.6em; }
        .acomp-hero p  { color: rgba(255,255,255,.85); margin: 5px 0 0; font-size: .92em; }
        .sup-header {
            background: #F5EBEC; border-radius: 10px; padding: 10px 16px;
            margin: 24px 0 10px; font-weight: 700; color: #AB6774; font-size: 1.04em;
            display: flex; align-items: center; gap: 10px;
        }
        .fu-card {
            background: white; border-radius: 12px; padding: 13px 16px;
            border-left: 4px solid #AB6774; margin-bottom: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,.06);
        }
        .fu-card.feito    { border-left-color: #22c55e; background: #f0fdf4; }
        .fu-card.atrasado { border-left-color: #ef4444; }
        .top-row  { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; flex-wrap: wrap; }
        .meta-row { display: flex; gap: 18px; font-size: .84em; color: #7A6068; flex-wrap: wrap; }
        .tag-tipo { color: white; border-radius: 6px; padding: 2px 10px;
                    font-weight: 700; font-size: .88em; white-space: nowrap; }
        .badge-n  { border-radius: 20px; padding: 1px 9px;
                    font-size: .77em; font-weight: 700; white-space: nowrap; }
        .urgencia { margin-left: auto; font-size: .87em; color: #7A6068; white-space: nowrap; }
        .tag-status { border-radius: 20px; padding: 3px 12px;
                      font-size: .82em; font-weight: 600; white-space: nowrap; }
        .tag-feito    { background: #dcfce7; color: #166534; }
        .tag-atrasado { background: #fee2e2; color: #991b1b; }
        .tag-hoje     { background: #fef9c3; color: #854d0e; }
        .tag-futuro   { background: #dbeafe; color: #1e40af; }
        .feito-tag { background: #dcfce7; color: #166534; border-radius: 20px;
                     padding: 1px 10px; font-size: .82em; font-weight: 600; white-space: nowrap; }
        .tag-acerto   { background: #fef9c3; color: #854d0e; border-radius: 6px;
                        padding: 2px 10px; font-size: .82em; font-weight: 700; white-space: nowrap;
                        border: 1px solid #fde047; }
        .tag-premiacao { background: #f3e8ff; color: #6b21a8; border-radius: 6px;
                         padding: 2px 10px; font-size: .82em; font-weight: 700; white-space: nowrap;
                         border: 1px solid #d8b4fe; }
        .tag-vendas   { background: #dcfce7; color: #166534; border-radius: 6px;
                        padding: 2px 10px; font-size: .82em; font-weight: 700; white-space: nowrap;
                        border: 1px solid #86efac; }
        .nome-rev { font-weight: 700; font-size: 1.01em; color: #2A1A1F; }
        </style>
        <div class="acomp-hero">
            <h1>📋 Acompanhamento Semanal</h1>
            <p>Controle de atendimento D+3 · D+7 · D+20 por supervisora</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hoje = date.today()

    # ── Seletor de semana ─────────────────────────────────────────────────────
    if "acomp_offset" not in st.session_state:
        st.session_state.acomp_offset = 0

    offset   = st.session_state.acomp_offset
    seg_base = hoje - timedelta(days=hoje.weekday())
    inicio   = seg_base + timedelta(weeks=offset)
    fim      = inicio + timedelta(days=6)
    num_sem  = inicio.isocalendar()[1]

    c_prev, c_label, c_next = st.columns([1, 6, 1])
    with c_prev:
        if st.button("◀", use_container_width=True, key="acomp_prev"):
            st.session_state.acomp_offset -= 1
            st.rerun()
    with c_label:
        st.markdown(
            f"<div style='text-align:center;padding:8px 0;font-weight:700;"
            f"font-size:1.1em;color:{ROSA}'>"
            f"📅 Semana {num_sem} — {_semana_str(inicio, fim)}</div>",
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("▶", use_container_width=True, key="acomp_next"):
            st.session_state.acomp_offset += 1
            st.rerun()

    if offset != 0:
        if st.button("↩ Semana atual", key="acomp_hoje_btn"):
            st.session_state.acomp_offset = 0
            st.rerun()

    st.divider()

    # ── Carregar dados ────────────────────────────────────────────────────────
    with st.spinner("Carregando pedidos..."):
        try:
            abertos = get_pedidos_abertos()
            todos   = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    # Mapa rid → primeiro pedido (proxy de tempo na equipe)
    primeiro_pedido: dict = {}
    for p in todos:
        rid = p.get("fk_revendedor_id")
        dc  = (p.get("data_criacao") or "")[:10]
        try:
            d = date.fromisoformat(dc)
            if rid not in primeiro_pedido or d < primeiro_pedido[rid]:
                primeiro_pedido[rid] = d
        except (ValueError, TypeError):
            pass

    # ── Calcular follow-ups da semana ─────────────────────────────────────────
    follow_ups = []
    for p in abertos:
        dc_str = (p.get("data_criacao") or "")[:10]
        try:
            data_ped = date.fromisoformat(dc_str)
        except (ValueError, TypeError):
            continue

        for tipo, dias in TIPOS_DIAS:
            data_fu = data_ped + timedelta(days=dias)
            if not (inicio <= data_fu <= fim):
                continue

            rid       = p.get("fk_revendedor_id")
            comprador = p.get("comprador") or {}
            nome      = comprador.get("nome") or f"Rev {rid}"
            sup       = p.get("supervisor_nome") or "Sem supervisora"
            nivel     = nivel_por_pecas(_qtd_original(p))
            preval    = float(p.get("valor_pre_baixa") or 0)
            p1        = primeiro_pedido.get(rid)
            meses     = _meses_na_equipe(p1, hoje) if p1 else None
            qtd       = _qtd_original(p)

            follow_ups.append({
                "pedido_id": p.get("id"),
                "tipo":      tipo,
                "nome":      nome,
                "supervisor": sup,
                "nivel":     nivel,
                "data_ped":  data_ped,
                "data_fu":   data_fu,
                "preval":    preval,
                "meses":     meses,
                "qtd":       qtd,
                "atrasado":  data_fu < hoje,
            })

    if not follow_ups:
        st.info(
            f"Nenhum acompanhamento D+3, D+7 ou D+20 cai nesta semana "
            f"({_semana_str(inicio, fim)})."
        )
        return

    # ── Feitos (Supabase + session_state) ────────────────────────────────────
    feitos = _get_feitos()  # {(pid, tipo): feito_em_str}

    # ── Resumo ────────────────────────────────────────────────────────────────
    total    = len(follow_ups)
    n_feitos = sum(1 for f in follow_ups if (f["pedido_id"], f["tipo"]) in feitos)
    n_pend   = total - n_feitos
    n_atras  = sum(
        1 for f in follow_ups
        if f["atrasado"] and (f["pedido_id"], f["tipo"]) not in feitos
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total da semana", total)
    m2.metric("✅ Feitos",        n_feitos)
    m3.metric("⏳ Pendentes",     n_pend)
    m4.metric("⚠️ Em atraso",     n_atras,
              delta=f"-{n_atras}" if n_atras else None, delta_color="inverse")

    if total > 0:
        pct = n_feitos / total
        st.progress(pct, text=f"{n_feitos}/{total} concluídos ({pct:.0%})")

    st.divider()

    # ── Agrupar por supervisora ───────────────────────────────────────────────
    por_sup: dict[str, list] = defaultdict(list)
    for f in follow_ups:
        por_sup[f["supervisor"]].append(f)

    tab_det, tab_res = st.tabs(["📋 Por supervisora", "📊 Resumo da semana"])

    # ════════════════════════════════════════════════════════════════════════
    # ABA 1 — Por supervisora (collapsible)
    # ════════════════════════════════════════════════════════════════════════
    with tab_det:
        for sup, items in sorted(por_sup.items()):
            n_f_sup  = sum(1 for f in items if (f["pedido_id"], f["tipo"]) in feitos)
            n_tot    = len(items)
            pct_icon = "✅" if n_f_sup == n_tot else ("⏳" if n_f_sup == 0 else "🔄")
            label_exp = f"👤 {sup}  ·  {pct_icon} {n_f_sup}/{n_tot} feitos"

            # Expander fechado por padrão; abre automaticamente se tiver pendentes
            tem_pendente = n_f_sup < n_tot
            with st.expander(label_exp, expanded=False):
                # Pendentes/atrasados primeiro
                items_ord = sorted(items, key=lambda x: (
                    (x["pedido_id"], x["tipo"]) in feitos,
                    not x["atrasado"],
                    x["data_fu"],
                    x["tipo"],
                ))

                for f in items_ord:
                    _render_card(f, feitos, hoje)

    # ════════════════════════════════════════════════════════════════════════
    # ABA 2 — Resumo da semana (pontualidade)
    # ════════════════════════════════════════════════════════════════════════
    with tab_res:
        st.markdown("#### Acompanhamentos realizados esta semana")
        st.caption("Mostra apenas os que foram marcados como ✅ Feito, com análise de pontualidade.")

        concluidos = [
            f for f in follow_ups
            if (f["pedido_id"], f["tipo"]) in feitos
        ]

        if not concluidos:
            st.info("Nenhum acompanhamento marcado como feito ainda nesta semana.")
        else:
            # Agrupa por supervisora
            por_sup_res: dict[str, list] = defaultdict(list)
            for f in concluidos:
                por_sup_res[f["supervisor"]].append(f)

            for sup, items in sorted(por_sup_res.items()):
                st.markdown(f"**👤 {sup}**")

                rows_html = ""
                for f in sorted(items, key=lambda x: (x["data_fu"], x["tipo"])):
                    pid      = f["pedido_id"]
                    tipo     = f["tipo"]
                    feito_em = feitos.get((pid, tipo), "")
                    tipo_cor = TIPO_COR[tipo]

                    data_prev_s = f["data_fu"].strftime("%d/%m")
                    feito_s     = _fmt_feito_em(feito_em) if feito_em else "—"

                    # Calcular pontualidade
                    pont_html = "—"
                    if feito_em:
                        try:
                            dt_feito = datetime.fromisoformat(
                                feito_em.replace("Z", "+00:00")
                            ).astimezone(timezone(timedelta(hours=-3))).date()
                            diff = (dt_feito - f["data_fu"]).days
                            if diff < 0:
                                pont_html = (
                                    f"<span style='color:#166534;font-weight:600'>"
                                    f"✅ {abs(diff)}d antes</span>"
                                )
                            elif diff == 0:
                                pont_html = (
                                    "<span style='color:#166534;font-weight:600'>"
                                    "✅ No dia</span>"
                                )
                            elif diff <= 2:
                                pont_html = (
                                    f"<span style='color:#854d0e;font-weight:600'>"
                                    f"⚠️ {diff}d depois</span>"
                                )
                            else:
                                pont_html = (
                                    f"<span style='color:#991b1b;font-weight:600'>"
                                    f"🔴 {diff}d depois</span>"
                                )
                        except Exception:
                            pass

                    rows_html += (
                        f"<tr>"
                        f"<td style='padding:6px 10px'>"
                        f"<span style='background:{tipo_cor};color:white;border-radius:5px;"
                        f"padding:1px 8px;font-size:.82em;font-weight:700'>{TIPO_LABEL[tipo]}</span>"
                        f"</td>"
                        f"<td style='padding:6px 10px'>{f['nome']}</td>"
                        f"<td style='padding:6px 10px;color:#7A6068'>{data_prev_s}</td>"
                        f"<td style='padding:6px 10px;color:#7A6068'>{feito_s}</td>"
                        f"<td style='padding:6px 10px'>{pont_html}</td>"
                        f"</tr>"
                    )

                st.markdown(
                    f"<table style='width:100%;border-collapse:collapse;margin-bottom:16px;"
                    f"background:white;border-radius:10px;overflow:hidden;"
                    f"box-shadow:0 1px 4px rgba(0,0,0,.06)'>"
                    f"<thead><tr style='background:#F5EBEC;color:#AB6774;font-size:.85em'>"
                    f"<th style='padding:7px 10px;text-align:left'>Tipo</th>"
                    f"<th style='padding:7px 10px;text-align:left'>Revendedora</th>"
                    f"<th style='padding:7px 10px;text-align:left'>Previsto</th>"
                    f"<th style='padding:7px 10px;text-align:left'>Realizado</th>"
                    f"<th style='padding:7px 10px;text-align:left'>Pontualidade</th>"
                    f"</tr></thead>"
                    f"<tbody>{rows_html}</tbody>"
                    f"</table>",
                    unsafe_allow_html=True,
                )

        # Pendentes na semana
        pendentes = [
            f for f in follow_ups
            if (f["pedido_id"], f["tipo"]) not in feitos
        ]
        if pendentes:
            st.markdown(f"#### ⏳ Ainda pendentes ({len(pendentes)})")
            rows_pend = ""
            for f in sorted(pendentes, key=lambda x: (x["supervisor"], x["data_fu"])):
                tipo_cor  = TIPO_COR[f["tipo"]]
                atras_txt = (
                    f"<span style='color:#991b1b;font-weight:600'>"
                    f"⚠️ {abs((f['data_fu'] - hoje).days)}d atraso</span>"
                    if f["atrasado"]
                    else f"<span style='color:#7A6068'>{f['data_fu'].strftime('%d/%m')}</span>"
                )
                rows_pend += (
                    f"<tr>"
                    f"<td style='padding:6px 10px'>"
                    f"<span style='background:{tipo_cor};color:white;border-radius:5px;"
                    f"padding:1px 8px;font-size:.82em;font-weight:700'>{TIPO_LABEL[f['tipo']]}</span>"
                    f"</td>"
                    f"<td style='padding:6px 10px'>{f['nome']}</td>"
                    f"<td style='padding:6px 10px;color:#7A6068'>{f['supervisor']}</td>"
                    f"<td style='padding:6px 10px'>{atras_txt}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<table style='width:100%;border-collapse:collapse;margin-bottom:16px;"
                f"background:white;border-radius:10px;overflow:hidden;"
                f"box-shadow:0 1px 4px rgba(0,0,0,.06)'>"
                f"<thead><tr style='background:#FEF2F2;color:#991b1b;font-size:.85em'>"
                f"<th style='padding:7px 10px;text-align:left'>Tipo</th>"
                f"<th style='padding:7px 10px;text-align:left'>Revendedora</th>"
                f"<th style='padding:7px 10px;text-align:left'>Supervisora</th>"
                f"<th style='padding:7px 10px;text-align:left'>Prazo</th>"
                f"</tr></thead>"
                f"<tbody>{rows_pend}</tbody>"
                f"</table>",
                unsafe_allow_html=True,
            )
