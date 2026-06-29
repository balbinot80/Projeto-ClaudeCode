from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.logic.revendedoras import parse_date

_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio",
          "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

_ANO_TESTE  = 2026
_MES_INICIO = 1
_MES_FIM    = 6
_MESES_GAP  = 4   # meses sem novo pedido para considerar retorno
_DIAS_PRAZO = 30  # dias que a supervisora soma na data_baixa


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cancelado_mesmo_mes(p: dict) -> bool:
    """Pedido criado e cancelado no mesmo mês — não conta como entrada."""
    d_cancel = parse_date(p.get("data_cancelamento"))
    if not d_cancel:
        return False
    d_cria = parse_date(p.get("data_criacao"))
    if not d_cria:
        return False
    return d_cria.year == d_cancel.year and d_cria.month == d_cancel.month


def _data_entrega(p: dict):
    """
    Data real de entrega da maleta à revendedora.
    Baixado: data_baixa - 30 dias  (a supervisora coloca data_baixa = entrega + 30 dias)
    Aberto:  data_criacao           (ainda com ela, entrega desconhecida)
    Cancelado: None                 (nunca entregue)
    """
    status = p.get("status", "")
    if p.get("data_cancelamento"):
        return None  # cancelado → sem entrega
    if status == "Baixado":
        d_baixa = parse_date(p.get("data_baixa"))
        if d_baixa:
            return d_baixa - timedelta(days=_DIAS_PRAZO)
    return parse_date(p.get("data_criacao"))


# ── Lógica principal ───────────────────────────────────────────────────────────

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

    # ── Entradas ──────────────────────────────────────────────────────────────
    for rid, itens in hist.items():
        contados = set()  # meses já contados para esta revendedora

        for i, (d_cria, p) in enumerate(itens):
            # Criado e cancelado no mesmo mês → ignora para efeito de entrada
            if _cancelado_mesmo_mes(p):
                continue

            # Data de entrega real da maleta
            d_entrega = _data_entrega(p)
            if not d_entrega:
                continue  # cancelado sem data ou sem data válida

            # Apenas dentro do período de teste
            if d_entrega.year != _ANO_TESTE:
                continue
            if not (_MES_INICIO <= d_entrega.month <= _MES_FIM):
                continue

            mes = d_entrega.month
            if mes in contados:
                continue  # revendedora já contada neste mês

            # Histórico anterior — exclui pedidos cancelados no mesmo mês de criação
            anteriores = [
                (d, pp) for d, pp in itens[:i]
                if not _cancelado_mesmo_mes(pp)
            ]

            if not anteriores:
                tipo = "🆕 Nova"
            else:
                # Gap comparado usando data_criacao do pedido anterior
                d_ant = anteriores[-1][0]
                gap = (d_cria.year - d_ant.year) * 12 + (d_cria.month - d_ant.month)
                if gap >= _MESES_GAP:
                    tipo = "🔄 Retorno"
                else:
                    continue  # revendedora ativa, não é entrada

            comprador  = p.get("comprador") or {}
            nome       = comprador.get("nome") or f"Rev {rid}"
            supervisor = p.get("supervisor_nome") or "Sem supervisora"

            entradas[mes].append({
                "rev_id":    rid,
                "Nome":      nome,
                "Supervisor": supervisor,
                "Data":      d_entrega.strftime("%d/%m/%Y"),
                "Tipo":      tipo,
            })
            contados.add(mes)

    # ── Saídas ────────────────────────────────────────────────────────────────
    for rid, itens in hist.items():
        if not itens:
            continue

        # Último pedido criado (desconsiderando cancelados mesmo mês)
        itens_validos = [(d, p) for d, p in itens if not _cancelado_mesmo_mes(p)]
        if not itens_validos:
            continue

        d_ultimo_cria, p_ultimo = itens_validos[-1]

        # Precisa estar Baixado (cancelado não é saída, apenas baixado sem continuidade)
        if p_ultimo.get("status") != "Baixado":
            continue

        # A "saída" ocorre no mês da data_baixa (mês do acerto final)
        d_baixa = parse_date(p_ultimo.get("data_baixa"))
        if not d_baixa:
            continue
        if d_baixa.year != _ANO_TESTE or not (_MES_INICIO <= d_baixa.month <= _MES_FIM):
            continue

        comprador  = p_ultimo.get("comprador") or {}
        nome       = comprador.get("nome") or f"Rev {rid}"
        supervisor = p_ultimo.get("supervisor_nome") or "Sem supervisora"

        # Tempo no time (da 1ª criação ao último baixo)
        d_primeira = itens_validos[0][0]
        meses_no_time = (
            (d_ultimo_cria.year - d_primeira.year) * 12
            + (d_ultimo_cria.month - d_primeira.month)
        )
        tempo_str = f"{meses_no_time} mes{'es' if meses_no_time != 1 else ''}"

        saidas[d_baixa.month].append({
            "rev_id":          rid,
            "Nome":            nome,
            "Supervisor":      supervisor,
            "1º pedido":       d_primeira.strftime("%d/%m/%Y"),
            "Último baixa":    d_baixa.strftime("%d/%m/%Y"),
            "Tempo no time":   tempo_str,
        })

    return entradas, saidas


