"""
Lógica do DRE — Aureum Joias.

Fontes: Jueri (receita + comissões) + Google Sheets (despesas).
Mapeamento automático por nome, com override manual salvo em JSON.
"""

from __future__ import annotations
import json
from datetime import date
from pathlib import Path

# ── Arquivo de mapeamento customizado ─────────────────────────────────────────

_CUSTOM_PATH = Path(__file__).parent.parent.parent / ".streamlit" / "dre_mapeamento_custom.json"


def carregar_mapeamento_custom() -> dict[str, str]:
    """Retorna {nome_exato_despesa: categoria} salvo pelo usuário."""
    try:
        if _CUSTOM_PATH.exists():
            return json.loads(_CUSTOM_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def salvar_mapeamento_custom(mapa: dict[str, str]) -> None:
    """Persiste o mapeamento customizado em disco."""
    _CUSTOM_PATH.write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Mapeamento padrão (substring, case-insensitive) ───────────────────────────

MAPA_CATEGORIAS: dict[str, str] = {
    # 2. Custos Variáveis
    "imposto":              "2.3 Impostos",
    "simples":              "2.3 Impostos",
    "icms":                 "2.3 Impostos",
    "correio":              "2.2 Frete",
    "transportadora":       "2.2 Frete",
    "frete":                "2.2 Frete",
    "motoboy":              "2.2 Frete",
    "embalagem":            "2.6 Embalagens",
    "taxa cartão":          "2.5 Taxa de Cobrança Cartão",
    "taxa de cobrança":     "2.5 Taxa de Cobrança Cartão",
    "galvânica":            "2.1 CMV",
    "galvanica":            "2.1 CMV",
    "peças em bruto":       "2.1 CMV",
    "compra de peças":      "2.1 CMV",
    "compra de joias":      "2.1 CMV",
    "maletas estojoias":    "2.1 CMV",
    "estojo":               "2.1 CMV",
    "seven":                "2.1 CMV",
    "anéis brasil":         "2.1 CMV",
    "boleto":               "2.1 CMV",
    # 4. Pessoal
    "pró-labore":           "4.1 Pró-labore",
    "pro-labore":           "4.1 Pró-labore",
    "prolabore":            "4.1 Pró-labore",
    "salário":              "4.2 Salários",
    "salario":              "4.2 Salários",
    "gestor de tráfego":    "4.2 Salários",
    "assistente virtual":   "4.2 Salários",
    "inss":                 "4.3 Encargos Sociais",
    "fgts":                 "4.3 Encargos Sociais",
    "vale alimentação":     "4.4 Benefícios",
    "vale refeição":        "4.4 Benefícios",
    # 4. Utilidades
    "energia":              "4.5 Energia Elétrica",
    "luz":                  "4.5 Energia Elétrica",
    "internet":             "4.7 Telefone/Internet",
    "telefone":             "4.7 Telefone/Internet",
    # 4. Serviços de Terceiros
    "advogado":             "4.12 Serviços de Terceiros",
    "contabilidade":        "4.12 Serviços de Terceiros",
    "contador":             "4.12 Serviços de Terceiros",
    "mentoria":             "4.12 Serviços de Terceiros",
    # 4. Marketing
    "anúncio":              "4.16 Marketing/Propaganda",
    "anuncio":              "4.16 Marketing/Propaganda",
    "meta":                 "4.16 Marketing/Propaganda",
    "desafio do empreendedor": "4.16 Marketing/Propaganda",
    "tráfego":              "4.16 Marketing/Propaganda",
    "trafego":              "4.16 Marketing/Propaganda",
    # 4. Aluguel
    "aluguel":              "4.31 Aluguel",
    # 4. Assinaturas
    "jueri":                "4.20 Assinaturas",
    "assinatura":           "4.20 Assinaturas",
    "canva":                "4.20 Assinaturas",
    "google drive":         "4.20 Assinaturas",
    "google workspace":     "4.20 Assinaturas",
    "icloud":               "4.20 Assinaturas",
    "capcut":               "4.20 Assinaturas",
    "carbon":               "4.20 Assinaturas",
    "respondi":             "4.20 Assinaturas",
    "claude":               "4.20 Assinaturas",
    "assertiva":            "4.20 Assinaturas",
    "software":             "4.20 Assinaturas",
    # 4. Viagens
    "alimentação viagem":   "4.22 Viagens",
    "hospedagem":           "4.22 Viagens",
    "viagem":               "4.22 Viagens",
    # 4. Manutenção
    "despesas showroom":    "4.19 Manutenção",
    "manutenção":           "4.19 Manutenção",
    "acii":                 "4.18 Sindicatos/Associações",
    "sindicato":            "4.18 Sindicatos/Associações",
    # 7. Não Operacionais
    "juros":                "7. Despesas Não Operacionais",
    "empréstimo":           "7. Despesas Não Operacionais",
    "emprestimo":           "7. Despesas Não Operacionais",
    "anuidade":             "7. Despesas Não Operacionais",
    "multa":                "7. Despesas Não Operacionais",
    # 8. Investimentos
    "câmera":               "8. Investimentos",
    "camera":               "8. Investimentos",
    "impressora":           "8. Investimentos",
    "notebook":             "8. Investimentos",
    "móveis":               "8. Investimentos",
    "moveis":               "8. Investimentos",
    "poltrona":             "8. Investimentos",
    "ar condicionado":      "8. Investimentos",
    "tapete":               "8. Investimentos",
    "equipamento":          "8. Investimentos",
}

# ── Lista de categorias disponíveis (para o editor) ───────────────────────────

CATEGORIAS_DISPONIVEIS: list[str] = [
    "2.1 CMV",
    "2.2 Frete",
    "2.3 Impostos",
    "2.4 Comissões",
    "2.5 Taxa de Cobrança Cartão",
    "2.6 Embalagens",
    "2.7 Perdas",
    "4.1 Pró-labore",
    "4.2 Salários",
    "4.3 Encargos Sociais",
    "4.4 Benefícios",
    "4.5 Energia Elétrica",
    "4.7 Telefone/Internet",
    "4.12 Serviços de Terceiros",
    "4.16 Marketing/Propaganda",
    "4.18 Sindicatos/Associações",
    "4.19 Manutenção",
    "4.20 Assinaturas",
    "4.22 Viagens",
    "4.31 Aluguel",
    "4.99 Outros",
    "6. Receitas Não Operacionais",
    "7. Despesas Não Operacionais",
    "8. Investimentos",
    "9. Retirada de Lucros",
]

# ── Estrutura e ordem do DRE ──────────────────────────────────────────────────

ORDEM_DRE: list[tuple[str, str]] = [
    ("receita_bruta",               "1. Receita Bruta de Vendas"),
    ("2.1 CMV",                     "  2.1 Custo da Mercadoria Vendida"),
    ("2.2 Frete",                   "  2.2 Frete e Logística"),
    ("2.3 Impostos",                "  2.3 Impostos sobre Vendas"),
    ("2.4 Comissões",               "  2.4 Comissões"),
    ("2.5 Taxa de Cobrança Cartão", "  2.5 Taxas de Cartão"),
    ("2.6 Embalagens",              "  2.6 Embalagens"),
    ("2.7 Perdas",                  "  2.7 Perdas"),
    ("margem_contribuicao",         "3. Margem de Contribuição"),
    ("4.1 Pró-labore",              "  4.1 Pró-labore"),
    ("4.2 Salários",                "  4.2 Salários"),
    ("4.3 Encargos Sociais",        "  4.3 Encargos Sociais (INSS/FGTS)"),
    ("4.4 Benefícios",              "  4.4 Benefícios"),
    ("4.5 Energia Elétrica",        "  4.5 Energia Elétrica"),
    ("4.7 Telefone/Internet",       "  4.7 Telefone/Internet"),
    ("4.12 Serviços de Terceiros",  "  4.12 Serviços de Terceiros"),
    ("4.16 Marketing/Propaganda",   "  4.16 Marketing e Propaganda"),
    ("4.18 Sindicatos/Associações", "  4.18 Sindicatos/Associações"),
    ("4.19 Manutenção",             "  4.19 Manutenção"),
    ("4.20 Assinaturas",            "  4.20 Assinaturas e Softwares"),
    ("4.22 Viagens",                "  4.22 Viagens e Alimentação"),
    ("4.31 Aluguel",                "  4.31 Aluguel"),
    ("4.99 Outros",                 "  4.99 Outros"),
    ("lucro_operacional",           "5. Lucro Operacional"),
    ("6. Receitas Não Operacionais","6. Receitas Não Operacionais"),
    ("7. Despesas Não Operacionais","7. Despesas Não Operacionais"),
    ("8. Investimentos",            "8. Investimentos"),
    ("9. Retirada de Lucros",       "9. Retirada de Lucros"),
    ("lucro_liquido",               "10. Lucro Líquido"),
]

TOTAIS       = {"receita_bruta", "margem_contribuicao", "lucro_operacional", "lucro_liquido"}
CUSTOS_VAR   = {"2.1 CMV","2.2 Frete","2.3 Impostos","2.4 Comissões",
                "2.5 Taxa de Cobrança Cartão","2.6 Embalagens","2.7 Perdas"}
CUSTOS_FIXOS = {c for c, _ in ORDEM_DRE
                if c.startswith("4.") and c not in TOTAIS}


# ── Funções principais ────────────────────────────────────────────────────────

def categorizar_despesa(nome: str, custom: dict[str, str] | None = None) -> str:
    """
    Retorna a categoria DRE para o nome da despesa.
    Prioridade: 1) override manual  2) mapa padrão (substring)  3) Outros
    """
    if custom is None:
        custom = carregar_mapeamento_custom()

    # 1. Override exato pelo nome
    if nome in custom:
        return custom[nome]

    # 2. Substring padrão
    nome_lower = nome.lower()
    for chave, cat in MAPA_CATEGORIAS.items():
        if chave in nome_lower:
            return cat

    return "4.99 Outros"


def calcular_dre(
    receita_bruta: float,
    comissoes: float,
    despesas: list[dict],
    custom: dict[str, str] | None = None,
) -> dict[str, float]:
    """Monta o DRE (realizado) a partir dos dados brutos. Compat. legado."""
    real, _ = calcular_dre_completo(receita_bruta, comissoes, despesas, custom)
    return real


def calcular_dre_completo(
    receita_bruta: float,
    comissoes: float,
    despesas: list[dict],
    custom: dict[str, str] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Retorna (dre_realizado, dre_planejado).
    Cada dict mapeia codigo_categoria → valor em R$.
    """
    if custom is None:
        custom = carregar_mapeamento_custom()

    real: dict[str, float] = {"receita_bruta": receita_bruta}
    plan: dict[str, float] = {"receita_bruta": receita_bruta}

    for desp in despesas:
        cat = categorizar_despesa(desp["nome"], custom)
        real[cat] = real.get(cat, 0.0) + float(desp.get("realizado") or 0)
        plan[cat] = plan.get(cat, 0.0) + float(desp.get("previsto") or 0)

    # Comissões (vindas do Jueri; só em realizado)
    real["2.4 Comissões"] = real.get("2.4 Comissões", 0.0) + comissoes
    plan["2.4 Comissões"] = plan.get("2.4 Comissões", 0.0) + comissoes

    for d in (real, plan):
        total_cv = sum(d.get(c, 0.0) for c in CUSTOS_VAR)
        d["margem_contribuicao"] = d["receita_bruta"] - total_cv

        total_cf = sum(d.get(c, 0.0) for c in CUSTOS_FIXOS)
        d["lucro_operacional"] = d["margem_contribuicao"] - total_cf

        d["lucro_liquido"] = (
            d["lucro_operacional"]
            + d.get("6. Receitas Não Operacionais", 0.0)
            - d.get("7. Despesas Não Operacionais", 0.0)
            - d.get("8. Investimentos", 0.0)
            - d.get("9. Retirada de Lucros", 0.0)
        )

    return real, plan


def mes_esta_fechado(mes: int, ano: int) -> bool:
    hoje = date.today()
    return (ano, mes) < (hoje.year, hoje.month)


def nome_aba_financeiro(mes: int, ano: int) -> str:
    MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    return f"{MESES[mes - 1]}-{str(ano)[2:]}"
