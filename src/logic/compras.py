from datetime import datetime, timedelta
import pandas as pd


def calcular_velocidade_vendas(vendas: list, dias: int = 90) -> pd.DataFrame:
    """
    Calcula quantas unidades de cada produto foram vendidas por dia
    no período informado.
    """
    if not vendas:
        return pd.DataFrame(columns=["produto_id", "descricao", "total_vendido", "media_diaria"])

    corte = datetime.now() - timedelta(days=dias)
    rows = []

    for venda in vendas:
        data_venda_str = venda.get("data_venda") or venda.get("data_criacao") or ""
        try:
            data_venda = datetime.fromisoformat(data_venda_str[:19])
        except (ValueError, TypeError):
            continue

        if data_venda < corte:
            continue

        for item in venda.get("itens", []):
            rows.append({
                "produto_id": item.get("fk_produto_id") or item.get("produto_id"),
                "descricao": item.get("descricao", ""),
                "quantidade": float(item.get("quantidade", 0)),
            })

    if not rows:
        return pd.DataFrame(columns=["produto_id", "descricao", "total_vendido", "media_diaria"])

    df = pd.DataFrame(rows)
    df = df.groupby(["produto_id", "descricao"], as_index=False).agg(total_vendido=("quantidade", "sum"))
    df["media_diaria"] = df["total_vendido"] / dias
    return df.sort_values("total_vendido", ascending=False)


def sugerir_compras(produtos: list, vendas: list, dias_cobertura: int = 60, dias_historico: int = 90) -> pd.DataFrame:
    """
    Gera sugestão de compras para cada produto.
    - dias_cobertura: quantos dias de estoque queremos manter
    - dias_historico: período para calcular velocidade de vendas
    """
    velocidade = calcular_velocidade_vendas(vendas, dias=dias_historico)
    vel_map = dict(zip(velocidade["produto_id"], velocidade["media_diaria"]))

    rows = []
    for p in produtos:
        pid = p.get("id")
        estoque_atual = float(p.get("quantidade", 0))
        estoque_min = float(p.get("estoque_minimo") or 0)
        estoque_max = float(p.get("estoque_maximo") or 0)
        media_diaria = vel_map.get(pid, 0)

        dias_restantes = (estoque_atual / media_diaria) if media_diaria > 0 else 999
        estoque_alvo = media_diaria * dias_cobertura
        quantidade_sugerida = max(0, estoque_alvo - estoque_atual)

        if estoque_max > 0:
            quantidade_sugerida = min(quantidade_sugerida, estoque_max - estoque_atual)

        if estoque_atual <= estoque_min:
            status = "🔴 Crítico"
        elif dias_restantes < 30:
            status = "🟡 Atenção"
        elif quantidade_sugerida > 0:
            status = "🟢 Planejar"
        else:
            status = "✅ OK"

        rows.append({
            "ID": pid,
            "Produto": p.get("descricao", ""),
            "Estoque Atual": int(estoque_atual),
            "Mínimo": int(estoque_min),
            "Máximo": int(estoque_max),
            "Vendas/dia": round(media_diaria, 2),
            "Dias restantes": round(dias_restantes, 0) if dias_restantes < 999 else "∞",
            "Sugestão de compra": int(quantidade_sugerida),
            "Status": status,
        })

    df = pd.DataFrame(rows)
    ordem_status = {"🔴 Crítico": 0, "🟡 Atenção": 1, "🟢 Planejar": 2, "✅ OK": 3}
    df["_ordem"] = df["Status"].map(ordem_status)
    df = df.sort_values("_ordem").drop(columns="_ordem")
    return df
