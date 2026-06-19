from collections import defaultdict
from datetime import date

import pandas as pd
import streamlit as st

from src.logic.revendedoras import parse_date

_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio",
          "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

_ANO_TESTE  = 2026
_MES_INICIO = 1
_MES_FIM    = 5
_MESES_GAP  = 4  # meses sem pedido para considerar retorno


# ── Lógica ─────────────────────────────────────────────────────────────────────

def _historico_por_rev(todos_pedidos: list) -> dict:
    """Retorna {rev_id: [(data_criacao, pedido), ...]} ordenado por data_criacao."""
    hist = defaultdict(list)
    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        d = parse_date(p.get("data_criacao"))
        if d:
            hist[rid].append((d, p))
    for rid in hist:
        hist[rid].sort(key=lambda x: x[0])
    return hist


def _calcular(todos_pedidos: list):
    hist = _historico_por_rev(todos_pedidos)

    entradas = defaultdict(list)  # {mes: [row]}
    saidas   = defaultdict(list)

    # ── Entradas ──────────────────────────────────────────────────────────
    for rid, itens in hist.items():
        contados = set()

        for i, (d_cria, p) in enumerate(itens):
            if d_cria.year != _ANO_TESTE:
                continue
            if not (_MES_INICIO <= d_cria.month <= _MES_FIM):
                continue

            mes = d_cria.month
            if mes in contados:
                continue  # já contou esta revendedora neste mês

            anteriores = itens[:i]  # todos os pedidos ANTES deste (qualquer ano)

            if not anteriores:
                tipo = "🆕 Nova"
            else:
                d_ant = anteriores[-1][0]
                gap = (d_cria.year - d_ant.year) * 12 + (d_cria.month - d_ant.month)
                if gap >= _MESES_GAP:
                    tipo = "🔄 Retorno"
                else:
                    continue  # revendedora ativa, não é entrada

            comprador = p.get("comprador") or {}
            nome      = comprador.get("nome") or f"Rev {rid}"
            supervisor = p.get("supervisor_nome") or "Sem supervisora"

            entradas[mes].append({
                "rev_id":    rid,
                "Nome":      nome,
                "Supervisor": supervisor,
                "Data":      d_cria.strftime("%d/%m/%Y"),
                "Tipo":      tipo,
            })
            contados.add(mes)

    # ── Saídas ────────────────────────────────────────────────────────────
    for rid, itens in hist.items():
        if not itens:
            continue

        # Último pedido criado para esta revendedora (de toda a história)
        d_ultimo_cria, p_ultimo = itens[-1]

        # Precisa estar Baixado
        if p_ultimo.get("status") != "Baixado":
            continue

        # A data de baixa precisa estar dentro do período de teste
        d_baixa = parse_date(p_ultimo.get("data_baixa"))
        if not d_baixa:
            continue
        if d_baixa.year != _ANO_TESTE or not (_MES_INICIO <= d_baixa.month <= _MES_FIM):
            continue

        comprador  = p_ultimo.get("comprador") or {}
        nome       = comprador.get("nome") or f"Rev {rid}"
        supervisor = p_ultimo.get("supervisor_nome") or "Sem supervisora"

        # Data de criação do primeiro pedido (para calcular tempo de time)
        d_entrada = itens[0][0]
        meses_no_time = (d_ultimo_cria.year - d_entrada.year) * 12 + \
                        (d_ultimo_cria.month - d_entrada.month)

        saidas[d_baixa.month].append({
            "rev_id":        rid,
            "Nome":          nome,
            "Supervisor":    supervisor,
            "Último baixa":  d_baixa.strftime("%d/%m/%Y"),
            "Tempo no time": f"{meses_no_time} mes{'es' if meses_no_time != 1 else ''}",
        })

    return entradas, saidas


# ── Render ──────────────────────────────────────────────────────────────────────

