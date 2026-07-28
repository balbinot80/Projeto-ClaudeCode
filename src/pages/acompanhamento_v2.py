"""
Acompanhamento Semanal — D+3, D+7, D+20
Tela admin para controle do nível de atendimento das supervisoras.
"""
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from src.api.jueri_client import _get_lista_pedidos, get_pedidos_abertos
from src.logic.niveis import ICONE_NIVEL, _qtd_original, nivel_por_pecas

# ── Constantes visuais ────────────────────────────────────────────────────────

ROSA  = "#AB6774"
GOLD  = "#C4985A"
CREME = "#FAF7F4"

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


@st.cache_data(ttl=60, show_spinner=False)
def _carregar_feitos() -> set:
    """Retorna conjunto de (pedido_id, tipo) marcados como feito."""
    client = _get_client()
    if not client:
        return set()
    try:
        res = client.table("follow_ups_semana").select(
            "pedido_id,tipo"
        ).eq("feito", True).execute()
        return {(r["pedido_id"], r["tipo"]) for r in (res.data or [])}
    except Exception:
        return set()


def _toggle_feito(pedido_id: int, tipo: str, feito: bool) -> bool:
    client = _get_client()
    if not client:
        st.toast("⚠️ Supabase não configurado — salvo apenas nesta sessão.", icon="⚠️")
        return False
    try:
        client.table("follow_ups_semana").upsert(
            {
                "pedido_id": pedido_id,
                "tipo": tipo,
                "feito": feito,
                "feito_em": datetime.now(timezone.utc).isoformat() if feito else None,
            },
            on_conflict="pedido_id,tipo",
        ).execute()
        _carregar_feitos.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _semana_str(inicio: date, fim: date) -> str:
    if inicio.month == fim.month:
        return f"{inicio.strftime('%d')} a {fim.strftime('%d/%m/%Y')}"
    return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m/%Y')}"


