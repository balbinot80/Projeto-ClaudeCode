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


def load_motivos(pedido_id) -> list:
    """Retorna lista de motivos para um pedido, ordenada por data decrescente."""
    client = _get_client()
    if client is None:
        return []
    try:
        res = (
            client.table("motivos_atraso")
            .select("id,pedido_id,motivo,usuario,created_at")
            .eq("pedido_id", str(pedido_id))
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        try:
            import streamlit as st
            st.warning(f"⚠️ Erro ao carregar motivos de atraso: {e}")
        except Exception:
            pass
        return []


def save_motivo(pedido_id, motivo: str, usuario: str = "") -> bool:
    """Insere um novo registro de motivo de atraso. Retorna True se bem-sucedido."""
    client = _get_client()
    if client is None:
        try:
            import streamlit as st
            st.warning("⚠️ Supabase não configurado. Motivo não foi salvo.")
        except Exception:
            pass
        return False
    try:
        client.table("motivos_atraso").insert({
            "pedido_id": str(pedido_id),
            "motivo": motivo,
            "usuario": usuario or "",
        }).execute()
        return True
    except Exception as e:
        try:
            import streamlit as st
            st.error(
                f"❌ Falha ao salvar motivo no Supabase: {e}. "
                "Verifique se a tabela 'motivos_atraso' existe e o RLS está desativado."
            )
        except Exception:
            pass
        return False
