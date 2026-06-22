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
    "Disk Tenha":   "🚗",
    "Motoboy":      "🏍️",
}

DIAS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ── Supabase ──────────────────────────────────────────────────────────────────

def _get_client():
    try:
        from supabase import create_client
        import streamlit as st
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except (KeyError, FileNotFoundError):
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


_SUPABASE_OK = None  # None = não testado, True = ok, False = erro


def _fetch_supabase() -> tuple[dict, bool]:
    """Retorna (dados, supabase_ok). supabase_ok=False indica erro de conexão."""
    global _SUPABASE_OK
    client = _get_client()
    if client is None:
        _SUPABASE_OK = False
        return {}, False
    try:
        res = client.table("agendamentos").select(
            "pedido_id,data_agendada,forma,obs,hora_agendada,data_envio_maleta,hora_envio_maleta"
        ).execute()
        _SUPABASE_OK = True
        return {
            row["pedido_id"]: {
                "data_agendada":     row.get("data_agendada", ""),
                "forma":             row.get("forma", ""),
                "obs":               row.get("obs", ""),
                "hora_agendada":     row.get("hora_agendada", ""),
                "data_envio_maleta": row.get("data_envio_maleta") or "",
                "hora_envio_maleta": row.get("hora_envio_maleta") or "",
            }
            for row in (res.data or [])
        }, True
    except Exception as e:
        _SUPABASE_OK = False
        try:
            import streamlit as st
            st.error(
                f"⚠️ Erro ao conectar ao Supabase (agendamentos): {e}. "
                "Os dados exibidos podem estar desatualizados. Verifique o RLS da tabela."
            )
        except Exception:
            pass
        return {}, False


# ── Persistência ──────────────────────────────────────────────────────────────

def _load_local() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _migrar_local_para_supabase(client, local: dict):
    """Copia todos os registros do JSON local para o Supabase (executado uma única vez)."""
    if not local:
        return
    try:
        registros = [
            {
                "pedido_id":     str(pid),
                "data_agendada": v.get("data_agendada", ""),
                "forma":         v.get("forma", ""),
                "obs":           v.get("obs", "") or "",
                "hora_agendada": v.get("hora_agendada", "") or "",
            }
            for pid, v in local.items()
        ]
        client.table("agendamentos").upsert(
            registros, on_conflict="pedido_id"
        ).execute()
    except Exception:
        pass


def load_agendamentos() -> dict:
    client = _get_client()
    if client is not None:
        dados, supabase_ok = _fetch_supabase()
        if not supabase_ok:
            # Erro de conexão — usa local como fallback temporário, mas não migra
            return _load_local()
        if not dados:
            # Supabase acessível e tabela genuinamente vazia — migra local se houver
            local = _load_local()
            if local:
                _migrar_local_para_supabase(client, local)
                return local
        return dados
    return _load_local()


def save_agendamento(
    pedido_id,
    data_agendada: str,
    forma: str,
    obs: str = "",
    hora: str = "",
):
    client = _get_client()
    if client is not None:
        try:
            client.table("agendamentos").upsert(
                {
                    "pedido_id":     str(pedido_id),
                    "data_agendada": data_agendada,
                    "forma":         forma,
                    "obs":           obs or "",
                    "hora_agendada": hora or "",
                },
                on_conflict="pedido_id",
            ).execute()
            return
        except Exception as e:
            import streamlit as st
            st.error(
                f"❌ Falha ao salvar agendamento no Supabase: {e}. "
                "Verifique se o RLS da tabela 'agendamentos' está desativado. "
                "O agendamento NÃO foi salvo."
            )
            return  # não cai no fallback local silencioso
    # Sem Supabase configurado: usa local
    import streamlit as st
    st.warning("⚠️ Supabase não configurado. Salvando localmente (dados não persistem entre deploys).")
    ag = _load_local()
    ag[str(pedido_id)] = {
        "data_agendada": data_agendada,
        "forma":         forma,
        "obs":           obs,
        "hora_agendada": hora,
    }
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(ag, f, ensure_ascii=False, indent=2)


