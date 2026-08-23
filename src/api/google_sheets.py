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

FINANCEIRO_ID    = "1cUiug2IFmRoAKN8UsQ_BTwuKKVxVthyZBwsVu9pfKWA"
DRE_ID           = "1neVIiyW9NE0riARjz7qvEu-gJj1YVCXHJmivhaMPD8M"
CMV_HISTORICO_ID = "1D_0ZVjbks4Os087W5bBvtiDALlt9GTecusIA6NgOVJ8"

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


# ── CMV histórico ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)   # cache 1h
def ler_cmv_historico() -> dict[tuple[int, int], float]:
    """
    Lê o % CMV por (mes, ano) da planilha histórica.
    Estrutura da planilha:
      - Linha 4: cabeçalhos dos meses
      - Linha 5: % CMV (ex: "10,76%")
      - Colunas B:M (índices 1-12) = 2025, meses 1-12
      - Colunas N+ (índice 13+)    = 2026, meses 1-N
      - Última coluna com "TOTAL"  = ignorada
    Retorna {(mes, ano): pct_decimal}, ex: {(6, 2026): 0.1076}
    """
    client = _get_gspread_client()
    if client is None:
        return {}
    try:
        sheet  = client.open_by_key(CMV_HISTORICO_ID)
        aba    = sheet.get_worksheet(0)
        rows   = aba.get_all_values()
        if len(rows) < 5:
            return {}

        headers = rows[3]   # linha 4 (0-indexed: 3)
        pcts    = rows[4]   # linha 5 (0-indexed: 4)

        MESES_LONG  = ["JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
                       "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"]
        MESES_CURTO = ["JAN","FEV","MAR","ABR","MAI","JUN",
                       "JUL","AGO","SET","OUT","NOV","DEZ"]

        resultado: dict[tuple[int, int], float] = {}

        for col_idx, (h, p) in enumerate(zip(headers, pcts)):
            h = h.strip().upper()
            p = p.strip()
            if not h or not p or h == "TOTAL":
                continue
            try:
                pct = float(p.replace("%", "").replace(",", ".").strip()) / 100
            except (ValueError, TypeError):
                continue

            # B=índice 1, M=índice 12 → 2025 (colunas 1-12)
            # N=índice 13 em diante → 2026
            if 1 <= col_idx <= 12:
                ano = 2025
                mes = col_idx          # col 1=Jan, col 12=Dez
            elif col_idx >= 13:
                ano = 2026
                if h in MESES_LONG:
                    mes = MESES_LONG.index(h) + 1
                elif h in MESES_CURTO:
                    mes = MESES_CURTO.index(h) + 1
                else:
                    continue
            else:
                continue

            resultado[(mes, ano)] = pct

        return resultado
    except Exception:
        return {}


def cmv_pct_mes(mes: int, ano: int) -> float | None:
    """
    Retorna o % CMV histórico para o mês/ano informado.
    Retorna None se não houver dado para o período.
    """
    historico = ler_cmv_historico()
    return historico.get((mes, ano))
