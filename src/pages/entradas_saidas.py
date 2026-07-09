from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.logic.revendedoras import parse_date

_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio",
          "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

_MES_INICIO = 1
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


def _calcular(todos_pedidos: list, ano: int, mes_inicio: int, mes_fim: int):
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

            # Apenas dentro do período
            if d_entrega.year != ano:
                continue
            if not (mes_inicio <= d_entrega.month <= mes_fim):
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
        if d_baixa.year != ano or not (mes_inicio <= d_baixa.month <= mes_fim):
            continue

        # Se existir qualquer pedido criado no mesmo mês da baixa ou depois → não é saída
        inicio_mes_baixa = d_baixa.replace(day=1)
        tem_pedido_posterior = any(
            d_cria >= inicio_mes_baixa
            for j, (d_cria, _) in enumerate(itens_validos)
            if j < len(itens_validos) - 1
        )
        if tem_pedido_posterior:
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
    try:
        return int(tempo_str.split()[0])
    except Exception:
        return 0


def _render_insights(ents: list, sais: list, saldo: int, nome_mes: str):
    """Insights mensais baseados em pesquisas de Gallup, McKinsey, HBR, ABEVD e Xactly."""
    if not sais and not ents:
        return

    alertas   = []
    positivos = []
    analises  = []

    n_sai = len(sais)
    n_ent = len(ents)

    # ── 1. Saldo ──────────────────────────────────────────────────────────────
    if saldo > 0:
        positivos.append(
            f"✅ **Saldo positivo de +{saldo} revendedora(s) em {nome_mes}.** "
            "O setor de venda direta no Brasil cresceu 6,3% em 2024 (ABEVD, 2025). "
            "Estar em expansão posiciona a equipe acima da média do setor."
        )
    elif saldo < 0:
        alertas.append(
            f"⚠️ **Saldo negativo de {saldo} em {nome_mes}** — saídas superaram entradas. "
            "Segundo a Harvard Business Review, reter uma revendedora custa de **5x a 25x menos** "
            "do que recrutar e integrar uma nova. Cada saída representa custo oculto significativo."
        )
    else:
        analises.append(
            f"↔️ **Saldo neutro em {nome_mes}.** O time se manteve estável, mas houve rotatividade. "
            "Crescimento zero combinado com saídas expressivas pode sinalizar estagnação — "
            "McKinsey ('The Great Attrition', 2022) aponta que times estagnados tendem a "
            "perder produtividade mesmo sem redução de headcount."
        )

    # ── 2. Proporção saídas/entradas ──────────────────────────────────────────
    if n_ent > 0 and n_sai > 0:
        proporcao = n_sai / n_ent * 100
        # Benchmark: Xactly Corp (2024) — equipes comerciais têm ~35% de rotatividade anual
        # ≈ 2,9%/mês. Aqui usamos a proporção saídas/entradas como proxy de pressão.
        if proporcao >= 80:
            alertas.append(
                f"🔴 **Alta pressão de rotatividade: {proporcao:.0f}% de proporção saídas/entradas.** "
                "Para cada revendedora nova que entra, quase uma sai. "
                "A Xactly Corp (2024) reporta que equipes de vendas têm rotatividade média de "
                "35% ao ano — acima disso, o custo de substituição compromete o crescimento líquido."
            )
        elif proporcao >= 50:
            analises.append(
                f"🟡 **Rotatividade moderada: {proporcao:.0f}% de proporção saídas/entradas.** "
                "Benchmark de referência: Xactly Corp (2024) — 35% ao ano para equipes comerciais. "
                "Monitorar a tendência nos próximos meses."
            )

    # ── 3. Saídas precoces — primeiros 90 dias ────────────────────────────────
    if sais:
        meses_lista = [_meses_de_str(r["Tempo no time"]) for r in sais]
        media       = sum(meses_lista) / len(meses_lista)
        precoces    = sum(1 for m in meses_lista if m < 3)
        longas      = sum(1 for m in meses_lista if m >= 12)
        pct_precoces = precoces / n_sai * 100 if n_sai else 0

        if precoces:
            msg = (
                f"🚨 **{precoces} saída(s) precoce(s) ({pct_precoces:.0f}% do total)** — "
                "revendedoras que saíram com menos de 3 meses no time. "
                "Os **primeiros 90 dias** são o período mais crítico: a DSA (Direct Selling Association, 2024) "
                "e a McKinsey identificam o onboarding como fator #1 de retenção no setor. "
                "Distribuidores que não concluem uma venda no primeiro ciclo têm probabilidade "
                "muito maior de abandono. Ação recomendada: acompanhamento intensivo nas primeiras 4 semanas."
            )
            if pct_precoces >= 30:
                alertas.append(msg)
            else:
                analises.append(msg)

        # Tempo médio
        tempo_msg = f"⏱️ **Tempo médio no time das que saíram: {media:.1f} meses.**"
        if longas:
            tempo_msg += (
                f" {longas} tinham mais de 12 meses — perda de revendedoras experientes com "
                "carteira de clientes formada. O Gallup (2023) estima que substituir um colaborador "
                "experiente custa entre **50% e 200% da remuneração anual** equivalente, "
                "considerando recrutamento, integração e queda de produtividade."
            )
        analises.append(tempo_msg)

    # ── 4. Concentração de saídas por supervisora ─────────────────────────────
    if sais:
        from collections import Counter
        contagem_sup = Counter(r["Supervisor"] for r in sais)
        sup_top, qtd_top = contagem_sup.most_common(1)[0]
        pct_sup = qtd_top / n_sai * 100
        if pct_sup >= 40 and qtd_top >= 2:
            alertas.append(
                f"📌 **{sup_top} concentrou {qtd_top} das {n_sai} saídas ({pct_sup:.0f}%).** "
                "A McKinsey ('The Great Attrition', 2022) aponta que **gestão direta** é a "
                "3ª maior causa de saída em equipes comerciais (31% dos casos), atrás de "
                "falta de crescimento (41%) e remuneração (36%). "
                "Uma concentração de saídas em uma equipe específica merece investigação."
            )

    # ── 5. Retornos ───────────────────────────────────────────────────────────
    retornos = [r for r in ents if r.get("Tipo") == "🔄 Retorno"]
    if retornos:
        positivos.append(
            f"🔄 **{len(retornos)} retorno(s) em {nome_mes}** — ex-revendedoras que voltaram após "
            f"{_MESES_GAP}+ meses inativas. "
            "Estratégias de reativação são **2-3x mais eficientes** do que prospectar novas: "
            "ex-revendedoras já conhecem o produto, a dinâmica e têm histórico de vendas. "
            "*(HBR: 'The Economics of Winning Back Lost Customers')*"
        )

    # ── Renderização ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 💡 Análise do mês")

    if alertas:
        st.markdown("**🔴 Pontos de atenção:**")
        for msg in alertas:
            st.markdown(f"- {msg}")

    if positivos:
        st.markdown("**🟢 Pontos positivos:**")
        for msg in positivos:
            st.markdown(f"- {msg}")

    if analises:
        st.markdown("**📊 Contexto e benchmarks:**")
        for msg in analises:
            st.markdown(f"- {msg}")