# ── Insights ───────────────────────────────────────────────────────────────────

def _meses_de_str(tempo_str: str) -> int:
    """Extrai o número inteiro de meses de uma string como '7 meses'."""
    try:
        return int(tempo_str.split()[0])
    except Exception:
        return 0


def _render_insights(ents: list, sais: list, saldo: int, nome_mes: str):
    if not sais and not ents:
        return

    st.divider()
    st.markdown("#### 💡 Insights do mês")

    insights = []

    # ── Saldo ─────────────────────────────────────────────────────────────────
    if saldo > 0:
        insights.append(
            f"✅ **Crescimento líquido de {saldo} revendedora(s)** em {nome_mes} — "
            "o time está em expansão."
        )
    elif saldo < 0:
        insights.append(
            f"⚠️ **Perda líquida de {abs(saldo)} revendedora(s)** em {nome_mes} — "
            "as saídas superaram as entradas. Vale revisar os motivos."
        )
    else:
        insights.append(
            f"↔️ **Saldo neutro** em {nome_mes}: entradas e saídas empatadas. "
            "O time manteve o tamanho, mas houve rotatividade."
        )

    # ── Tempo médio no time das que saíram ────────────────────────────────────
    if sais:
        meses_lista = [_meses_de_str(r["Tempo no time"]) for r in sais]
        media = sum(meses_lista) / len(meses_lista)
        precoces = sum(1 for m in meses_lista if m < 3)
        longas   = sum(1 for m in meses_lista if m >= 12)

        insights.append(
            f"⏱️ **Tempo médio no time das que saíram: {media:.1f} meses.** "
            + (f"  {precoces} delas ficaram menos de 3 meses — saída precoce, "
               "pode indicar problema na integração ou expectativas." if precoces else "")
            + (f"  {longas} tinham mais de 1 ano — perda de revendedoras experientes." if longas else "")
        )

        # Supervisora com mais saídas
        from collections import Counter
        contagem_sup = Counter(r["Supervisor"] for r in sais)
        sup_top, qtd_top = contagem_sup.most_common(1)[0]
        if qtd_top >= 2:
            insights.append(
                f"📌 **{sup_top}** concentrou {qtd_top} das {len(sais)} saídas deste mês. "
                "Pode valer uma conversa para entender o que está acontecendo."
            )

    # ── Retornos entre as entradas ─────────────────────────────────────────────
    retornos = [r for r in ents if r.get("Tipo") == "🔄 Retorno"]
    if retornos:
        insights.append(
            f"🔄 **{len(retornos)} retorno(s)** neste mês — "
            f"revendedoras que voltaram após {_MESES_GAP}+ meses. "
            "Estratégias de reativação podem estar funcionando."
        )

    # ── Proporção saídas/entradas ──────────────────────────────────────────────
    if ents and sais:
        taxa = len(sais) / len(ents) * 100
        if taxa >= 80:
            insights.append(
                f"🔴 **Alta rotatividade:** {taxa:.0f}% de proporção saídas/entradas. "
                "Para cada revendedora nova que entra, quase uma sai."
            )
        elif taxa >= 50:
            insights.append(
                f"🟡 **Rotatividade moderada:** {taxa:.0f}% de proporção saídas/entradas."
            )

    for msg in insights:
        st.markdown(f"- {msg}")


# ── Render ─────────────────────────────────────────────────────────────────────