def save_envio_maleta(pedido_id, data_envio: str, hora_envio: str = "") -> None:
    """Salva/atualiza a data de envio da maleta em um agendamento já existente."""
    client = _get_client()
    if client is not None:
        try:
            client.table("agendamentos").update({
                "data_envio_maleta": data_envio,
                "hora_envio_maleta": hora_envio or "",
            }).eq("pedido_id", str(pedido_id)).execute()
            return
        except Exception as e:
            import streamlit as st
            st.error(
                f"❌ Falha ao salvar envio de maleta no Supabase: {e}. "
                "Verifique se as colunas existem na tabela 'agendamentos'."
            )
            return
    import streamlit as st
    st.warning("⚠️ Supabase não configurado. Data de envio não foi salva.")


def remove_agendamento(pedido_id):
    client = _get_client()
    if client is not None:
        try:
            client.table("agendamentos").delete().eq(
                "pedido_id", str(pedido_id)
            ).execute()
            return
        except Exception as e:
            try:
                import streamlit as st
                st.warning(f"⚠️ Erro ao remover agendamento no Supabase: {e}.")
            except Exception:
                pass
    # Fallback local
    ag = _load_local()
    ag.pop(str(pedido_id), None)
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(ag, f, ensure_ascii=False, indent=2)


# ── Montagem do DataFrame de acertos ──────────────────────────────────────────

def montar_acertos(pedidos: list) -> pd.DataFrame:
    ag_map = load_agendamentos()
    hoje   = date.today()
    corte  = hoje - timedelta(days=90)  # 3 meses: baixados recentes + abertos não muito antigos

    rows = []
    for p in pedidos:
        pid    = p.get("id")
        rid    = p.get("fk_revendedor_id")
        status = p.get("status", "")

        # Ignora pedidos cancelados ou com status desconhecido
        if status not in ("Aberto", "Baixado"):
            continue

        d_acerto = parse_date(p.get("data_acerto"))
        if not d_acerto:
            continue

        d_baixa = parse_date(p.get("data_baixa")) if status == "Baixado" else None

        # Baixados: apenas últimos 90 dias
        if status == "Baixado" and (not d_baixa or d_baixa < corte):
            continue

        # Abertos: apenas acertos dos últimos 3 meses (evita vencidos muito antigos)
        if status != "Baixado" and d_acerto < corte:
            continue

        comprador   = p.get("comprador") or {}
        nome        = comprador.get("nome") or f"Rev {rid}"
        supervisor  = p.get("supervisor_nome") or "Sem supervisora"
        cod_pedido  = p.get("codigo_pedido") or ""

        ag               = ag_map.get(str(pid), {})
        d_ag_str         = ag.get("data_agendada")
        d_agendada       = parse_date(d_ag_str) if d_ag_str else None
        forma            = ag.get("forma", "")
        obs              = ag.get("obs", "")
        hora_ag          = ag.get("hora_agendada", "")
        data_envio_str   = ag.get("data_envio_maleta", "")
        hora_envio_str   = ag.get("hora_envio_maleta", "")
        d_envio_maleta   = parse_date(data_envio_str) if data_envio_str else None

        data_ref = d_agendada or d_baixa or d_acerto

        if status == "Baixado":
            if d_baixa and d_baixa > d_acerto:
                atraso   = (d_baixa - d_acerto).days
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

        valor = float(p.get("valor_total") if status == "Baixado" else p.get("valor_pre_baixa") or 0)

        rows.append({
            "id":                pid,
            "Código":            cod_pedido,
            "Nome":              nome,
            "Supervisor":        supervisor,
            "Status":            status,
            "Data acerto":       d_acerto,
            "Data agendada":     d_agendada,
            "Data baixa":        d_baixa,
            "Data ref":          data_ref,
            "Valor":             round(valor, 2),
            "Forma":             forma,
            "Obs":               obs,
            "Hora agendada":     hora_ag,
            "Data envio maleta": d_envio_maleta,
            "Hora envio maleta": hora_envio_str,
            "Situação":          situacao,
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
    seg = d - timedelta(days=d.weekday())
    return seg, seg + timedelta(days=6)


def proxima_semana_resumo(df: pd.DataFrame, hoje: date = None) -> dict:
    if hoje is None:
        hoje = date.today()
    seg_prox = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=1)
    dom_prox = seg_prox + timedelta(days=6)

    if df.empty:
        return {"total": 0, "agendados": 0, "a_agendar": 0}

    mask    = (df["Data ref"] >= seg_prox) & (df["Data ref"] <= dom_prox)
    df_prox = df[mask]
    return {
        "total":     len(df_prox),
        "agendados": (df_prox["Situação"] == "📅 Agendado").sum(),
        "a_agendar": (df_prox["Situação"] == "⬜ A agendar").sum(),
    }