def _render_insights_periodo(dados_meses: list):
    """
    Análise consolidada do período completo.
    dados_meses: lista de dicts {mes, nome, n_ent, n_sai, saldo, sais}
    """
    if not dados_meses:
        return

    st.divider()
    st.markdown("## 🔬 Análise consolidada do período")
    st.caption(
        "Baseado em: ABEVD Anuário 2025 · Gallup Workplace 2023 · McKinsey 'The Great Attrition' 2022 · "
        "Harvard Business Review · Xactly Corp Sales Turnover 2024 · "
        "DIEESE/Robert Half Rotatividade Brasil 2024"
    )

    total_ent  = sum(d["n_ent"] for d in dados_meses)
    total_sai  = sum(d["n_sai"] for d in dados_meses)
    saldo_per  = total_ent - total_sai
    n_meses    = len(dados_meses)

    # Taxa de retenção do período: (entradas - saídas) / entradas
    taxa_retencao = (1 - total_sai / total_ent) * 100 if total_ent > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Taxa de retenção no período", f"{taxa_retencao:.1f}%",
                help="(Entradas − Saídas) / Entradas × 100")
    col2.metric("Média de saídas/mês", f"{total_sai / n_meses:.1f}")
    col3.metric("Média de entradas/mês", f"{total_ent / n_meses:.1f}")

    st.markdown("")

    # ── Tendência: meses com saldo negativo consecutivos ──────────────────────
    saldos = [d["saldo"] for d in dados_meses]
    negativos_consecutivos = 0
    max_neg_consecutivos   = 0
    for s in saldos:
        if s < 0:
            negativos_consecutivos += 1
            max_neg_consecutivos = max(max_neg_consecutivos, negativos_consecutivos)
        else:
            negativos_consecutivos = 0

    melhor_mes = max(dados_meses, key=lambda d: d["saldo"])
    pior_mes   = min(dados_meses, key=lambda d: d["saldo"])

    st.markdown("**📈 Tendência de crescimento:**")
    tendencia_items = [
        f"Melhor mês: **{melhor_mes['nome']}** (saldo {melhor_mes['saldo']:+d})",
        f"Pior mês: **{pior_mes['nome']}** (saldo {pior_mes['saldo']:+d})",
    ]
    if max_neg_consecutivos >= 2:
        tendencia_items.append(
            f"⚠️ **{max_neg_consecutivos} meses consecutivos com saldo negativo** detectados. "
            "McKinsey aponta que padrões de declínio persistentes exigem revisão estrutural "
            "da estratégia de captação e retenção — ajustes pontuais tendem a não resolver."
        )
    for item in tendencia_items:
        st.markdown(f"- {item}")

    # ── Análise de saídas precoces no período ─────────────────────────────────
    todas_sais = []
    for d in dados_meses:
        todas_sais.extend(d["sais"])

    precoces_total = 0
    longas_total   = 0
    media_total    = 0.0

    if todas_sais:
        meses_todos    = [_meses_de_str(r["Tempo no time"]) for r in todas_sais]
        precoces_total = sum(1 for m in meses_todos if m < 3)
        longas_total   = sum(1 for m in meses_todos if m >= 12)
        media_total    = sum(meses_todos) / len(meses_todos)

        st.markdown("**⏱️ Perfil das saídas no período:**")
        perfil_items = [
            f"Tempo médio no time: **{media_total:.1f} meses**",
            f"Saídas precoces (< 3 meses): **{precoces_total}** "
            f"({precoces_total / total_sai * 100:.0f}% do total) — "
            "referência DSA: taxa acima de 30% indica problema de onboarding",
            f"Veteranas que saíram (12+ meses): **{longas_total}** — "
            "cada uma representa até 200% do custo de substituição (Gallup, 2023)",
        ]
        for item in perfil_items:
            st.markdown(f"- {item}")

    # ── Benchmark do setor ────────────────────────────────────────────────────
    st.markdown("**🏭 Benchmarks do setor para comparação:**")
    benchmarks = [
        "**Venda direta no Brasil (ABEVD, 2025):** 3 milhões de revendedoras ativas, "
        "crescimento de 6,3% em 2024, movimentando R$ 50 bilhões. "
        "Alta rotatividade é característica estrutural do setor — o diferencial está em quem retém melhor.",
        "**Rotatividade saudável (Gallup, 2023):** < 10% ao ano para qualquer setor. "
        "Para equipes de vendas diretas, taxas de 20-40% ao ano são comuns — "
        "o objetivo é ficar abaixo da média do próprio histórico.",
        "**Equipes comerciais (Xactly Corp, 2024):** média de 35% de rotatividade anual, "
        "a mais alta de todas as áreas nas empresas.",
        "**Custo de rotatividade no Brasil (Robert Half / DIEESE, 2024):** "
        "a rotatividade no país cresceu 54% em 2024. Substituir um profissional custa "
        "entre 50% e 200% da remuneração anual equivalente.",
        "**Impacto financeiro da retenção (HBR):** aumentar a taxa de retenção em apenas 5% "
        "pode gerar mais de 25% de aumento no lucro operacional.",
    ]
    for b in benchmarks:
        st.markdown(f"- {b}")

    # ── Recomendações baseadas nos dados ──────────────────────────────────────
    st.markdown("**🎯 Recomendações baseadas nos seus dados:**")
    recomendacoes = []

    if total_sai > 0 and precoces_total / total_sai >= 0.30:
        recomendacoes.append(
            "**Programa de integração nos primeiros 30 dias:** "
            "contato semanal nos primeiros 4 ciclos, meta de primeira venda na semana 1. "
            "DSA aponta que distribuidores que vendem no 1º ciclo têm 3x mais chance de permanecer."
        )

    if max_neg_consecutivos >= 2:
        recomendacoes.append(
            "**Revisão da estratégia de captação:** o perfil de quem está sendo recrutado "
            "pode não estar alinhado com o perfil de quem permanece. "
            "Comparar características das que ficam vs. as que saem precocemente."
        )

    recomendacoes.append(
        "**Monitoramento mensal do saldo líquido:** acompanhar essa métrica todo mês "
        "é mais relevante do que acompanhar só entradas. Um time de 100 com saldo +5 "
        "é mais saudável do que um de 200 com saldo −10."
    )

    recomendacoes.append(
        "**Estratégia de reativação de inativos:** ex-revendedoras têm custo de reconversão "
        "2-3x menor do que novas. Manter contato com as que saíram há menos de 12 meses "
        "pode ser a fonte mais barata de crescimento."
    )

    for r in recomendacoes:
        st.markdown(f"- {r}")


