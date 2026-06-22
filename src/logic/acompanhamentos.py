import json
import os

import streamlit as st

_SEMANAS = ["0-7", "8-15", "16-20", "21-30"]

# ── Arquivo local (fallback para dev offline) ─────────────────────────────────
_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "acompanhamentos.json")
)


def _get_client():
    try:
        from supabase import create_client
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


# ── Supabase ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_supabase() -> tuple:
    """Retorna (rows: list, supabase_ok: bool, erro: str). supabase_ok=False indica erro."""
    client = _get_client()
    if client is None:
        return [], False, ""
    try:
        res = client.table("acompanhamentos").select("*").order("criado_em").execute()
        return res.data or [], True, ""
    except Exception as e:
        return [], False, str(e)


def _rows_para_dict(rows: list) -> dict:
    dados: dict = {}
    for row in rows:
        nome = row.get("nome", "")
        if not nome:
            continue
        if nome not in dados:
            dados[nome] = []
        dados[nome].append({
            "_id":      row.get("id"),   # ID do Supabase para exclusão
            "data":     str(row.get("data", "")),
            "descricao": row.get("descricao", ""),
            "prebaixa_semanas": {
                "0-7":   float(row.get("prebaixa_0_7",   0) or 0),
                "8-15":  float(row.get("prebaixa_8_15",  0) or 0),
                "16-20": float(row.get("prebaixa_16_20", 0) or 0),
                "21-30": float(row.get("prebaixa_21_30", 0) or 0),
            },
        })
    return dados


# ── JSON local (fallback) ─────────────────────────────────────────────────────

def _load_local() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_local(nome: str, data_str: str, descricao: str, prebaixa_semanas: dict):
    dados = _load_local()
    if nome not in dados:
        dados[nome] = []
    dados[nome].append({
        "data": data_str,
        "descricao": descricao,
        "prebaixa_semanas": {k: prebaixa_semanas.get(k, 0.0) for k in _SEMANAS},
    })
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ── API pública ───────────────────────────────────────────────────────────────

def load_acompanhamentos() -> dict:
    if _get_client() is not None:
        rows, ok, erro = _fetch_supabase()
        if not ok and erro:
            st.error(
                f"⚠️ Erro ao carregar acompanhamentos do Supabase: {erro}. "
                "Verifique se o RLS da tabela 'acompanhamentos' está desativado."
            )
        return _rows_para_dict(rows)
    return _load_local()


def save_acompanhamento(nome: str, data_str: str, descricao: str, prebaixa_semanas: dict):
    client = _get_client()
    if client is not None:
        try:
            client.table("acompanhamentos").insert({
                "nome":           nome,
                "data":           data_str,
                "descricao":      descricao,
                "prebaixa_0_7":   float(prebaixa_semanas.get("0-7",   0)),
                "prebaixa_8_15":  float(prebaixa_semanas.get("8-15",  0)),
                "prebaixa_16_20": float(prebaixa_semanas.get("16-20", 0)),
                "prebaixa_21_30": float(prebaixa_semanas.get("21-30", 0)),
            }).execute()
            _fetch_supabase.clear()
            return
        except Exception as e:
            st.error(
                f"❌ Falha ao salvar acompanhamento no Supabase: {e}. "
                "Verifique se o RLS da tabela 'acompanhamentos' está desativado. "
                "O registro NÃO foi salvo."
            )
            return  # não cai no fallback local silencioso
    # Sem Supabase configurado: usa local (apenas desenvolvimento)
    st.warning("⚠️ Supabase não configurado. Salvando localmente (dados não persistem entre deploys).")
    _save_local(nome, data_str, descricao, prebaixa_semanas)


def delete_acompanhamento(nome: str, record_id=None, local_idx: int = None):
    client = _get_client()
    if client is not None and record_id is not None:
        try:
            client.table("acompanhamentos").delete().eq("id", record_id).execute()
            _fetch_supabase.clear()
            return
        except Exception as e:
            st.warning(f"⚠️ Erro ao excluir no Supabase: {e}")
            return
    # Fallback: exclusão no JSON local
    if local_idx is not None:
        dados = _load_local()
        registros = dados.get(nome, [])
        if 0 <= local_idx < len(registros):
            registros.pop(local_idx)
            dados[nome] = registros
            os.makedirs(os.path.dirname(_FILE), exist_ok=True)
            with open(_FILE, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)


def get_ultimos_valores(nome: str) -> dict:
    registros = load_acompanhamentos().get(nome, [])
    if not registros:
        return {k: 0.0 for k in _SEMANAS}
    return {k: registros[-1].get("prebaixa_semanas", {}).get(k, 0.0) for k in _SEMANAS}


def get_historico(nome: str) -> list:
    client = _get_client()
    if client is not None:
        rows, ok, _ = _fetch_supabase()
        return _rows_para_dict(rows).get(nome, [])
    # Sem Supabase configurado: usa local com índice para exclusão
    dados = _load_local()
    return [{"_local_idx": i, **r} for i, r in enumerate(dados.get(nome, []))]
