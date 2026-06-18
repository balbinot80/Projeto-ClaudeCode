from datetime import date, datetime, timedelta
import pandas as pd

MINIMO_REV = 300.0  # R$ mínimo mensal para permanência na equipe


def parse_date(s):
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except Exception:
        return None


def meses_disponiveis(n: int = 7, futuros: int = 1):
    """
    Retorna lista de (ano, mes) com `futuros` meses à frente + mês atual + últimos n-1 meses.
    Ordem: mais recente (futuro) primeiro.
    """
    hoje = date.today()
    meses = []

    # Meses futuros
    for i in range(futuros, 0, -1):
        m = hoje.month + i
        y = hoje.year
        while m > 12:
            m -= 12
            y += 1
        if (y, m) not in meses:
            meses.append((y, m))

    # Mês atual + passados
    for i in range(n):
        m = hoje.month - i
        y = hoje.year
        while m <= 0:
            m += 12
            y -= 1
        if (y, m) not in meses:
            meses.append((y, m))

    return meses


def calcular_competencia(pedidos: list, mes: int, ano: int):
    """
    Regras de competência:
    - Baixados com data_baixa no mês → soma valor_total
    - Abertos com data_acerto no mês → soma valor_pre_baixa

    Retorna (df_resumo_por_revendedora, df_detalhe_por_pedido).
    """
    detalhe = []

    for p in pedidos:
        rev_id = p.get("fk_revendedor_id")
        if not rev_id:
            continue

        comprador = p.get("comprador") or {}
        nome = comprador.get("nome") or f"Rev {rev_id}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"
        status = p.get("status", "")
        cod = p.get("codigo_pedido")

        baixado = 0.0
        pre_baixa = 0.0
        data_ref = None

        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if d and d.month == mes and d.year == ano:
                baixado = float(p.get("valor_total") or 0)
                data_ref = d
        elif status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if d and d.month == mes and d.year == ano:
                pre_baixa = float(p.get("valor_pre_baixa") or 0)
                data_ref = d

        if data_ref is not None:
            detalhe.append({
                "fk_revendedor_id": rev_id,
                "Nome": nome,
                "Supervisor": supervisor,
                "Status": status,
                "Pedido": cod,
                "Baixado": baixado,
                "Pré-baixa": pre_baixa,
                "Total": baixado + pre_baixa,
                "Data ref.": data_ref.strftime("%d/%m/%y"),
                "Valor pedido": float(p.get("valor_total") or 0),
            })

    if not detalhe:
        return pd.DataFrame(), pd.DataFrame()

    df_det = pd.DataFrame(detalhe)

    df_res = (
        df_det.groupby(["fk_revendedor_id", "Nome", "Supervisor"], as_index=False)
        .agg(
            Baixado=("Baixado", "sum"),
            Pre_baixa=("Pré-baixa", "sum"),
            Total=("Total", "sum"),
            Pedidos=("Pedido", "count"),
        )
        .rename(columns={"Pre_baixa": "Pré-baixa"})
    )

    def _risco(row):
        t = row["Total"]
        if t == 0:
            return "🔴 Sem vendas"
        if t < MINIMO_REV:
            return "🟡 Abaixo do mínimo"
        return "🟢 OK"

    df_res["Risco"] = df_res.apply(_risco, axis=1)
    df_res = df_res.sort_values(["Supervisor", "Total"], ascending=[True, False]).reset_index(drop=True)
    return df_res, df_det


