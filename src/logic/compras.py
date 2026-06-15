from datetime import datetime, timedelta
import pandas as pd
from src.logic.estoque import nome_categoria, calcular_na_rua


def extrair_itens_vendidos(vendas: list, pedidos_baixados: list, produtos_map: dict) -> pd.DataFrame:
    """
    Consolida todos os itens vendidos (via venda e via pedidos baixados).
    produtos_map: {produto_id: {descricao, fk_categoria_id}}
    """
    rows = []

    def _adicionar(itens, data_str):
        try:
            data = datetime.fromisoformat((data_str or "")[:10])
        except (ValueError, TypeError):
            data = None
        for item in itens:
            pid = item.get("produto", {}).get("id") if isinstance(item.get("produto"), dict) else item.get("fk_produto_id")
            if not pid:
                continue
            produto_info = produtos_map.get(pid, {})
            rows.append({
                "produto_id": pid,
                "descricao": produto_info.get("descricao", f"Produto {pid}"),
                "categoria_id": produto_info.get("fk_categoria_id"),
                "quantidade": float(item.get("quantidade") or 0),
                "data": data,
            })

    for v in vendas:
        _adicionar(v.get("itens", []), v.get("data_criacao"))

    for p in pedidos_baixados:
        _adicionar(p.get("itens", []), p.get("data_baixa") or p.get("data_criacao"))

    if not rows:
        return pd.DataFrame(columns=["produto_id", "descricao", "categoria_id", "quantidade", "data"])

    return pd.DataFrame(rows)


def top_vendidos_por_categoria(itens_df: pd.DataFrame, categorias_map: dict, top_n: int = 10) -> dict:
    """
    Retorna {categoria: DataFrame com top N produtos mais vendidos}.
    """
    if itens_df.empty:
        return {}

    itens_df = itens_df.copy()
    itens_df["categoria"] = itens_df.apply(
        lambda r: nome_categoria(r["categoria_id"], categorias_map, r["descricao"]), axis=1
    )

    resultado = {}
    for cat, grupo in itens_df.groupby("categoria"):
        ranking = (
            grupo.groupby(["produto_id", "descricao"], as_index=False)
            .agg(total_vendido=("quantidade", "sum"))
            .sort_values("total_vendido", ascending=False)
            .head(top_n)
        )
        resultado[cat] = ranking

    return resultado


def sugerir_compras(produtos: list, vendas: list, pedidos_baixados: list,
                    pedidos_abertos: list, categorias_map: dict,
                    dias_cobertura: int = 60, dias_historico: int = 180) -> pd.DataFrame:
    """
    Gera sugestão de compras por categoria com base nos últimos dias_historico dias.
    """
    produtos_map = {p["id"]: p for p in produtos}
    itens_df = extrair_itens_vendidos(vendas, pedidos_baixados, produtos_map)
    na_rua_map = calcular_na_rua(pedidos_abertos)

    # Calcula velocidade de vendas por produto
    vel_map = {}
    if not itens_df.empty:
        agg = itens_df.groupby("produto_id")["quantidade"].sum()
        for pid, total in agg.items():
            vel_map[pid] = total / dias_historico

    rows = []
    for p in produtos:
        pid = p.get("id")
        cat_id = p.get("fk_categoria_id")
        categoria = nome_categoria(cat_id, categorias_map, p.get("descricao", ""))
        descricao = p.get("descricao", "")
        em_estoque = float(p.get("quantidade") or 0)
        na_rua = na_rua_map.get(pid, 0)
        estoque_min = float(p.get("estoque_minimo") or 0)
        estoque_max = float(p.get("estoque_maximo") or 0)
        media_diaria = vel_map.get(pid, 0)

        dias_restantes = (em_estoque / media_diaria) if media_diaria > 0 else 999
        estoque_alvo = media_diaria * dias_cobertura
        qtd_sugerida = max(0, estoque_alvo - em_estoque - na_rua)
        if estoque_max > 0:
            qtd_sugerida = min(qtd_sugerida, max(0, estoque_max - em_estoque - na_rua))

        # Só mostra produtos com histórico de vendas ou estoque crítico
        if media_diaria == 0 and em_estoque >= estoque_min:
            continue

        if em_estoque <= estoque_min and estoque_min > 0:
            status = "🔴 Crítico"
        elif dias_restantes < 30:
            status = "🟡 Atenção"
        elif qtd_sugerida > 0:
            status = "🟢 Planejar"
        else:
            status = "✅ OK"

        rows.append({
            "Categoria": categoria,
            "Produto": descricao,
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "Vendas/dia": round(media_diaria, 2),
            "Dias restantes": round(dias_restantes, 0) if dias_restantes < 999 else "∞",
            "Sugestão de compra": int(qtd_sugerida),
            "Status": status,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    ordem = {"🔴 Crítico": 0, "🟡 Atenção": 1, "🟢 Planejar": 2, "✅ OK": 3}
    df["_ord"] = df["Status"].map(ordem)
    return df.sort_values(["Categoria", "_ord"]).drop(columns="_ord").reset_index(drop=True)
