import os


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


def load_entregas(mes_key: str) -> dict:
    """Retorna {rev_id_str: bool} com o status de entrega do prêmio no mês."""
    client = _get_client()
    if client is None:
        return {}
    try:
        res = (
            client.table("entrega_premiacoes")
            .select("rev_id,entregue")
            .eq("mes_key", mes_key)
            .execute()
        )
        return {str(row["rev_id"]): bool(row["entregue"]) for row in (res.data or [])}
    except Exception as e:
        import streamlit as st
        st.error(
            f"⚠️ Erro ao carregar entregas de prêmios do Supabase: {e}. "
            "Verifique se o RLS da tabela 'entrega_premiacoes' está desativado."
        )
        return {}


def save_entrega(mes_key: str, rev_id: str, nome: str, entregue: bool) -> None:
    """Grava/atualiza o status de entrega de uma revendedora no mês."""
    client = _get_client()
    if client is None:
        return
    try:
        client.table("entrega_premiacoes").upsert(
            {
                "mes_key": mes_key,
                "rev_id":  str(rev_id),
                "nome":    nome,
                "entregue": entregue,
            },
            on_conflict="mes_key,rev_id",
        ).execute()
    except Exception as e:
        import streamlit as st
        st.error(
            f"❌ Falha ao salvar entrega de prêmio no Supabase: {e}. "
            "Verifique se o RLS da tabela 'entrega_premiacoes' está desativado."
        )