def pedidos_abertos_sem_prebaixa(pedidos: list, mes: int, ano: int) -> pd.DataFrame:
    """Pedidos abertos com acerto no mês e pré-baixa = R$0."""
    rows = []
    for p in pedidos:
        if p.get("status") != "Aberto":
            continue
        d = parse_date(p.get("data_acerto"))
        if not (d and d.month == mes and d.year == ano):
            continue
        pb = float(p.get("valor_pre_baixa") or 0)
        if pb > 0:
            continue
        comprador = p.get("comprador") or {}
        rows.append({
            "Nome": comprador.get("nome") or f"Rev {p.get('fk_revendedor_id')}",
            "Supervisor": p.get("supervisor_nome") or "Sem supervisora",
            "Pedido": p.get("codigo_pedido"),
            "Valor pedido": float(p.get("valor_total") or 0),
            "Acerto": parse_date(p.get("data_acerto")).strftime("%d/%m/%y") if parse_date(p.get("data_acerto")) else "-",
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _media_vendas_3meses(pedidos: list, hoje: date) -> dict:
    """
    Média mensal de vendas (baixados) dos 3 meses anteriores ao mês atual,
    por revendedora. Meses sem venda contam como R$0 na média.
    Retorna {fk_revendedor_id: media_mensal}.
    """
    # Determina os 3 meses anteriores
    mes, ano = hoje.month, hoje.year
    meses_ref = []
    for _ in range(3):
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
        meses_ref.append((ano, mes))

    corte_de  = date(meses_ref[-1][0], meses_ref[-1][1], 1)
    corte_ate = date(hoje.year, hoje.month, 1)  # exclui mês atual

    from collections import defaultdict
    totais: dict = defaultdict(float)

    for p in pedidos:
        if p.get("status") != "Baixado":
            continue
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        d = parse_date(p.get("data_baixa"))
        if not d or d < corte_de or d >= corte_ate:
            continue
        totais[rid] += float(p.get("valor_total") or 0)

    return {rid: round(total / 3, 2) for rid, total in totais.items()}


def analise_periodo(pedidos: list, dias: int, hoje: date = None, dias_min: int = 0) -> pd.DataFrame:
    """
    Pedidos abertos criados num intervalo exclusivo de dias:
      d_criacao entre (hoje - dias) e (hoje - dias_min).
    Ritmo de referência = média mensal de vendas dos últimos 3 meses da revendedora.
    Para novas revendedoras sem histórico, usa MINIMO_REV como referência.
    """
    if hoje is None:
        hoje = date.today()

    media_3m  = _media_vendas_3meses(pedidos, hoje)
    corte_ate = hoje - timedelta(days=dias_min)
    corte_de  = hoje - timedelta(days=dias)
    rows = []

    for p in pedidos:
        if p.get("status") != "Aberto":
            continue

        d_criacao = parse_date(p.get("data_criacao"))
        if not d_criacao or d_criacao < corte_de or d_criacao > corte_ate:
            continue

        rid      = p.get("fk_revendedor_id")
        d_acerto = parse_date(p.get("data_acerto"))
        comprador = p.get("comprador") or {}
        nome      = comprador.get("nome") or f"Rev {rid}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"

        valor_pedido   = float(p.get("valor_total") or 0)
        pre_baixa      = float(p.get("valor_pre_baixa") or 0)
        dias_decorridos = max((hoje - d_criacao).days, 1)

        # Ritmo = média mensal dos últimos 3 meses; fallback para MINIMO_REV se sem histórico
        ritmo_esperado = media_3m.get(rid) or MINIMO_REV
        pct_ritmo      = round(pre_baixa / max(ritmo_esperado, 0.01) * 100, 1)

        if pre_baixa == 0:
            risco = "🔴 Sem vendas"
        elif pre_baixa < MINIMO_REV:
            risco = "🟠 Abaixo do mínimo"
        elif pre_baixa < ritmo_esperado * 0.9:
            risco = "🟡 Abaixo do ritmo"
        else:
            risco = "🟢 No ritmo"

        rows.append({
            "Pedido":           p.get("codigo_pedido", ""),
            "Nome":             nome,
            "Supervisor":       supervisor,
            "Criado":           d_criacao.strftime("%d/%m/%y"),
            "Acerto":           d_acerto.strftime("%d/%m/%y") if d_acerto else "-",
            "Dias do pedido":   dias_decorridos,
            "Pré-baixa":        round(pre_baixa, 2),
            "Ritmo ref. (3M)":  round(ritmo_esperado, 2),
            "% do ritmo":       pct_ritmo,
            "Valor pedido":     valor_pedido,
            "Risco":            risco,
        })

    if not rows:
        return pd.DataFrame()

    _ord = {"🔴 Sem vendas": 0, "🟠 Abaixo do mínimo": 1, "🟡 Abaixo do ritmo": 2, "🟢 No ritmo": 3}
    df = pd.DataFrame(rows)
    df["_ord"] = df["Risco"].map(_ord).fillna(4)
    return df.sort_values(["_ord", "Pré-baixa"]).drop(columns="_ord").reset_index(drop=True)
