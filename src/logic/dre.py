"""
Lógica do DRE — Aureum Joias.

Plano de contas alinhado com a planilha "Plano de Contas" (DRE_ID).
Fontes: Jueri (receita + comissões) + Google Sheets (despesas).
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
# Baseado no Plano de Contas real da planilha DRE.

MAPA_CATEGORIAS: dict[str, str] = {
    # ── 2. Custos Variáveis ──────────────────────────────────────────────────
    "galvânica":            "2.1 CMV",
    "galvanica":            "2.1 CMV",
    "peças em bruto":       "2.1 CMV",
    "compra de peças":      "2.1 CMV",
    "compra de joias":      "2.1 CMV",
    "maletas estojoias":    "2.1 CMV",
    "maletas esto":         "2.1 CMV",
    "estojo":               "2.1 CMV",
    "seven":                "2.1 CMV",
    "anéis brasil":         "2.1 CMV",
    "boleto":               "2.1 CMV",

    "correio":              "2.2 Frete",
    "transportadora":       "2.2 Frete",
    "frete":                "2.2 Frete",
    "motoboy":              "2.2 Frete",

    "imposto":              "2.3 Impostos",
    "simples":              "2.3 Impostos",
    "icms":                 "2.3 Impostos",
    "pis":                  "2.3 Impostos",
    "cofins":               "2.3 Impostos",
    "irpj":                 "2.3 Impostos",

    # 2.4 Comissões — via Jueri, mas também entradas manuais
    "comissão supervisor":  "2.4 Comissões",
    "comissao supervisor":  "2.4 Comissões",

    "taxa cartão":          "2.5 Taxa de Cobrança Cartão",
    "taxa de cobrança":     "2.5 Taxa de Cobrança Cartão",

    "embalagem":            "2.6 Embalagens",

    # ── 4.1 Pró-labore ───────────────────────────────────────────────────────
    "pró-labore":           "4.1 Pró-labore",
    "pro-labore":           "4.1 Pró-labore",
    "prolabore":            "4.1 Pró-labore",

    # 4.2 Encargos do Pró Labore
    "encargo pró":          "4.2 Encargos do Pró Labore",
    "encargo pro":          "4.2 Encargos do Pró Labore",

    # ── 4.3 Salários ─────────────────────────────────────────────────────────
    "salário":              "4.3 Salários",
    "salario":              "4.3 Salários",

    # ── 4.4 Encargos dos Salários ────────────────────────────────────────────
    "inss":                 "4.4 Encargos dos Salários",
    "fgts":                 "4.4 Encargos dos Salários",
    "gps":                  "4.4 Encargos dos Salários",
    "rescisão":             "4.4 Encargos dos Salários",
    "rescisao":             "4.4 Encargos dos Salários",
    "premiação":            "4.4 Encargos dos Salários",
    "premiacao":            "4.4 Encargos dos Salários",
    "plano de saúde":       "4.4 Encargos dos Salários",
    "plano de saude":       "4.4 Encargos dos Salários",
    "13 salário":           "4.4 Encargos dos Salários",
    "13 salario":           "4.4 Encargos dos Salários",
    "férias":               "4.4 Encargos dos Salários",
    "ferias":               "4.4 Encargos dos Salários",

    # ── 4.5 Energia Elétrica ─────────────────────────────────────────────────
    "energia":              "4.5 Energia Elétrica",
    "luz":                  "4.5 Energia Elétrica",
    "conta de luz":         "4.5 Energia Elétrica",

    # ── 4.6 Água ─────────────────────────────────────────────────────────────
    "água":                 "4.6 Água",
    "agua":                 "4.6 Água",

    # ── 4.7 Telefone/Internet ─────────────────────────────────────────────────
    "internet":             "4.7 Telefone/Internet",
    "telefone":             "4.7 Telefone/Internet",
    "celular":              "4.7 Telefone/Internet",

    # ── 4.8 Despesas com Veículos ────────────────────────────────────────────
    "combustível":          "4.8 Despesas com Veículos",
    "combustivel":          "4.8 Despesas com Veículos",
    "seguro veículo":       "4.8 Despesas com Veículos",
    "ipva":                 "4.8 Despesas com Veículos",
    "manutenção veículo":   "4.8 Despesas com Veículos",
    "manutenção veiculo":   "4.8 Despesas com Veículos",

    # ── 4.9 Materiais de Escritório ──────────────────────────────────────────
    "material de escritório": "4.9 Materiais de Escritório",
    "material de escritorio": "4.9 Materiais de Escritório",
    "garrafa":              "4.9 Materiais de Escritório",
    "caneta":               "4.9 Materiais de Escritório",
    "papel":                "4.9 Materiais de Escritório",

    # ── 4.10 Materiais de Limpeza ────────────────────────────────────────────
    "limpeza":              "4.10 Materiais de Limpeza",
    "higiene":              "4.10 Materiais de Limpeza",

    # ── 4.12 Serviços de Terceiros ───────────────────────────────────────────
    "advogado":             "4.12 Serviços de Terceiros",
    "contabilidade":        "4.12 Serviços de Terceiros",
    "contador":             "4.12 Serviços de Terceiros",
    "mensalidade contab":   "4.12 Serviços de Terceiros",
    "assistente virtual":   "4.12 Serviços de Terceiros",
    "desafio do empreendedor": "4.12 Serviços de Terceiros",
    "produto do grupo":     "4.12 Serviços de Terceiros",
    "cursos":               "4.12 Serviços de Terceiros",
    "treinamento":          "4.12 Serviços de Terceiros",
    "mentoria":             "4.12 Serviços de Terceiros",
    "impressgraf":          "4.12 Serviços de Terceiros",
    "gestão de ponto":      "4.12 Serviços de Terceiros",
    "gestao de ponto":      "4.12 Serviços de Terceiros",
    "serviço rh":           "4.12 Serviços de Terceiros",
    "servico rh":           "4.12 Serviços de Terceiros",
    "programador":          "4.12 Serviços de Terceiros",
    "software":             "4.12 Serviços de Terceiros",
    "segurança":            "4.12 Serviços de Terceiros",
    "seguranca":            "4.12 Serviços de Terceiros",

    # ── 4.13 Sindicatos ──────────────────────────────────────────────────────
    "sindicato":            "4.13 Sindicatos",

    # ── 4.14 Associações ─────────────────────────────────────────────────────
    "associação":           "4.14 Associações",
    "associacao":           "4.14 Associações",
    "acii":                 "4.14 Associações",

    # ── 4.15 Despesas com Viagens ────────────────────────────────────────────
    "viagem":               "4.15 Despesas com Viagens",
    "hospedagem":           "4.15 Despesas com Viagens",
    "alimentação viagem":   "4.15 Despesas com Viagens",
    "alimentacao viagem":   "4.15 Despesas com Viagens",
    "passagem":             "4.15 Despesas com Viagens",
    "combustivel viagem":   "4.15 Despesas com Viagens",

    # ── 4.16 IPTU ────────────────────────────────────────────────────────────
    "iptu":                 "4.16 IPTU",

    # ── 4.17 Taxas da Prefeitura ─────────────────────────────────────────────
    "prefeitura":           "4.17 Taxas da Prefeitura",
    "vigilância sanitária": "4.17 Taxas da Prefeitura",
    "vigilancia sanitaria": "4.17 Taxas da Prefeitura",
    "taxa municipal":       "4.17 Taxas da Prefeitura",

    # ── 4.18 Propaganda/Publicidade ──────────────────────────────────────────
    "anúncio":              "4.18 Propaganda/Publicidade",
    "anuncio":              "4.18 Propaganda/Publicidade",
    "meta ads":             "4.18 Propaganda/Publicidade",
    "anúncio meta":         "4.18 Propaganda/Publicidade",
    "anuncio meta":         "4.18 Propaganda/Publicidade",
    "google adwords":       "4.18 Propaganda/Publicidade",
    "tráfego":              "4.18 Propaganda/Publicidade",
    "trafego":              "4.18 Propaganda/Publicidade",
    "gestor de tráfego":    "4.18 Propaganda/Publicidade",
    "gestor de trafego":    "4.18 Propaganda/Publicidade",
    "social midia":         "4.18 Propaganda/Publicidade",
    "social mídia":         "4.18 Propaganda/Publicidade",
    "influenciadora":       "4.18 Propaganda/Publicidade",
    "faixa":                "4.18 Propaganda/Publicidade",
    "doação":               "4.18 Propaganda/Publicidade",
    "doacao":               "4.18 Propaganda/Publicidade",
    "publicidade":          "4.18 Propaganda/Publicidade",
    "propaganda":           "4.18 Propaganda/Publicidade",
    "marketing":            "4.18 Propaganda/Publicidade",

    # ── 4.19 Manutenção do Ativo Fixo ────────────────────────────────────────
    "manutenção show":      "4.19 Manutenção do Ativo Fixo",
    "manutencao show":      "4.19 Manutenção do Ativo Fixo",
    "despesas showroom":    "4.19 Manutenção do Ativo Fixo",
    "reparo":               "4.19 Manutenção do Ativo Fixo",
    "reforma":              "4.19 Manutenção do Ativo Fixo",
    "obra":                 "4.19 Manutenção do Ativo Fixo",

    # ── 4.20 Assinaturas ─────────────────────────────────────────────────────
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
    "sistema assertiva":    "4.20 Assinaturas",
    "spotify":              "4.20 Assinaturas",

    # ── 4.21 Alimentação ─────────────────────────────────────────────────────
    "alimentação":          "4.21 Alimentação",
    "alimentacao":          "4.21 Alimentação",
    "lanche":               "4.21 Alimentação",
    "almoço":               "4.21 Alimentação",
    "almoco":               "4.21 Alimentação",
    "refeição":             "4.21 Alimentação",
    "refeicao":             "4.21 Alimentação",

    # ── 4.22 Vale Refeição ───────────────────────────────────────────────────
    "vale alimentação":     "4.22 Vale Refeição",
    "vale alimentacao":     "4.22 Vale Refeição",
    "vale refeição":        "4.22 Vale Refeição",
    "vale refeicao":        "4.22 Vale Refeição",

    # ── 4.23 Cartório/Correios ───────────────────────────────────────────────
    "cartório":             "4.23 Cartório/Correios",
    "cartorio":             "4.23 Cartório/Correios",

    # ── 4.24 Tarifas Bancárias ───────────────────────────────────────────────
    "tarifa bancária":      "4.24 Tarifas Bancárias",
    "tarifa bancaria":      "4.24 Tarifas Bancárias",
    "taxa bancária":        "4.24 Tarifas Bancárias",
    "taxa bancaria":        "4.24 Tarifas Bancárias",
    "tarifa":               "4.24 Tarifas Bancárias",

    # ── 4.25 Despesas com Juros ──────────────────────────────────────────────
    "juros":                "4.25 Despesas com Juros",
    "empréstimo":           "4.25 Despesas com Juros",
    "emprestimo":           "4.25 Despesas com Juros",
    "multa":                "4.25 Despesas com Juros",
    "anuidade":             "4.25 Despesas com Juros",

    # ── 4.26 Aluguel ─────────────────────────────────────────────────────────
    "aluguel":              "4.26 Aluguel",

    # ── 4.27 Decoração Showroom ──────────────────────────────────────────────
    "decoração":            "4.27 Decoração Showroom",
    "decoracao":            "4.27 Decoração Showroom",
    "tapete":               "4.27 Decoração Showroom",
    "difusor":              "4.27 Decoração Showroom",
    "spray showroom":       "4.27 Decoração Showroom",
    "poltrona":             "4.27 Decoração Showroom",

    # ── 4.28 Fotos ───────────────────────────────────────────────────────────
    "foto":                 "4.28 Fotos",
    "fotografia":           "4.28 Fotos",
    "sessão foto":          "4.28 Fotos",

    # ── 4.29 Eventos ─────────────────────────────────────────────────────────
    "evento":               "4.29 Eventos",
    "comemoração":          "4.29 Eventos",
    "comemoracao":          "4.29 Eventos",
    "festa":                "4.29 Eventos",
    "presente":             "4.29 Eventos",
    "presença":             "4.29 Eventos",

    # ── 6. Receitas não Operacionais ─────────────────────────────────────────
    "receita não operacional": "6. Receitas Não Operacionais",
    "receita extra":        "6. Receitas Não Operacionais",

    # ── 7. Despesas não Operacionais ─────────────────────────────────────────
    "despesa não operacional": "7. Despesas Não Operacionais",

    # ── 8. Investimentos ─────────────────────────────────────────────────────
    "câmera":               "8. Investimentos",
    "camera":               "8. Investimentos",
    "impressora":           "8. Investimentos",
    "notebook":             "8. Investimentos",
    "computador":           "8. Investimentos",
    "móveis":               "8. Investimentos",
    "movéis":               "8. Investimentos",
    "moveis":               "8. Investimentos",
    "ar condicionado":      "8. Investimentos",
    "equipamento":          "8. Investimentos",
    "maquina":              "8. Investimentos",
    "máquina":              "8. Investimentos",
    "veículo":              "8. Investimentos",
    "veiculo":              "8. Investimentos",
    "financiamento":        "8. Investimentos",

    # ── 9. Retirada de Lucros ────────────────────────────────────────────────
    "retirada":             "9. Retirada de Lucros",
    "lucros":               "9. Retirada de Lucros",
    "distribuição":         "9. Retirada de Lucros",
    "distribuicao":         "9. Retirada de Lucros",
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
    "2.8 Outros Custos Variáveis",
    "4.1 Pró-labore",
    "4.2 Encargos do Pró Labore",
    "4.3 Salários",
    "4.4 Encargos dos Salários",
    "4.5 Energia Elétrica",
    "4.6 Água",
    "4.7 Telefone/Internet",
    "4.8 Despesas com Veículos",
    "4.9 Materiais de Escritório",
    "4.10 Materiais de Limpeza",
    "4.11 Depreciação",
    "4.12 Serviços de Terceiros",
    "4.13 Sindicatos",
    "4.14 Associações",
    "4.15 Despesas com Viagens",
    "4.16 IPTU",
    "4.17 Taxas da Prefeitura",
    "4.18 Propaganda/Publicidade",
    "4.19 Manutenção do Ativo Fixo",
    "4.20 Assinaturas",
    "4.21 Alimentação",
    "4.22 Vale Refeição",
    "4.23 Cartório/Correios",
    "4.24 Tarifas Bancárias",
    "4.25 Despesas com Juros",
    "4.26 Aluguel",
    "4.27 Decoração Showroom",
    "4.28 Fotos",
    "4.29 Eventos",
    "4.30 Outros Custos Fixos",
    "4.99 Sem Classificação",
    "6. Receitas Não Operacionais",
    "7. Despesas Não Operacionais",
    "8. Investimentos",
    "9. Retirada de Lucros",
]

# ── Estrutura e ordem do DRE ──────────────────────────────────────────────────

ORDEM_DRE: list[tuple[str, str]] = [
    ("receita_bruta",                "1. Receita Bruta de Vendas"),
    ("2.1 CMV",                      "  2.1 Custo da Mercadoria Vendida"),
    ("2.2 Frete",                    "  2.2 Frete e Logística"),
    ("2.3 Impostos",                 "  2.3 Impostos sobre Vendas"),
    ("2.4 Comissões",                "  2.4 Comissões"),
    ("2.5 Taxa de Cobrança Cartão",  "  2.5 Taxa de Cobrança Cartão"),
    ("2.6 Embalagens",               "  2.6 Embalagens"),
    ("2.7 Perdas",                   "  2.7 Perdas"),
    ("2.8 Outros Custos Variáveis",  "  2.8/2.9 Outros Custos Variáveis"),
    ("margem_contribuicao",          "3. Margem de Contribuição"),
    ("4.1 Pró-labore",               "  4.1 Pró-labore (Retirada Sócios)"),
    ("4.2 Encargos do Pró Labore",   "  4.2 Encargos do Pró Labore"),
    ("4.3 Salários",                 "  4.3 Salários"),
    ("4.4 Encargos dos Salários",    "  4.4 Encargos dos Salários (INSS/FGTS)"),
    ("4.5 Energia Elétrica",         "  4.5 Energia Elétrica"),
    ("4.6 Água",                     "  4.6 Água"),
    ("4.7 Telefone/Internet",        "  4.7 Telefone/Internet"),
    ("4.8 Despesas com Veículos",    "  4.8 Despesas com Veículos"),
    ("4.9 Materiais de Escritório",  "  4.9 Materiais de Escritório"),
    ("4.10 Materiais de Limpeza",    "  4.10 Materiais de Limpeza"),
    ("4.11 Depreciação",             "  4.11 Depreciação"),
    ("4.12 Serviços de Terceiros",   "  4.12 Serviços de Terceiros"),
    ("4.13 Sindicatos",              "  4.13 Sindicatos"),
    ("4.14 Associações",             "  4.14 Associações"),
    ("4.15 Despesas com Viagens",    "  4.15 Despesas com Viagens"),
    ("4.16 IPTU",                    "  4.16 IPTU"),
    ("4.17 Taxas da Prefeitura",     "  4.17 Taxas da Prefeitura"),
    ("4.18 Propaganda/Publicidade",  "  4.18 Propaganda/Publicidade"),
    ("4.19 Manutenção do Ativo Fixo","  4.19 Manutenção do Ativo Fixo"),
    ("4.20 Assinaturas",             "  4.20 Assinaturas"),
    ("4.21 Alimentação",             "  4.21 Alimentação"),
    ("4.22 Vale Refeição",           "  4.22 Vale Refeição"),
    ("4.23 Cartório/Correios",       "  4.23 Cartório/Correios"),
    ("4.24 Tarifas Bancárias",       "  4.24 Tarifas Bancárias"),
    ("4.25 Despesas com Juros",      "  4.25 Despesas com Juros"),
    ("4.26 Aluguel",                 "  4.26 Aluguel"),
    ("4.27 Decoração Showroom",      "  4.27 Decoração Showroom"),
    ("4.28 Fotos",                   "  4.28 Fotos"),
    ("4.29 Eventos",                 "  4.29 Eventos"),
    ("4.30 Outros Custos Fixos",     "  4.30/4.31 Outros Custos Fixos"),
    ("4.99 Sem Classificação",       "  4.99 Sem Classificação ⚠️"),
    ("lucro_operacional",            "5. Lucro Operacional"),
    ("6. Receitas Não Operacionais", "6. Receitas Não Operacionais"),
    ("7. Despesas Não Operacionais", "7. Despesas Não Operacionais"),
    ("8. Investimentos",             "8. Investimentos"),
    ("9. Retirada de Lucros",        "9. Retirada de Lucros"),
    ("lucro_liquido",                "10. Lucro Líquido"),
]

TOTAIS = {"receita_bruta", "margem_contribuicao", "lucro_operacional", "lucro_liquido"}

CUSTOS_VAR = {
    "2.1 CMV", "2.2 Frete", "2.3 Impostos", "2.4 Comissões",
    "2.5 Taxa de Cobrança Cartão", "2.6 Embalagens", "2.7 Perdas",
    "2.8 Outros Custos Variáveis",
}

CUSTOS_FIXOS = {
    cod for cod, _ in ORDEM_DRE
    if cod.startswith("4.") and cod not in TOTAIS
}


# ── Funções principais ────────────────────────────────────────────────────────

def categorizar_despesa(nome: str, custom: dict[str, str] | None = None) -> str:
    """
    Retorna a categoria DRE para o nome da despesa.
    Prioridade: 1) override manual  2) mapa padrão (substring)  3) Sem Classificação
    """
    if custom is None:
        custom = carregar_mapeamento_custom()

    # 1. Override exato pelo nome
    if nome in custom:
        return custom[nome]

    # 2. Substring padrão (case-insensitive)
    nome_lower = nome.lower()
    for chave, cat in MAPA_CATEGORIAS.items():
        if chave in nome_lower:
            return cat

    return "4.99 Sem Classificação"


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

    # Comissões vindas do Jueri
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
