from datetime import date
import pandas as pd
from src.logic.revendedoras import parse_date, calcular_competencia

# ── Definição dos níveis ──────────────────────────────────────────────────────

NIVEIS_PECAS = [           # (nome, min_pecas, max_pecas) — ordem decrescente
    ("Diamante", 76,  500),
    ("Ouro",     55,  75),
    ("Pérola",   40,  54),
]

MINIMO_VENDAS = {          # venda mínima mensal para MANTER o nível
    "Diamante": 2500.0,
    "Ouro":     1000.0,
    "Pérola":   0.01,      # qualquer venda simbólica mantém Pérola
}

NIVEL_ANTERIOR = {
    "Diamante": "Ouro",
    "Ouro":     "Pérola",
    "Pérola":   None,
}

NIVEL_SUPERIOR = {
    "Pérola":   "Ouro",
    "Ouro":     "Diamante",
    "Diamante": None,
}

LIMIAR_SUBIDA = {          # vendas mínimas para SUBIR para o próximo nível
    "Pérola":   1000.0,
    "Ouro":     2500.0,
}

ICONE_NIVEL = {
    "Diamante": "💎",
    "Ouro":     "🥇",
    "Pérola":   "🔮",
    "Sem nível": "—",
}


# ── Helpers internos ──────────────────────────────────────────────────────────

def nivel_por_pecas(qtd) -> str:
    try:
        qtd = int(float(qtd or 0))
    except (TypeError, ValueError):
        return "Sem nível"
    for nome, mn, mx in NIVEIS_PECAS:
        if mn <= qtd <= mx:
            return nome
    return "Sem nível"


def _mes_n_atras(mes: int, ano: int, n: int):
    for _ in range(n):
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1
    return mes, ano


def _nivel_atual_por_revendedora(pedidos: list) -> dict:
    """
    Retorna dict {fk_revendedor_id: info} baseado no pedido ABERTO mais recente
    de cada revendedora. Campo `quantidade` = total de peças consignadas.
    """
    mais_recente: dict = {}
    for p in pedidos:
        if p.get("status") != "Aberto":
            continue
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        d = parse_date(p.get("data_criacao"))
        if not d:
            continue
        if rid not in mais_recente or d > mais_recente[rid]["data"]:
            comprador = p.get("comprador") or {}
            nome = comprador.get("nome") or f"Rev {rid}"
            qtd = int(float(p.get("quantidade") or 0))
            mais_recente[rid] = {
                "data":       d,
                "nivel":      nivel_por_pecas(qtd),
                "pecas":      qtd,
                "nome":       nome,
                "supervisor": p.get("supervisor_nome") or "Sem supervisora",
            }
    return mais_recente


# ── Funções públicas ──────────────────────────────────────────────────────────

def classificar_revendedoras(pedidos: list, mes: int, ano: int) -> pd.DataFrame:
    """
    Classifica cada revendedora com pedido aberto:
    - Nível pelas peças do pedido (campo `quantidade`)
    - Vendas = pré-baixa dos pedidos com data_acerto no mês
    - Status: mantendo / abaixo do mínimo / sem vendas
    """
    niveis_map = _nivel_atual_por_revendedora(pedidos)

    vendas_mes: dict = {}
    for p in pedidos:
        if p.get("status") != "Aberto":
            continue
        d = parse_date(p.get("data_acerto"))
        if not (d and d.month == mes and d.year == ano):
            continue
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        vendas_mes[rid] = vendas_mes.get(rid, 0) + float(p.get("valor_pre_baixa") or 0)

    rows = []
    for rid, info in niveis_map.items():
        vendas = vendas_mes.get(rid, 0)
        nivel = info["nivel"]
        minimo = MINIMO_VENDAS.get(nivel, 0)

        if nivel == "Sem nível":
            status = "—"
        elif vendas == 0:
            status = "🔴 Sem vendas"
        elif vendas < minimo:
            status = "⚠️ Abaixo do mínimo"
        else:
            status = "✅ Mantendo nível"

        rows.append({
            "fk_revendedor_id": rid,
            "Nome":             info["nome"],
            "Supervisor":       info["supervisor"],
            "Nível":            nivel,
            "Peças pedido":     info["pecas"],
            "Vendas mês":       round(vendas, 2),
            "Mínimo nível":     minimo,
            "Status":           status,
        })

    if not rows:
        return pd.DataFrame()

    _ord = {"Diamante": 0, "Ouro": 1, "Pérola": 2, "Sem nível": 3}
    df = pd.DataFrame(rows)
    df["_ord"] = df["Nível"].map(_ord).fillna(4)
    return (
        df.sort_values(["_ord", "Vendas mês"], ascending=[True, False])
        .drop(columns="_ord")
        .reset_index(drop=True)
    )


def alertas_rebaixamento(pedidos: list, mes: int, ano: int) -> pd.DataFrame:
    """
    Revendedoras abaixo do mínimo do seu nível nos 2 meses anteriores consecutivos
    E que tinham pedidos ativos nesses meses (apareceram na competência dos 2 meses).
    """
    m1, y1 = _mes_n_atras(mes, ano, 1)
    m2, y2 = _mes_n_atras(mes, ano, 2)

    df1, _ = calcular_competencia(pedidos, m1, y1)
    df2, _ = calcular_competencia(pedidos, m2, y2)

    niveis_map = _nivel_atual_por_revendedora(pedidos)
    if not niveis_map:
        return pd.DataFrame()

    rows = []
    for rid, info in niveis_map.items():
        nivel = info["nivel"]
        if nivel == "Sem nível":
            continue
        minimo = MINIMO_VENDAS.get(nivel, 0)

        r1 = df1[df1["fk_revendedor_id"] == rid] if not df1.empty else pd.DataFrame()
        r2 = df2[df2["fk_revendedor_id"] == rid] if not df2.empty else pd.DataFrame()

        # Só alerta se a revendedora apareceu nos 2 meses (tinha pedido ativo)
        if r1.empty or r2.empty:
            continue

        v1 = float(r1["Total"].sum())
        v2 = float(r2["Total"].sum())

        if v1 < minimo and v2 < minimo:
            anterior = NIVEL_ANTERIOR.get(nivel)
            rows.append({
                "Nome":             info["nome"],
                "Supervisor":       info["supervisor"],
                "Nível atual":      nivel,
                f"Vendas {m2:02d}/{y2}": round(v2, 2),
                f"Vendas {m1:02d}/{y1}": round(v1, 2),
                "Mínimo do nível":  minimo,
                "Rebaixa para":     anterior or "—",
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def alertas_subida(pedidos: list, mes: int, ano: int, pct: float = 0.75) -> pd.DataFrame:
    """
    Revendedoras com vendas entre pct*limiar e limiar do próximo nível.
    Padrão: 75% do limiar já é potencial de subida.
    """
    df = classificar_revendedoras(pedidos, mes, ano)
    if df.empty:
        return pd.DataFrame()

    rows = []
    for _, rev in df.iterrows():
        nivel = rev["Nível"]
        proximo = NIVEL_SUPERIOR.get(nivel)
        if not proximo:
            continue
        limiar = LIMIAR_SUBIDA.get(nivel)
        if not limiar:
            continue
        vendas = rev["Vendas mês"]
        if limiar * pct <= vendas < limiar:
            rows.append({
                "Nome":        rev["Nome"],
                "Supervisor":  rev["Supervisor"],
                "Nível atual": nivel,
                "Próx. nível": proximo,
                "Vendas mês":  vendas,
                "Meta subida": limiar,
                "Falta":       round(limiar - vendas, 2),
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
