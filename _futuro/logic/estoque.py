import pandas as pd

_KEYWORDS = [
    ("Brinco",       ["brinco"]),
    ("Colar",        ["colar", "gargantilha", "corrente"]),
    ("Choker",       ["choker"]),
    ("Pulseira",     ["pulseira", "bracelete"]),
    ("Tornozeleira", ["tornozeleira"]),
    ("Anel",         ["anel", "aliança"]),
    ("Pingente",     ["pingente"]),
    ("Conjunto",     ["conjunto", "kit"]),
    ("Ponto de Luz", ["ponto de luz"]),
    ("Berloque",     ["berloque"]),
]


def inferir_categoria(descricao: str) -> str:
    desc = (descricao or "").lower()
    for nome, keys in _KEYWORDS:
        if any(k in desc for k in keys):
            return nome
    return "Outros"


def nome_categoria(cat_id, categorias_map: dict, descricao: str = "") -> str:
    nome = categorias_map.get(str(cat_id), "")
    if nome:
        return nome
    if descricao:
        return inferir_categoria(descricao)
    return f"Categoria {cat_id}" if cat_id else "Sem categoria"


def montar_df_estoque(produtos: list, na_rua_map: dict, categorias_map: dict) -> pd.DataFrame:
    """
    na_rua_map: {produto_id: qtd_na_rua} obtido via get_itens_pedidos_abertos()
    """
    rows = []
    for p in produtos:
        pid = p.get("id")
        descricao = p.get("descricao", "")
        cat_id = p.get("fk_categoria_id")
        categoria = nome_categoria(cat_id, categorias_map, descricao)
        em_estoque = float(p.get("quantidade") or 0)
        na_rua = na_rua_map.get(pid, 0)
        total = em_estoque + na_rua
        estoque_min = float(p.get("estoque_minimo") or 0)
        estoque_max = float(p.get("estoque_maximo") or 0)

        if em_estoque < estoque_min and estoque_min > 0:
            alerta = "🔴 Crítico"
        elif em_estoque == 0 and na_rua > 0:
            alerta = "🟡 Só na rua"
        elif em_estoque > 0 and na_rua > 0:
            alerta = "✅ OK"
        elif em_estoque > 0:
            alerta = "✅ Em estoque"
        else:
            alerta = "⚫ Zerado"

        rows.append({
            "ID": pid,
            "Produto": descricao,
            "Categoria": categoria,
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "Total": int(total),
            "Mínimo": int(estoque_min),
            "Máximo": int(estoque_max),
            "Situação": alerta,
        })

    return pd.DataFrame(rows)