def render():
    st.title("📊 Entradas e Saídas de Revendedoras")
    st.caption(
        f"Teste — Janeiro a Maio de {_ANO_TESTE}. "
        f"Nova = 1º pedido da revendedora. "
        f"Retorno = pedido após {_MESES_GAP}+ meses sem atividade."
    )

    from src.api.jueri_client import _get_lista_pedidos

    try:
        with st.spinner("Carregando pedidos..."):
            todos_pedidos = _get_lista_pedidos()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    entradas, saidas = _calcular(todos_pedidos)

    # ── Filtro de supervisora ──────────────────────────────────────────────
    supervisoras = sorted({
        p.get("supervisor_nome")
        for p in todos_pedidos
        if p.get("supervisor_nome")
    })
    col_f, col_r = st.columns([2, 4])
    with col_f:
        filtro_sup = st.selectbox("Supervisora", ["Todas"] + supervisoras, key="es_sup")

    st.divider()

    # ── Resumo acumulado ───────────────────────────────────────────────────
    def _filtrar(rows):
        if filtro_sup == "Todas":
            return rows
        return [r for r in rows if r.get("Supervisor") == filtro_sup]

    tot_novas    = sum(len([r for r in _filtrar(entradas[m]) if r["Tipo"] == "🆕 Nova"])   for m in range(1, 6))
    tot_retornos = sum(len([r for r in _filtrar(entradas[m]) if r["Tipo"] == "🔄 Retorno"]) for m in range(1, 6))
    tot_saidas   = sum(len(_filtrar(saidas[m])) for m in range(1, 6))
    tot_ent      = tot_novas + tot_retornos
    saldo        = tot_ent - tot_saidas

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🆕 Novas (Jan–Mai)",    tot_novas)
    c2.metric("🔄 Retornos (Jan–Mai)", tot_retornos)
    c3.metric("📥 Total entradas",     tot_ent)
    c4.metric("📤 Total saídas",       tot_saidas)
    c5.metric("📊 Saldo período",      f"{saldo:+d}")

    st.divider()

    # ── Mês a mês ─────────────────────────────────────────────────────────
    tabs = st.tabs([_MESES[m - 1] for m in range(_MES_INICIO, _MES_FIM + 1)])

    for tab, mes in zip(tabs, range(_MES_INICIO, _MES_FIM + 1)):
        with tab:
            ents = _filtrar(entradas[mes])
            sais = _filtrar(saidas[mes])

            novas    = [r for r in ents if r["Tipo"] == "🆕 Nova"]
            retornos = [r for r in ents if r["Tipo"] == "🔄 Retorno"]

            n_ent  = len(ents)
            n_sai  = len(sais)
            saldo_m = n_ent - n_sai

            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric("🆕 Novas",    len(novas))
            cm2.metric("🔄 Retornos", len(retornos))
            cm3.metric("📤 Saídas",   n_sai)
            cm4.metric("📊 Saldo",    f"{saldo_m:+d}",
                       delta=None,
                       help="Entradas menos saídas no mês")

            st.markdown("")
            col_e, col_s = st.columns(2)

            # ── Entradas ──────────────────────────────────────────────────
            with col_e:
                st.markdown(f"**📥 Entradas — {n_ent}**")

                if novas:
                    st.caption(f"🆕 Novas — {len(novas)}")
                    df_n = pd.DataFrame(novas)[["Nome", "Supervisor", "Data"]]
                    st.dataframe(df_n, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome": st.column_config.TextColumn("Revendedora"),
                                     "Supervisor": st.column_config.TextColumn("Supervisora"),
                                     "Data": st.column_config.TextColumn("Data 1º pedido"),
                                 })

                if retornos:
                    st.caption(f"🔄 Retornos ({_MESES_GAP}+ meses) — {len(retornos)}")
                    df_r = pd.DataFrame(retornos)[["Nome", "Supervisor", "Data"]]
                    st.dataframe(df_r, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome": st.column_config.TextColumn("Revendedora"),
                                     "Supervisor": st.column_config.TextColumn("Supervisora"),
                                     "Data": st.column_config.TextColumn("Data retorno"),
                                 })

                if not ents:
                    st.caption("Nenhuma entrada neste mês.")

            # ── Saídas ────────────────────────────────────────────────────
            with col_s:
                st.markdown(f"**📤 Saídas — {n_sai}**")

                if sais:
                    df_s = pd.DataFrame(sais)[["Nome", "Supervisor", "Último baixa", "Tempo no time"]]
                    st.dataframe(df_s, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome": st.column_config.TextColumn("Revendedora"),
                                     "Supervisor": st.column_config.TextColumn("Supervisora"),
                                     "Último baixa": st.column_config.TextColumn("Última baixa"),
                                     "Tempo no time": st.column_config.TextColumn("Tempo no time"),
                                 })
                else:
                    st.caption("Nenhuma saída neste mês.")
