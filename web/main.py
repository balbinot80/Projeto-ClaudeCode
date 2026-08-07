"""
FastAPI — Aureum Dashboard
Porta 8001  /  Streamlit na 8501 (sem conflito).

Para iniciar:
    cd "Projeto ClaudeCode"
    uvicorn web.main:app --port 8001 --reload

O dashboard fica em:  http://localhost:8001
A documentação da API: http://localhost:8001/docs
"""
import sys
from pathlib import Path
from datetime import date

# Garante que src/ seja importável quando rodado da raiz do projeto
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Lógica de negócios — puro Python, sem dependência de Streamlit
from src.logic.revendedoras import calcular_competencia, parse_date
from src.logic.niveis import (
    classificar_revendedoras,
    nivel_por_pecas,
    MINIMO_VENDAS,
    ICONE_NIVEL,
)
from src.api.cache_supabase import ler_cache, ultima_sincronizacao

# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Aureum Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

FRONTEND = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(FRONTEND / "index.html"))


# ── Helpers ───────────────────────────────────────────────────────────────────

_MES_NOMES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]


def _nome_mes(m: int) -> str:
    return _MES_NOMES[m - 1]


def _pedidos() -> list:
    """Lê pedidos do cache Supabase (TTL generoso: 24h — o Streamlit faz o sync)."""
    dados, _ = ler_cache("pedidos", max_idade_horas=24.0)
    return dados or []


def _mes_anterior(mes: int, ano: int) -> tuple[int, int]:
    if mes > 1:
        return mes - 1, ano
    return 12, ano - 1


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/meses")
def api_meses():
    """Lista de meses disponíveis (mês futuro + atual + 7 passados)."""
    hoje = date.today()
    resultado = []
    for delta in range(-1, 8):   # -1 = 1 mês futuro
        m = hoje.month - delta
        a = hoje.year
        while m <= 0:
            m += 12
            a -= 1
        while m > 12:
            m -= 12
            a += 1
        resultado.append({
            "value": f"{a}-{m:02d}",
            "label": f"{_nome_mes(m)}/{a}",
            "mes": m,
            "ano": a,
        })
    return resultado


@app.get("/api/kpis")
def api_kpis(mes: int = Query(...), ano: int = Query(...)):
    ped = _pedidos()
    if not ped:
        return {"erro": "cache_vazio"}

    df_comp, _ = calcular_competencia(ped, mes, ano)
    total_vendas = float(df_comp["Total"].sum()) if not df_comp.empty else 0.0
    n_acertos    = int((df_comp["Total"] > 0).sum()) if not df_comp.empty else 0
    ticket_medio = round(total_vendas / n_acertos, 2) if n_acertos else 0.0

    # Revendedoras ativas = maletas em aberto
    revs_ativas = {
        p["fk_revendedor_id"] for p in ped
        if p.get("status") == "Aberto" and p.get("fk_revendedor_id")
    }

    # Ganhadoras = atingiram mínimo do seu nível
    df_class = classificar_revendedoras(ped, mes, ano)
    ganhadoras = 0
    if not df_class.empty:
        for _, row in df_class.iterrows():
            nivel  = row.get("Nível", "")
            minimo = MINIMO_VENDAS.get(nivel, 0)
            if minimo > 0 and float(row.get("Vendas mês", 0)) >= minimo:
                ganhadoras += 1

    # Variação vs mês anterior (%)
    m_ant, a_ant = _mes_anterior(mes, ano)
    df_ant, _ = calcular_competencia(ped, m_ant, a_ant)
    total_ant  = float(df_ant["Total"].sum()) if not df_ant.empty else 0.0
    variacao   = round((total_vendas - total_ant) / total_ant * 100, 1) if total_ant else 0.0

    ultima = ultima_sincronizacao("pedidos")

    return {
        "total_vendas":        round(total_vendas, 2),
        "ticket_medio":        ticket_medio,
        "revendedoras_ativas": len(revs_ativas),
        "ganhadoras_meta":     ganhadoras,
        "n_acertos":           n_acertos,
        "variacao_pct":        variacao,
        "ultima_sync":         ultima.isoformat() if ultima else None,
    }