def _meses_na_equipe(primeira: date, hoje: date) -> int:
    return (hoje.year - primeira.year) * 12 + (hoje.month - primeira.month)


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _urgencia_txt(data_fu: date, hoje: date, feito: bool) -> str:
    if feito:
        return "✅ Feito"
    delta = (data_fu - hoje).days
    if delta == 0:
        return "📌 Hoje"
    if delta < 0:
        return f"⚠️ {abs(delta)}d atraso"
    if delta == 1:
        return "⏰ Amanhã"
    return f"em {delta}d ({data_fu.strftime('%d/%m')})"


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
        .fu-card.feito    { border-left-color: #22c55e; opacity: .65; }
        .fu-card.atrasado { border-left-color: #ef4444; }
        .fu-card .top-row {
            display: flex; align-items: center; gap: 10px; margin-bottom: 5px;
        }
        .fu-card .meta-row {
            display: flex; gap: 18px; font-size: .84em; color: #7A6068; flex-wrap: wrap;
        }
        .tag-tipo {
            color: white; border-radius: 6px; padding: 2px 10px;
            font-weight: 700; font-size: .88em; white-space: nowrap;
        }
        .badge-n {
            border-radius: 20px; padding: 1px 9px;
            font-size: .77em; font-weight: 700; white-space: nowrap;
        }
        .urgencia {
            margin-left: auto; font-size: .87em; color: #7A6068; white-space: nowrap;
        }
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
    seg_base = hoje - timedelta(days=hoje.weekday())  # segunda-feira da semana atual
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
            abertos      = get_pedidos_abertos()
            todos        = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    # Mapa rid → data do primeiro pedido (proxy de "tempo na equipe")
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

    # ── Calcular follow-ups da semana selecionada ─────────────────────────────
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

            rid        = p.get("fk_revendedor_id")
            comprador  = p.get("comprador") or {}
            nome       = comprador.get("nome") or f"Rev {rid}"
            sup        = p.get("supervisor_nome") or "Sem supervisora"
            nivel      = nivel_por_pecas(_qtd_original(p))
            preval     = float(p.get("valor_pre_baixa") or 0)
            p1         = primeiro_pedido.get(rid)
            meses      = _meses_na_equipe(p1, hoje) if p1 else None
            qtd_pecas  = _qtd_original(p)

            follow_ups.append({
                "pedido_id":  p.get("id"),
                "tipo":       tipo,
                "nome":       nome,
                "supervisor": sup,
                "nivel":      nivel,
                "data_ped":   data_ped,
                "data_fu":    data_fu,
                "preval":     preval,
                "meses":      meses,
                "qtd_pecas":  qtd_pecas,
                "atrasado":   data_fu < hoje,
            })

    if not follow_ups:
        st.info(
            f"Nenhum acompanhamento D+3, D+7 ou D+20 cai nesta semana "
            f"({_semana_str(inicio, fim)})."
        )
        return

    # ── Status "feito" no Supabase ────────────────────────────────────────────
    feitos = _carregar_feitos()

    # ── Resumo ────────────────────────────────────────────────────────────────
    total     = len(follow_ups)
    n_feitos  = sum(1 for f in follow_ups if (f["pedido_id"], f["tipo"]) in feitos)
    n_pend    = total - n_feitos
    n_atras   = sum(
        1 for f in follow_ups
        if f["atrasado"] and (f["pedido_id"], f["tipo"]) not in feitos
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total da semana",    total)
    m2.metric("✅ Feitos",           n_feitos)
    m3.metric("⏳ Pendentes",        n_pend)
    m4.metric(
        "⚠️ Em atraso",
        n_atras,
        delta=f"-{n_atras}" if n_atras else None,
        delta_color="inverse",
    )

    # Barra de progresso
    if total > 0:
        pct = n_feitos / total
        st.progress(pct, text=f"{n_feitos}/{total} concluídos ({pct:.0%})")

    st.divider()

    # ── Filtro por supervisora ────────────────────────────────────────────────
    sups = sorted({f["supervisor"] for f in follow_ups})
    sup_sel = st.selectbox(
        "Filtrar por supervisora",
        options=["Todas"] + sups,
        key="acomp_sup_filtro",
        label_visibility="collapsed",
    )

    lista = follow_ups if sup_sel == "Todas" else [
        f for f in follow_ups if f["supervisor"] == sup_sel
    ]

    # ── Agrupar e renderizar por supervisora ──────────────────────────────────
    por_sup: dict[str, list] = defaultdict(list)
    for f in lista:
        por_sup[f["supervisor"]].append(f)

    for sup, items in sorted(por_sup.items()):
        n_f_sup  = sum(1 for f in items if (f["pedido_id"], f["tipo"]) in feitos)
        pct_sup  = f"{n_f_sup}/{len(items)}"
        pct_icon = "✅" if n_f_sup == len(items) else "⏳"

        st.markdown(
            f"<div class='sup-header'>"
            f"<span>👤 {sup}</span>"
            f"<span style='margin-left:auto;font-weight:400;font-size:.92em'>"
            f"{pct_icon} {pct_sup} feitos</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Ordena: pendentes/atrasados primeiro, depois por data, depois por tipo
        items_ord = sorted(items, key=lambda x: (
            (x["pedido_id"], x["tipo"]) in feitos,
            not x["atrasado"],
            x["data_fu"],
            x["tipo"],
        ))

        for f in items_ord:
            pid   = f["pedido_id"]
            tipo  = f["tipo"]
            feito = (pid, tipo) in feitos
            atras = f["atrasado"] and not feito

            cls        = "feito" if feito else ("atrasado" if atras else "")
            emoji_n, bg_n, fg_n = BADGE_NIVEL.get(f["nivel"], ("—", "#E5E7EB", "#6B7280"))
            tipo_cor   = TIPO_COR[tipo]
            meses_txt  = f"{f['meses']} meses na equipe" if f["meses"] is not None else "—"
            preval_txt = _fmt_brl(f["preval"]) if f["preval"] > 0 else "—"
            urgencia   = _urgencia_txt(f["data_fu"], hoje, feito)
            data_ped_s = f["data_ped"].strftime("%d/%m")
            data_fu_s  = f["data_fu"].strftime("%d/%m")

            col_card, col_btn = st.columns([6, 1])
            with col_card:
                st.markdown(
                    f"<div class='fu-card {cls}'>"
                    f"<div class='top-row'>"
                    f"<span class='tag-tipo' style='background:{tipo_cor}'>{TIPO_LABEL[tipo]}</span>"
                    f"<span class='nome-rev'>{f['nome']}</span>"
                    f"<span class='badge-n' style='background:{bg_n};color:{fg_n}'>"
                    f"{emoji_n} {f['nivel']}</span>"
                    f"<span class='urgencia'>{urgencia}</span>"
                    f"</div>"
                    f"<div class='meta-row'>"
                    f"<span>📦 Pedido: {data_ped_s}</span>"
                    f"<span>📅 Acomp.: {data_fu_s}</span>"
                    f"<span>💰 Pré-baixa: {preval_txt}</span>"
                    f"<span>🧩 {f['qtd_pecas']} peças</span>"
                    f"<span>⏳ {meses_txt}</span>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_btn:
                lbl = "↩ Desfazer" if feito else "✅ Feito"
                btn_type = "secondary" if feito else "primary"
                if st.button(lbl, key=f"fu_{pid}_{tipo}", use_container_width=True, type=btn_type):
                    ok = _toggle_feito(pid, tipo, not feito)
                    if ok:
                        st.rerun()
                    else:
                        # Fallback: session-state local
                        key_local = f"_fu_local_{pid}_{tipo}"
                        st.session_state[key_local] = not feito
                        st.rerun()

    st.divider()
    st.caption(
        "💡 **Legenda:** "
        "🔵 D+3 = 3 dias após criação do pedido · "
        "🟣 D+7 = 7 dias · "
        "🟡 D+20 = 20 dias · "
        "⚠️ Em atraso = data já passou e não foi marcado como feito"
    )
    st.caption(
        "ℹ️ Os acompanhamentos marcados como ✅ Feito são salvos no Supabase "
        "e persistem entre sessões. O tempo na equipe é calculado a partir "
        "do primeiro pedido da revendedora."
    )