def render():
    st.title("📊 Entradas e Saídas de Revendedoras")
    _mes_ini_label = _MESES[_MES_INICIO - 1]
    _mes_fim_label = _MESES[_MES_FIM - 1]
    st.caption(
        f"Teste — {_mes_ini_label} a {_mes_fim_label} de {_ANO_TESTE} · "
        f"Entrada = mês da data de baixa − {_DIAS_PRAZO} dias · "
        f"Retorno = novo pedido após {_MESES_GAP}+ meses sem atividade · "
        f"Pedidos criados e cancelados no mesmo mês são desconsiderados."
    )

    from src.api.jueri_client import _get_lista_pedidos

    try:
        with st.spinner("Carregando pedidos..."):
            todos_pedidos = _get_lista_pedidos()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    entradas, saidas = _calcular(todos_pedidos)

    # ── Filtro ────────────────────────────────────────────────────────────────
    supervisoras = sorted({
        p.get("supervisor_nome")
        for p in todos_pedidos
        if p.get("supervisor_nome")
    })

    col_f, _ = st.columns([2, 4])
    with col_f:
        filtro_sup = st.selectbox("Supervisora", ["Todas"] + supervisoras, key="es_sup")

    def _filtrar(rows):
        if filtro_sup == "Todas":
            return rows
        return [r for r in rows if r.get("Supervisor") == filtro_sup]

    st.divider()

    # ── Resumo acumulado ──────────────────────────────────────────────────────
    _rng = range(_MES_INICIO, _MES_FIM + 1)
    _abrev_ini = _MESES[_MES_INICIO - 1][:3]
    _abrev_fim = _MESES[_MES_FIM - 1][:3]
    _periodo   = f"{_abrev_ini}–{_abrev_fim}"

    tot_novas    = sum(len([r for r in _filtrar(entradas[m]) if r["Tipo"] == "🆕 Nova"])    for m in _rng)
    tot_retornos = sum(len([r for r in _filtrar(entradas[m]) if r["Tipo"] == "🔄 Retorno"]) for m in _rng)
    tot_saidas   = sum(len(_filtrar(saidas[m])) for m in _rng)
    tot_ent      = tot_novas + tot_retornos
    saldo        = tot_ent - tot_saidas

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"🆕 Novas ({_periodo})",    tot_novas)
    c2.metric(f"🔄 Retornos ({_periodo})", tot_retornos)
    c3.metric("📥 Total entradas",         tot_ent)
    c4.metric("📤 Total saídas",           tot_saidas)
    c5.metric("📊 Saldo período",          f"{saldo:+d}")

    st.divider()

    # ── Mês a mês (abas) ──────────────────────────────────────────────────────
    tabs = st.tabs([_MESES[m - 1] for m in range(_MES_INICIO, _MES_FIM + 1)])

    for tab, mes in zip(tabs, range(_MES_INICIO, _MES_FIM + 1)):
        with tab:
            ents = _filtrar(entradas[mes])
            sais = _filtrar(saidas[mes])

            novas    = [r for r in ents if r["Tipo"] == "🆕 Nova"]
            retornos = [r for r in ents if r["Tipo"] == "🔄 Retorno"]

            n_ent   = len(ents)
            n_sai   = len(sais)
            saldo_m = n_ent - n_sai

            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric("🆕 Novas",    len(novas))
            cm2.metric("🔄 Retornos", len(retornos))
            cm3.metric("📤 Saídas",   n_sai)
            cm4.metric("📊 Saldo",    f"{saldo_m:+d}")

            st.markdown("")
            col_e, col_s = st.columns(2)

            with col_e:
                st.markdown(f"**📥 Entradas — {n_ent}**")

                if novas:
                    st.caption(f"🆕 Novas — {len(novas)}")
                    df_n = pd.DataFrame(novas)[["Nome", "Supervisor", "Data"]]
                    st.dataframe(df_n, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome":       st.column_config.TextColumn("Revendedora"),
                                     "Supervisor": st.column_config.TextColumn("Supervisora"),
                                     "Data":       st.column_config.TextColumn("Data entrega"),
                                 })

                if retornos:
                    st.caption(f"🔄 Retornos ({_MESES_GAP}+ meses) — {len(retornos)}")
                    df_r = pd.DataFrame(retornos)[["Nome", "Supervisor", "Data"]]
                    st.dataframe(df_r, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome":       st.column_config.TextColumn("Revendedora"),
                                     "Supervisor": st.column_config.TextColumn("Supervisora"),
                                     "Data":       st.column_config.TextColumn("Data retorno"),
                                 })

                if not ents:
                    st.caption("Nenhuma entrada neste mês.")

            with col_s:
                st.markdown(f"**📤 Saídas — {n_sai}**")

                if sais:
                    df_s = pd.DataFrame(sais)[["Nome", "Supervisor", "1º pedido", "Último baixa", "Tempo no time"]]
                    st.dataframe(df_s, hide_index=True, use_container_width=True,
                                 column_config={
                                     "Nome":          st.column_config.TextColumn("Revendedora"),
                                     "Supervisor":    st.column_config.TextColumn("Supervisora"),
                                     "1º pedido":     st.column_config.TextColumn("1º pedido"),
                                     "Último baixa":  st.column_config.TextColumn("Última baixa"),
                                     "Tempo no time": st.column_config.TextColumn("Tempo no time"),
                                 })
                else:
                    st.caption("Nenhuma saída neste mês.")

            # ── Insights do mês ───────────────────────────────────────────────
            _render_insights(ents, sais, saldo_m, _MESES[mes - 1])
