"""
Acesso ao Google Sheets via conta de serviço (gspread).

Credenciais: .streamlit/google_credentials.json
  → gerado no Google Cloud Console > Conta de Serviço > Chave JSON

IDs das planilhas:
  FINANCEIRO_ID : planilha de despesas mensais
  DRE_ID        : planilha DRE (leitura de referência)
"""

from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache

import streamlit as st

# ── IDs das planilhas ─────────────────────────────────────────────────────────

FINANCEIRO_ID = "1cUiug2IFmRoAKN8UsQ_BTwuKKVxVthyZBwsVu9pfKWA"
DRE_ID        = "1neVIiyW9NE0riARjz7qvEu-gJj1YVCXHJmivhaMPD8M"

# Caminho padrão do arquivo de credenciais
_CRED_PATH = Path(__file__).parent.parent.parent / ".streamlit" / "google_credentials.json"


def _get_creds_dict() -> dict | None:
    """
    Retorna o dict de credenciais da conta de serviço.
    Tenta 3 fontes em ordem:
      1. st.secrets["GOOGLE_CREDENTIALS"] (JSON inline no secrets.toml)
      2. Variável de ambiente GOOGLE_CREDENTIALS
      3. Arquivo .streamlit/google_credentials.json
    """
    # 1. st.secrets
    try:
        raw = st.secrets.get("GOOGLE_CREDENTIALS", "")
        if raw:
            return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        pass

    # 2. Variável de ambiente
    raw_env = os.getenv("GOOGLE_CREDENTIALS", "")
    if raw_env:
        try:
            return json.loads(raw_env)
        except Exception:
            pass

    # 3. Arquivo JSON local
    if _CRED_PATH.exists():
        try:
            return json.loads(_CRED_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    return None


@st.cache_resource(show_spinner=False)
def _get_gspread_client():
    """Cria e cacheia o cliente gspread (uma conexão por processo)."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = _get_creds_dict()
        if not creds_dict:
            return None

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception:
        return None


# ── Leitura das planilhas ─────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)   # cache 30 min
def ler_despesas_mes(mes: int, ano: int) -> list[dict]:
    """
    Lê as despesas da planilha financeira para o mês/ano informado.
    Retorna lista de dicts: {nome, previsto, realizado, tipo, forma_pgto, dia}
    Retorna [] se a aba não existir ou credenciais não configuradas.
    """
    from src.logic.dre import nome_aba_financeiro

    client = _get_gspread_client()
    if client is None:
        return []

    try:
        sheet = client.open_by_key(FINANCEIRO_ID)
        nome_aba = nome_aba_financeiro(mes, ano)

        try:
            aba = sheet.worksheet(nome_aba)
        except Exception:
            return []   # aba do mês não existe ainda

        rows = aba.get("B:G")   # colunas B até G

        despesas = []
        for row in rows:
            # Linha de cabeçalho ou vazia
            if not row or not row[0] or row[0].strip().startswith("Despesa"):
                continue

            nome = str(row[0]).strip()
            if not nome:
                continue

            def _val(idx: int) -> float:
                try:
                    if idx >= len(row):
                        return 0.0
                    v = str(row[idx]).replace("R$", "").replace(".", "").replace(",", ".").strip()
                    return float(v) if v else 0.0
                except (ValueError, TypeError):
                    return 0.0

            despesas.append({
                "nome":       nome,
                "previsto":   _val(1),   # coluna C
                "realizado":  _val(2),   # coluna D
                "tipo":       str(row[3]).strip() if len(row) > 3 else "",
                "forma_pgto": str(row[4]).strip() if len(row) > 4 else "",
                "dia":        str(row[5]).strip() if len(row) > 5 else "",
            })

        return despesas

    except Exception:
        return []


def credentials_configuradas() -> bool:
    """Verifica se as credenciais do Google estão disponíveis."""
    return _get_creds_dict() is not None
