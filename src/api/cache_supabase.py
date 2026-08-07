"""
Cache persistente em Supabase para dados da API Jueri.

Tabelas necessárias — rode supabase_cache_setup.sql no SQL Editor do Supabase:
  cache_jueri            — listas (pedidos, produtos, revendedores, categorias)
  cache_pedidos_detalhes — detalhes individuais de pedidos (itens)
"""

import os
from datetime import datetime, timezone


# ── Client ────────────────────────────────────────────────────────────────────

def _get_client():
    try:
        from supabase import create_client
        import streamlit as st
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Listas (pedidos, produtos, revendedores, categorias) ─────────────────────

def ler_cache(chave: str, max_idade_horas: float = 4.0):
    """
    Retorna (dados: list, atualizado_em: datetime | None).
    dados = None quando: cache não existe, erro, ou mais antigo que max_idade_horas.
    atualizado_em é retornado mesmo quando expirado (útil para mostrar quando foi a última sync).
    """
    client = _get_client()
    if client is None:
        return None, None
    try:
        res = (
            client.table("cache_jueri")
            .select("dados, atualizado_em")
            .eq("chave", chave)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None, None

        row = rows[0]
        ts_str = row.get("atualizado_em") or ""
        atualizado = (
            datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts_str else None
        )

        if atualizado:
            idade_h = (datetime.now(timezone.utc) - atualizado).total_seconds() / 3600
            if idade_h > max_idade_horas:
                return None, atualizado  # expirado — caller decide buscar da API
        return row.get("dados") or [], atualizado
    except Exception:
        return None, None


def escrever_cache(chave: str, dados: list) -> bool:
    """Grava/atualiza a lista de dados para a chave fornecida."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.table("cache_jueri").upsert(
            {"chave": chave, "dados": dados, "atualizado_em": _agora_iso()},
            on_conflict="chave",
        ).execute()
        return True
    except Exception:
        return False


def ultima_sincronizacao(chave: str) -> datetime | None:
    """Retorna quando o cache foi atualizado pela última vez, ou None."""
    client = _get_client()
    if client is None:
        return None
    try:
        res = (
            client.table("cache_jueri")
            .select("atualizado_em")
            .eq("chave", chave)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows or not rows[0].get("atualizado_em"):
            return None
        ts = rows[0]["atualizado_em"]
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ── Detalhes de pedidos individuais ──────────────────────────────────────────

def ler_cache_pedidos_batch(pedido_ids: list) -> dict:
    """
    Retorna {pedido_id: dados_dict} para os IDs que estão no cache.
    IDs ausentes simplesmente não aparecem no resultado.
    """
    client = _get_client()
    if client is None or not pedido_ids:
        return {}
    try:
        # Supabase .in_() aceita no máximo 1000 valores — divide se necessário
        BATCH = 500
        resultado = {}
        for i in range(0, len(pedido_ids), BATCH):
            lote = pedido_ids[i : i + BATCH]
            res = (
                client.table("cache_pedidos_detalhes")
                .select("pedido_id, dados")
                .in_("pedido_id", lote)
                .execute()
            )
            for row in (res.data or []):
                resultado[row["pedido_id"]] = row["dados"]
        return resultado
    except Exception:
        return {}


def escrever_cache_pedidos(pedidos_map: dict) -> bool:
    """
    pedidos_map = {pedido_id: dados_dict}
    Grava em lotes de 200 para não estourar o limite de payload do Supabase.
    """
    client = _get_client()
    if client is None or not pedidos_map:
        return False
    try:
        rows = [
            {
                "pedido_id": int(pid),
                "dados": dados,
                "atualizado_em": _agora_iso(),
            }
            for pid, dados in pedidos_map.items()
        ]
        BATCH = 200
        for i in range(0, len(rows), BATCH):
            client.table("cache_pedidos_detalhes").upsert(
                rows[i : i + BATCH], on_conflict="pedido_id"
            ).execute()
        return True
    except Exception:
        return False
