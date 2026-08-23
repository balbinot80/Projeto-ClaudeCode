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


@st.cache_data(ttl=1800, show_spinner=False)   # cache 30 min
def ler_taxa_cartao_mes(mes: int, ano: int) -> float:
    """
    Soma a coluna N (Tx Cartão) da aba mensal do FINANCEIRO.
    Usar a partir de Jul/2026, onde a taxa é cobrada por pedido
    e registrada diretamente na tabela de receita.
    Retorna 0.0 se a aba não existir.
    """
    from src.logic.dre import nome_aba_financeiro

    client = _get_gspread_client()
    if client is None:
        return 0.0
    try:
        sheet    = client.open_by_key(FINANCEIRO_ID)
        nome_aba = nome_aba_financeiro(mes, ano)
        try:
            aba = sheet.worksheet(nome_aba)
        except Exception:
            return 0.0

        col_n = aba.col_values(14)   # coluna N = 14 (1-based)
        total = 0.0
        for v in col_n[2:]:          # pula as 2 linhas de cabeçalho
            s = (str(v).strip()
                 .replace("R$", "").replace(".", "").replace(",", ".").strip())
            try:
                f = float(s)
                if f > 0:
                    total += f
            except (ValueError, TypeError):
                pass
        return total
    except Exception:
        return 0.0


# ── CMV histórico ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)   # cache 1h
def ler_cmv_historico() -> dict:
    """
    Lê a planilha de CMV histórico e retorna um dict com:
      - 'pct'          : float  — % médio total (total_compra / total_venda)
      - 'total_compra' : float  — soma de todas as compras
      - 'total_venda'  : float  — soma de todas as vendas
      - 'n_meses'      : int    — quantos meses foram considerados

    Estrutura da planilha:
      - Linha 6 (idx 5): COMPRA por mês + TOTAL na última coluna preenchida
      - Linha 7 (idx 6): VENDA  por mês + TOTAL na última coluna preenchida
      - A coluna TOTAL é usada diretamente para maior precisão.
    """
    client = _get_gspread_client()
    if client is None:
        return {}
    try:
        sheet = client.open_by_key(CMV_HISTORICO_ID)
        aba   = sheet.get_worksheet(0)
        rows  = aba.get_all_values()
        if len(rows) < 7:
            return {}

        compra_row = rows[5]   # linha 6: COMPRA
        venda_row  = rows[6]   # linha 7: VENDA

        def _br_to_float(s: str) -> float | None:
            s = s.strip().replace("R$", "").replace(".", "").replace(",", ".").strip()
            try:
                return float(s) if s and s != "-" else None
            except ValueError:
                return None

        # Soma todos os valores mensais (ignora a célula "COMPRA"/"VENDA" e o TOTAL)
        # O TOTAL está na última célula com valor — usamos soma para ser dinâmico
        total_compra = 0.0
        total_venda  = 0.0
        n_meses      = 0

        for c_val, v_val in zip(compra_row[1:], venda_row[1:]):
            c = _br_to_float(c_val)
            v = _br_to_float(v_val)
            if c is not None and v is not None and v > 0:
                # Só acumula se ambos têm valor (evita a coluna TOTAL duplicar)
                # Heurística: TOTAL costuma ser >> qualquer mês; ignora se c > 50k
                # Melhor: para, pois o TOTAL fica na última coluna após os meses
                pass

        # Estratégia mais robusta: soma das colunas mensais excluindo o TOTAL
        # O TOTAL é identificado como a coluna onde venda > 500k (soma de todos)
        compras_mensais = []
        vendas_mensais  = []
        for c_val, v_val in zip(compra_row[1:], venda_row[1:]):
            c = _br_to_float(c_val)
            v = _br_to_float(v_val)
            if c is not None and v is not None and v > 0:
                if v < 500_000:           # exclui a coluna TOTAL (soma total > 500k)
                    compras_mensais.append(c)
                    vendas_mensais.append(v)

        total_compra = sum(compras_mensais)
        total_venda  = sum(vendas_mensais)
        n_meses      = len(compras_mensais)

        if total_venda <= 0:
            return {}

        pct = total_compra / total_venda

        return {
            "pct":          pct,
            "total_compra": total_compra,
            "total_venda":  total_venda,
            "n_meses":      n_meses,
        }
    except Exception:
        return {}


def cmv_pct_historico() -> float | None:
    """
    Retorna o % CMV médio total histórico (total_compra / total_venda).
    Aplicado a qualquer mês — passado ou futuro.
    Retorna None se a planilha não estiver acessível.
    """
    dados = ler_cmv_historico()
    return dados.get("pct")
