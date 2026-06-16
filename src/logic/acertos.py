import json
import os
from datetime import date, timedelta
import pandas as pd
from src.logic.revendedoras import parse_date

_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "acertos_agendamento.json")
)

FORMAS = {
    "Presencial":   "🏪",
    "Correios":     "📮",
    "Disk Entrega": "🚗",
    "Motoboy":      "🏍️",
}

DIAS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ── Persistência ──────────────────────────────────────────────────────────────

def load_agendamentos() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_agendamento(pedido_id, data_agendada: str, forma: str, obs: str = ""):
    ag = load_agendamentos()
    ag[str(pedido_id)] = {"data_agendada": data_agendada, "forma": forma, "obs": obs}
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(ag, f, ensure_ascii=False, indent=2)


def remove_agendamento(pedido_id):
    ag = load_agendamentos()
    ag.pop(str(pedido_id), None)
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(ag, f, ensure_ascii=False, indent=2)


# ── Montagem do DataFrame de acertos ──────────────────────────────────────────

def montar_acertos(pedidos: list) -> pd.DataFrame:
    """
    Retorna um DataFrame com todos os pedidos relevantes para o calendário
    de acertos (abertos com data_acerto futura/corrente + baixados recentes).
    """
    ag_map    = load_agendamentos()
    hoje      = date.today()
    corte_passado = hoje - timedelta(days=90)   # baixados dos últimos 90 dias

    rows = []
    for p in pedidos:
        pid    = p.get("id")
        rid    = p.get("fk_revendedor_id")
        status = p.get("status", "")

        d_acerto = parse_date(p.get("data_acerto"))
        if not d_acerto:
            continue

        # Inclui: abertos com acerto futuro/atual e baixados dos últimos 90 dias
        d_baixa = parse_date(p.get("data_baixa")) if status == "Baixado" else None
        if status == "Baixado" and (not d_baixa or d_baixa < corte_passado):
            continue

        comprador  = p.get("comprador") or {}
        nome       = comprador.get("nome") or f"Rev {rid}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"

        ag          = ag_map.get(str(pid), {})
        d_ag_str    = ag.get("data_agendada")
        d_agendada  = parse_date(d_ag_str) if d_ag_str else None
        forma       = ag.get("forma", "")
        obs         = ag.get("obs", "")

        # Data de referência para posição no calendário
        data_ref = d_agendada or d_baixa or d_acerto

        # Situação
        if status == "Baixado":
            if d_baixa and d_baixa > d_acerto:
                atraso = (d_baixa - d_acerto).days
                situacao = f"⚠️ Atrasou {atraso}d"
            else:
                situacao = "✅ Realizado"
        else:
            if d_acerto < hoje:
                situacao = "🔴 Vencido"
            elif d_agendada:
                situacao = "📅 Agendado"
            else:
                situacao = "⬜ A agendar"

        if status == "Baixado":
            valor = float(p.get("valor_total") or 0)
        else:
            valor = float(p.get("valor_pre_baixa") or 0)

        rows.append({
            "id":           pid,
            "Nome":         nome,
            "Supervisor":   supervisor,
            "Status":       status,
            "Data acerto":  d_acerto,
            "Data agendada": d_agendada,
            "Data baixa":   d_baixa,
            "Data ref":     data_ref,
            "Valor":        round(valor, 2),
            "Forma":        forma,
            "Obs":          obs,
            "Situação":     situacao,
        })

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values("Data ref")
        .reset_index(drop=True)
    )


# ── Helpers de semana ─────────────────────────────────────────────────────────

def semana_de(d: date):
    """Retorna (segunda, domingo) da semana que contém d."""
    seg = d - timedelta(days=d.weekday())
    return seg, seg + timedelta(days=6)


def proxima_semana_resumo(df: pd.DataFrame, hoje: date = None) -> dict:
    """Conta acertos da próxima semana (segunda a domingo)."""
    if hoje is None:
        hoje = date.today()
    seg_prox = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=1)
    dom_prox = seg_prox + timedelta(days=6)

    if df.empty:
        return {"total": 0, "agendados": 0, "a_agendar": 0}

    mask = (df["Data ref"] >= seg_prox) & (df["Data ref"] <= dom_prox)
    df_prox = df[mask]
    return {
        "total":      len(df_prox),
        "agendados":  (df_prox["Situação"] == "📅 Agendado").sum(),
        "a_agendar":  (df_prox["Situação"] == "⬜ A agendar").sum(),
    }