# ── Render ─────────────────────────────────────────────────────────────────────

def render():
    _hoje    = date.today()
    _ANO     = _hoje.year
    _MES_INI = 1
    _MES_FIM = _hoje.month

    st.title("📊 Entradas e Saídas de Revendedoras")
    _mes_ini_label = _MESES[_MES_INI - 1]
    _mes_fim_label = _MESES[_MES_FIM - 1]
    st.caption(
        f"{_mes_ini_label} a {_mes_fim_label} de {_ANO} · "
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

    entradas, saidas = _calcular(todos_pedidos, _ANO, _MES_INI, _MES_FIM)

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
    _rng = range(_MES_INI, _MES_FIM + 1)
    _abrev_ini = _MESES[_MES_INI - 1][:3]
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
    tabs = st.tabs([_MESES[m - 1] for m in range(_MES_INI, _MES_FIM + 1)])

    dados_para_periodo = []

    for tab, mes in zip(tabs, range(_MES_INI, _MES_FIM + 1)):
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

            dados_para_periodo.append({
                "mes": mes, "nome": _MESES[mes - 1],
                "n_ent": n_ent, "n_sai": n_sai, "saldo": saldo_m, "sais": sais,
            })

    # ── Análise consolidada do período ─────────────────────────────────────────
    if dados_para_periodo:
        _render_insights_periodo(dados_para_periodo)
