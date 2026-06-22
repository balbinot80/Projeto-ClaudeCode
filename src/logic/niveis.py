from datetime import date
import pandas as pd
from src.logic.revendedoras import parse_date, calcular_competencia

# ── Definição dos níveis ──────────────────────────────────────────────────────

NIVEIS_PECAS = [
    ("Diamante", 80,  500),
    ("Ouro",     55,  79),
    ("Pérola",   40,  54),
]

MINIMO_UNIVERSAL = 300.0   # mínimo de permanência válido para todos os níveis

MINIMO_VENDAS = {
    "Diamante": 2500.0,
    "Ouro":     1000.0,
    "Pérola":   MINIMO_UNIVERSAL,
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

LIMIAR_SUBIDA = {
    "Pérola":   1000.0,
    "Ouro":     2500.0,
}

ICONE_NIVEL = {
    "Diamante":  "💎",
    "Ouro":      "🥇",
    "Pérola":    "🔮",
    "Sem nível": "—",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def nivel_por_pecas(qtd) -> str:
    try:
        qtd = int(float(qtd or 0))
    except (TypeError, ValueError):
        return "Sem nível"
    for nome, mn, mx in NIVEIS_PECAS:
        if mn <= qtd <= mx:
            return nome
    return "Sem nível"


def _qtd_original(p: dict) -> int:
    """
    Quantidade original de peças do pedido (total consignado na maleta).

    Pedidos ABERTOS:  `quantidade` = total consignado (correto).
    Pedidos BAIXADOS: `quantidade_antes_baixa` = total que foi na maleta (campo correto).
                      `quantidade` = apenas o que foi efetivamente vendido (errado para nível).
    """
    if p.get("status") == "Baixado":
        qab = p.get("quantidade_antes_baixa")
        if qab is not None:
            try:
                iv = int(float(qab))
                if iv > 0:
                    return iv
            except (ValueError, TypeError):
                pass
    return int(float(p.get("quantidade") or 0))


def _mes_n_atras(mes: int, ano: int, n: int):
    for _ in range(n):
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1
    return mes, ano


def _mes_a_frente(mes: int, ano: int, n: int = 1):
    for _ in range(n):
        mes += 1
        if mes == 13:
            mes = 1
            ano += 1
    return mes, ano


def nivel_por_vendas(valor: float) -> str:
    """
    Para pedidos já fechados (baixados): inferimos o nível alcançado pelo valor vendido,
    pois a quantidade original consignada não é guardada pela API após o fechamento.
    """
    if valor >= 2500.0:
        return "Diamante"
    if valor >= 1000.0:
        return "Ouro"
    if valor > 0:
        return "Pérola"
    return "Sem nível"


def _status_nivel(nivel: str, vendas: float) -> str:
    if nivel == "Sem nível":
        return "—"
    minimo = MINIMO_VENDAS.get(nivel, 0)
    if vendas == 0:
        return "🔴 Sem vendas"
    if vendas < minimo:
        return "⚠️ Abaixo do mínimo"
    return "✅ Atingiu o mínimo"


# ── Classificação mensal ──────────────────────────────────────────────────────

def classificar_revendedoras(pedidos: list, mes: int, ano: int) -> pd.DataFrame:
    """
    Retorna UMA linha por revendedora por tipo (Baixado / Em aberto) no mês.
    Quando há múltiplos pedidos do mesmo tipo para a mesma revendedora:
      - Nível definido pelo pedido com MAIS PEÇAS
      - Vendas somadas de todos os pedidos
    """
    # agg_map[(rid, tipo)] → linha agregada
    agg_map: dict = {}

    for p in pedidos:
        rid    = p.get("fk_revendedor_id")
        status = p.get("status", "")
        if not rid or status not in ("Baixado", "Aberto"):
            continue

        comprador  = p.get("comprador") or {}
        nome       = comprador.get("nome") or f"Rev {rid}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"

        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if not (d and d.month == mes and d.year == ano):
                continue
            vendas = float(p.get("valor_total") or 0)
            tipo   = "🔒 Baixado (fechado)"
            qtd    = _qtd_original(p)
        else:
            d = parse_date(p.get("data_acerto"))
            if not (d and d.month == mes and d.year == ano):
                continue
            vendas = float(p.get("valor_pre_baixa") or 0)
            tipo   = "🔓 Em aberto"
            qtd    = int(float(p.get("quantidade") or 0))

        key = (rid, tipo)
        if key not in agg_map:
            nivel = nivel_por_pecas(qtd)
            agg_map[key] = {
                "fk_revendedor_id": rid,
                "Nome":             nome,
                "Supervisor":       supervisor,
                "Tipo":             tipo,
                "Nível":            nivel,
                "Peças pedido":     qtd,
                "Vendas mês":       round(vendas, 2),
            }
        else:
            entry = agg_map[key]
            # Nível sempre definido pelo pedido com mais peças
            if qtd > entry["Peças pedido"]:
                entry["Peças pedido"] = qtd
                entry["Nível"]        = nivel_por_pecas(qtd)
            # Vendas somadas
            entry["Vendas mês"] = round(entry["Vendas mês"] + vendas, 2)

    if not agg_map:
        return pd.DataFrame()

    rows = []
    for entry in agg_map.values():
        nivel  = entry["Nível"]
        vendas = entry["Vendas mês"]
        rows.append({
            **entry,
            "Mínimo nível": MINIMO_VENDAS.get(nivel, 0),
            "Status":       _status_nivel(nivel, vendas),
        })

    _ord_tipo  = {"🔒 Baixado (fechado)": 0, "🔓 Em aberto": 1}
    _ord_nivel = {"Diamante": 0, "Ouro": 1, "Pérola": 2, "Sem nível": 3}

    df = pd.DataFrame(rows)
    df["_ot"] = df["Tipo"].map(_ord_tipo).fillna(2)
    df["_on"] = df["Nível"].map(_ord_nivel).fillna(4)
    return (
        df.sort_values(["_ot", "_on", "Vendas mês"], ascending=[True, True, False])
        .drop(columns=["_ot", "_on"])
        .reset_index(drop=True)
    )


# ── Alerta: potencial de subida ───────────────────────────────────────────────

def alertas_subida(pedidos: list, mes: int, ano: int, pct: float = 0.75) -> pd.DataFrame:
    """
    Revendedoras com vendas >= pct × limiar do próximo nível.
    Inclui quem já ultrapassou o limiar (coluna Situação distingue).
    Vendas calculadas pelo padrão de competência via calcular_competencia.
    """
    df_comp, _ = calcular_competencia(pedidos, mes, ano)
    if df_comp.empty:
        return pd.DataFrame()

    # Revendedoras com pelo menos um pedido em aberto (ativa na equipe)
    revs_ativas = {
        p["fk_revendedor_id"]
        for p in pedidos
        if p.get("status") == "Aberto" and p.get("fk_revendedor_id")
    }

    # Monta lookup nível por revendedora — Aberto tem prioridade sobre Baixado
    nivel_map: dict = {}
    for p in pedidos:
        rid    = p.get("fk_revendedor_id")
        status = p.get("status", "")
        if not rid or status not in ("Aberto", "Baixado"):
            continue

        campo_data = "data_acerto" if status == "Aberto" else "data_baixa"
        d = parse_date(p.get(campo_data))
        if not (d and d.month == mes and d.year == ano):
            continue

        # Aberto sobrepõe Baixado se já houver entrada
        if rid in nivel_map and nivel_map[rid]["status"] == "Aberto":
            continue

        comprador  = p.get("comprador") or {}
        nome       = comprador.get("nome") or f"Rev {rid}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"
        qtd        = _qtd_original(p)
        nivel_map[rid] = {
            "nivel":      nivel_por_pecas(qtd),
            "nome":       nome,
            "supervisor": supervisor,
            "status":     status,
        }

    rows = []
    for _, row in df_comp.iterrows():
        rid    = row["fk_revendedor_id"]
        info   = nivel_map.get(rid)
        if not info:
            continue

        nivel   = info["nivel"]
        proximo = NIVEL_SUPERIOR.get(nivel)
        limiar  = LIMIAR_SUBIDA.get(nivel)
        if not proximo or not limiar:
            continue

        vendas = float(row["Total"])
        if vendas >= limiar * pct:
            situacao = "✅ Já atingiu a meta" if vendas >= limiar else "🔜 Próxima de subir"
            rows.append({
                "Pedido":      info["status"],
                "Equipe":      "Ativa" if rid in revs_ativas else "Saiu",
                "Nome":        info["nome"],
                "Supervisor":  info["supervisor"],
                "Nível atual": nivel,
                "Próx. nível": proximo,
                "Vendas mês":  round(vendas, 2),
                "Meta subida": limiar,
                "Falta":       round(max(limiar - vendas, 0), 2),
                "Situação":    situacao,
            })

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    df_out["_ord_s"] = df_out["Situação"].map({"✅ Já atingiu a meta": 0, "🔜 Próxima de subir": 1})
    df_out["_ord_p"] = df_out["Pedido"].map({"Aberto": 0, "Baixado": 1})
    return (
        df_out.sort_values(["_ord_p", "_ord_s", "Vendas mês"], ascending=[True, True, False])
        .drop(columns=["_ord_s", "_ord_p"])
        .reset_index(drop=True)
    )


# ── Alerta: risco de rebaixamento ─────────────────────────────────────────────

def alertas_rebaixamento(pedidos: list, mes: int, ano: int) -> pd.DataFrame:
    """
    Analisa os 3 meses: M-2, M-1 e M0 (mês atual).
    - M-2 e M-1: apenas baixados (meses encerrados) via calcular_competencia
    - M0: baixados + pré-baixa (mês corrente) via calcular_competencia

    Projeção para M+1:
      🔴 Risco de rebaixamento  — M-1 E M0 abaixo do mínimo (2 consecutivos recentes)
      🟠 Atenção                — M-2 E M-1 abaixo (mas M0 ainda em curso)
      🟡 Monitorar              — apenas M0 abaixo
    Só exibe revendedoras com ao menos 1 mês abaixo do mínimo.
    """
    m1, y1 = _mes_n_atras(mes, ano, 1)
    m2, y2 = _mes_n_atras(mes, ano, 2)
    mP, yP = _mes_a_frente(mes, ano, 1)

    df0, _ = calcular_competencia(pedidos, mes, ano)
    df1, _ = calcular_competencia(pedidos, m1, y1)
    df2, _ = calcular_competencia(pedidos, m2, y2)

    # Revendedoras com pelo menos um pedido em aberto (ativa na equipe)
    revs_ativas = {
        p["fk_revendedor_id"]
        for p in pedidos
        if p.get("status") == "Aberto" and p.get("fk_revendedor_id")
    }

    # Nível atual: Aberto tem prioridade; Baixado do mês como fallback
    nivel_map: dict = {}
    for p in pedidos:
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        status = p.get("status", "")
        if status == "Aberto":
            if rid not in nivel_map:
                comprador = p.get("comprador") or {}
                qtd = _qtd_original(p)
                nivel_map[rid] = {
                    "nivel":      nivel_por_pecas(qtd),
                    "nome":       comprador.get("nome") or f"Rev {rid}",
                    "supervisor": p.get("supervisor_nome") or "Sem supervisora",
                    "status":     "Aberto",
                }

    # Fallback: baixados do mês atual
    for p in pedidos:
        rid = p.get("fk_revendedor_id")
        if not rid or rid in nivel_map or p.get("status") != "Baixado":
            continue
        d = parse_date(p.get("data_baixa"))
        if d and d.month == mes and d.year == ano:
            comprador = p.get("comprador") or {}
            qtd = _qtd_original(p)
            nivel_map[rid] = {
                "nivel":      nivel_por_pecas(qtd),
                "nome":       comprador.get("nome") or f"Rev {rid}",
                "supervisor": p.get("supervisor_nome") or "Sem supervisora",
                "status":     "Baixado",
            }

    def _total(df, rid):
        if df.empty:
            return None
        r = df[df["fk_revendedor_id"] == rid]
        return float(r["Total"].sum()) if not r.empty else None

    rows = []
    for rid, info in nivel_map.items():
        nivel  = info["nivel"]
        if nivel == "Sem nível":
            continue
        minimo = MINIMO_VENDAS.get(nivel, 0)

        v0 = _total(df0, rid)
        v1 = _total(df1, rid)
        v2 = _total(df2, rid)

        # Só exibe se houve algum mês abaixo do mínimo
        abaixo = [v for v in (v0, v1, v2) if v is not None and v < minimo]
        if not abaixo:
            continue

        # Projeção para o próximo mês
        m1_abaixo = (v1 is not None and v1 < minimo)
        m0_abaixo = (v0 is not None and v0 < minimo)
        m2_abaixo = (v2 is not None and v2 < minimo)

        if m1_abaixo and m0_abaixo:
            projecao = "🔴 Risco de rebaixamento"
        elif m2_abaixo and m1_abaixo:
            projecao = "🟠 Atenção — tendência negativa"
        else:
            projecao = "🟡 Monitorar"

        def _fmt_v(v):
            return round(v, 2) if v is not None else "—"

        rows.append({
            "Pedido":                  info["status"],
            "Equipe":                  "Ativa" if rid in revs_ativas else "Saiu",
            "Nome":                    info["nome"],
            "Supervisor":              info["supervisor"],
            "Nível atual":             nivel,
            f"Vendas {m2:02d}/{y2}":   _fmt_v(v2),
            f"Vendas {m1:02d}/{y1}":   _fmt_v(v1),
            f"Vendas {mes:02d}/{ano}":  _fmt_v(v0),
            "Mínimo do nível":         minimo,
            f"Projeção {mP:02d}/{yP}":  projecao,
            "Rebaixa para":            NIVEL_ANTERIOR.get(nivel) or "—",
        })

    if not rows:
        return pd.DataFrame()

    _ord_proj = {
        "🔴 Risco de rebaixamento":        0,
        "🟠 Atenção — tendência negativa": 1,
        "🟡 Monitorar":                    2,
    }
    df_out = pd.DataFrame(rows)
    proj_col = [c for c in df_out.columns if c.startswith("Projeção")][0]
    df_out["_ord_proj"] = df_out[proj_col].map(_ord_proj).fillna(3)
    df_out["_ord_ped"]  = df_out["Pedido"].map({"Aberto": 0, "Baixado": 1})
    return (
        df_out.sort_values(["_ord_ped", "_ord_proj"])
        .drop(columns=["_ord_proj", "_ord_ped"])
        .reset_index(drop=True)
    )
