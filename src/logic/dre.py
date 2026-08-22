"""
Lógica do DRE (Demonstração do Resultado do Exercício) — Aureum Joias.

Fontes de dados:
  - Receita e Comissões: cache Jueri (pedidos baixados + pré-baixa)
  - Despesas: Google Sheets (planilha financeira, leitura ao vivo)

Mapeamento de despesas → categorias DRE feito automaticamente por nome.
"""

from __future__ import annotations
from datetime import date
from typing import Optional

# ── Mapeamento despesa → categoria DRE ───────────────────────────────────────
# Chave: substring do nome da despesa (case-insensitive)
# Valor: categoria DRE

MAPA_CATEGORIAS: dict[str, str] = {
    # ── 2. Custos Variáveis ──────────────────────────────────────────────────
    "imposto":              "2.3 Impostos",
    "simples":              "2.3 Impostos",
    "icms":                 "2.3 Impostos",
    "pis":                  "2.3 Impostos",
    "cofins":               "2.3 Impostos",
    "irpj":                 "2.3 Impostos",
    "correio":              "2.2 Frete",
    "transportadora":       "2.2 Frete",
    "frete":                "2.2 Frete",
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
    "entregas motoboy":     "2.2 Frete",
    "motoboy":              "2.2 Frete",

    # ── 4. Custos Fixos — Pessoal ────────────────────────────────────────────
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

    # ── 4. Custos Fixos — Utilidades ─────────────────────────────────────────
    "energia":              "4.5 Energia Elétrica",
    "luz":                  "4.5 Energia Elétrica",
    "internet":             "4.7 Telefone/Internet",
    "telefone":             "4.7 Telefone/Internet",

    # ── 4. Custos Fixos — Serviços de Terceiros ──────────────────────────────
    "advogado":             "4.12 Serviços de Terceiros",
    "contabilidade":        "4.12 Serviços de Terceiros",
    "contador":             "4.12 Serviços de Terceiros",
    "mentoria":             "4.12 Serviços de Terceiros",
    "rh ":                  "4.12 Serviços de Terceiros",

    # ── 4. Custos Fixos — Marketing ──────────────────────────────────────────
    "anúncio":              "4.16 Marketing/Propaganda",
    "anuncio":              "4.16 Marketing/Propaganda",
    "meta":                 "4.16 Marketing/Propaganda",
    "desafio do empreendedor": "4.16 Marketing/Propaganda",
    "tráfego":              "4.16 Marketing/Propaganda",
    "trafego":              "4.16 Marketing/Propaganda",

    # ── 4. Custos Fixos — Aluguel ────────────────────────────────────────────
    "aluguel":              "4.31 Aluguel",

    # ── 4. Custos Fixos — Assinaturas/Software ───────────────────────────────
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

    # ── 4. Custos Fixos — Viagens/Alimentação ────────────────────────────────
    "alimentação viagem":   "4.22 Viagens",
    "hospedagem":           "4.22 Viagens",
    "viagem":               "4.22 Viagens",

    # ── 4. Custos Fixos — Manutenção/Despesas Operacionais ───────────────────
    "despesas showroom":    "4.19 Manutenção",
    "manutenção":           "4.19 Manutenção",
    "acii":                 "4.18 Sindicatos/Associações",
    "sindicato":            "4.18 Sindicatos/Associações",

    # ── 7. Despesas Não Operacionais ─────────────────────────────────────────
    "juros":                "7. Despesas Não Operacionais",
    "empréstimo":           "7. Despesas Não Operacionais",
    "emprestimo":           "7. Despesas Não Operacionais",
    "anuidade cartão":      "7. Despesas Não Operacionais",
    "multa":                "7. Despesas Não Operacionais",

    # ── 8. Investimentos (parcelas de equipamentos/móveis) ───────────────────
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

# Ordem das categorias no DRE (para exibição)
ORDEM_DRE: list[tuple[str, str]] = [
    # (código, rótulo de exibição)
    ("receita_bruta",                   "1. Receita Bruta de Vendas"),
    ("2.1 CMV",                         "  2.1 Custo da Mercadoria Vendida"),
    ("2.2 Frete",                       "  2.2 Frete e Logística"),
    ("2.3 Impostos",                    "  2.3 Impostos sobre Vendas"),
    ("2.4 Comissões",                   "  2.4 Comissões"),
    ("2.5 Taxa de Cobrança Cartão",     "  2.5 Taxas de Cartão"),
    ("2.6 Embalagens",                  "  2.6 Embalagens"),
    ("2.7 Perdas",                      "  2.7 Perdas"),
    ("margem_contribuicao",             "3. Margem de Contribuição"),
    ("4.1 Pró-labore",                  "  4.1 Pró-labore"),
    ("4.2 Salários",                    "  4.2 Salários"),
    ("4.3 Encargos Sociais",            "  4.3 Encargos Sociais (INSS/FGTS)"),
    ("4.4 Benefícios",                  "  4.4 Benefícios"),
    ("4.5 Energia Elétrica",            "  4.5 Energia Elétrica"),
    ("4.7 Telefone/Internet",           "  4.7 Telefone/Internet"),
    ("4.12 Serviços de Terceiros",      "  4.12 Serviços de Terceiros"),
    ("4.16 Marketing/Propaganda",       "  4.16 Marketing e Propaganda"),
    ("4.18 Sindicatos/Associações",     "  4.18 Sindicatos/Associações"),
    ("4.19 Manutenção",                 "  4.19 Manutenção"),
    ("4.20 Assinaturas",                "  4.20 Assinaturas e Softwares"),
    ("4.22 Viagens",                    "  4.22 Viagens e Alimentação"),
    ("4.31 Aluguel",                    "  4.31 Aluguel"),
    ("lucro_operacional",               "5. Lucro Operacional"),
    ("6. Receitas Não Operacionais",    "6. Receitas Não Operacionais"),
    ("7. Despesas Não Operacionais",    "7. Despesas Não Operacionais"),
    ("8. Investimentos",                "8. Investimentos"),
    ("9. Retirada de Lucros",           "9. Retirada de Lucros"),
    ("lucro_liquido",                   "10. Lucro Líquido"),
]

TOTAIS = {"receita_bruta", "margem_contribuicao", "lucro_operacional", "lucro_liquido"}
CUSTOS_VARIAVEIS = {"2.1 CMV", "2.2 Frete", "2.3 Impostos", "2.4 Comissões",
                    "2.5 Taxa de Cobrança Cartão", "2.6 Embalagens", "2.7 Perdas"}
CUSTOS_FIXOS = {c for c, _ in ORDEM_DRE
                if c.startswith("4.") and c not in TOTAIS}


def categorizar_despesa(nome: str) -> str:
    """
    Retorna a categoria DRE para um nome de despesa.
    Usa matching por substring (case-insensitive).
    Padrão: '4.99 Outros' quando não encontrar match.
    """
    nome_lower = nome.lower()
    for chave, categoria in MAPA_CATEGORIAS.items():
        if chave in nome_lower:
            return categoria
    return "4.99 Outros"


def calcular_dre(
    receita_bruta: float,
    comissoes: float,
    despesas: list[dict],
) -> dict[str, float]:
    """
    Monta o DRE a partir dos dados brutos.

    despesas: lista de dicts com chaves 'nome', 'realizado'
    Retorna dict {categoria: valor} com os totalizadores calculados.
    """
    valores: dict[str, float] = {}

    # 1. Receita
    valores["receita_bruta"] = receita_bruta

    # 2. Custos variáveis da planilha
    for desp in despesas:
        cat = categorizar_despesa(desp["nome"])
        valores[cat] = valores.get(cat, 0.0) + desp["realizado"]

    # 2.4 Comissões vêm do Jueri
    valores["2.4 Comissões"] = valores.get("2.4 Comissões", 0.0) + comissoes

    # 3. Margem de Contribuição = Receita - Custos Variáveis
    total_cv = sum(valores.get(c, 0.0) for c in CUSTOS_VARIAVEIS)
    valores["margem_contribuicao"] = receita_bruta - total_cv

    # 5. Lucro Operacional = Margem - Custos Fixos
    total_cf = sum(valores.get(c, 0.0) for c in CUSTOS_FIXOS)
    valores["lucro_operacional"] = valores["margem_contribuicao"] - total_cf

    # 10. Lucro Líquido
    rec_nao_op  = valores.get("6. Receitas Não Operacionais", 0.0)
    desp_nao_op = valores.get("7. Despesas Não Operacionais", 0.0)
    investim    = valores.get("8. Investimentos", 0.0)
    retiradas   = valores.get("9. Retirada de Lucros", 0.0)
    valores["lucro_liquido"] = (
        valores["lucro_operacional"]
        + rec_nao_op
        - desp_nao_op
        - investim
        - retiradas
    )

    return valores


def mes_esta_fechado(mes: int, ano: int) -> bool:
    """Retorna True se o mês já passou (não é o mês atual nem futuro)."""
    hoje = date.today()
    return (ano, mes) < (hoje.year, hoje.month)


def nome_aba_financeiro(mes: int, ano: int) -> str:
    """Retorna o nome da aba na planilha financeira, ex: 'Ago-26'."""
    MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    return f"{MESES[mes - 1]}-{str(ano)[2:]}"