@app.get("/api/vendas-meses")
def api_vendas_meses(
    mes: int = Query(...),
    ano: int = Query(...),
    n:   int = Query(6),
):
    """Vendas mensais dos últimos n meses (terminando no mês selecionado)."""
    ped = _pedidos()
    meses_seq: list[tuple[int, int]] = []
    m, a = mes, ano
    for _ in range(n):
        meses_seq.insert(0, (m, a))
        m -= 1
        if m == 0:
            m = 12
            a -= 1

    resultado = []
    for (mi, ai) in meses_seq:
        df, _ = calcular_competencia(ped, mi, ai)
        total = float(df["Total"].sum()) if not df.empty else 0.0
        resultado.append({
            "label": f"{_nome_mes(mi)}/{str(ai)[2:]}",
            "mes":   mi,
            "ano":   ai,
            "valor": round(total, 2),
        })
    return resultado


@app.get("/api/top-revendedoras")
def api_top_revs(
    mes:   int = Query(...),
    ano:   int = Query(...),
    limit: int = Query(5),
):
    ped = _pedidos()
    df_comp, _ = calcular_competencia(ped, mes, ano)
    if df_comp.empty:
        return []

    df_class = classificar_revendedoras(ped, mes, ano)
    nivel_por_rid: dict[int, str] = {}
    if not df_class.empty:
        for _, r in df_class.iterrows():
            nivel_por_rid[r["fk_revendedor_id"]] = r.get("Nível", "Pérola")

    top    = df_comp.sort_values("Total", ascending=False).head(limit)
    maximo = float(top.iloc[0]["Total"]) if len(top) else 1.0

    return [
        {
            "nome":  row["Nome"],
            "total": round(float(row["Total"]), 2),
            "nivel": nivel_por_rid.get(row["fk_revendedor_id"], "Pérola"),
            "pct":   round(float(row["Total"]) / maximo * 100, 1),
        }
        for _, row in top.iterrows()
    ]


@app.get("/api/distribuicao-niveis")
def api_niveis(mes: int = Query(...), ano: int = Query(...)):
    ped = _pedidos()
    df_class = classificar_revendedoras(ped, mes, ano)
    if df_class.empty:
        return []

    contagem = df_class["Nível"].value_counts().to_dict()
    total    = sum(contagem.values()) or 1
    ORDEM    = ["Diamante", "Ouro", "Pérola", "Sem nível"]
    CORES    = {
        "Diamante":  "#AB6774",
        "Ouro":      "#C4985A",
        "Pérola":    "#0B7E78",
        "Sem nível": "#B8A0A6",
    }

    return [
        {
            "nivel": nv,
            "icone": ICONE_NIVEL.get(nv, ""),
            "count": contagem.get(nv, 0),
            "pct":   round(contagem.get(nv, 0) / total * 100, 1),
            "cor":   CORES.get(nv, "#B8A0A6"),
        }
        for nv in ORDEM if contagem.get(nv, 0) > 0
    ]


@app.get("/api/acertos")
def api_acertos(mes: int = Query(...), ano: int = Query(...)):
    """Pedidos com acerto/baixa no mês selecionado (abertos + baixados)."""
    ped  = _pedidos()
    hoje = date.today()
    rows = []

    for p in ped:
        status    = p.get("status", "")
        comprador = p.get("comprador") or {}
        nome      = comprador.get("nome") or f"Rev {p.get('fk_revendedor_id')}"

        if status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if not (d and d.month == mes and d.year == ano):
                continue
            qtd   = int(float(p.get("quantidade") or 0))
            valor = float(p.get("valor_pre_baixa") or 0)
            sit   = "Vencido" if d < hoje else "Agendado"

        elif status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if not (d and d.month == mes and d.year == ano):
                continue
            qab = p.get("quantidade_antes_baixa")
            qtd = int(float(qab)) if qab else int(float(p.get("quantidade") or 0))
            valor = float(p.get("valor_total") or 0)
            sit   = "Realizado"

        else:
            continue

        rows.append({
            "nome":       nome,
            "nivel":      nivel_por_pecas(qtd),
            "data":       d.strftime("%d/%m"),
            "data_iso":   d.isoformat(),
            "valor":      round(valor, 2),
            "sit":        sit,
            "supervisor": p.get("supervisor_nome") or "—",
        })

    rows.sort(key=lambda r: r["data_iso"])
    return rows[:30]
