# Regras de Negócio — Sistema de Gestão Aureum Joias

> **Para quem é este documento**
> Descreve como o sistema funciona, quais regras estão implementadas e o que cada tela e aba busca alcançar. A linguagem é direta para facilitar o entendimento por qualquer pessoa da equipe — e também serve de referência para construir prompts de IA sobre o sistema.

---

## Contexto Geral

A Aureum Joias trabalha com o modelo de **consignação por maleta**: uma supervisora é responsável por uma equipe de revendedoras. Cada revendedora recebe uma maleta com joias e tem um prazo para devolver o dinheiro das vendas (o "acerto"). O sistema acompanha todo esse ciclo — desde a saída da maleta até o fechamento do pedido — e gera alertas, rankings e relatórios para as supervisoras e para a administração.

**Origem dos dados:** ERP Jueri (API externa). Os dados são sincronizados para o Supabase (cache persistente) e depois carregados na memória do Streamlit.

**Quem usa o sistema:**
- **Admin** — acesso total a todas as telas
- **Supervisora** — vê apenas sua equipe em "Revendedoras" e "Controle de Acertos"
- **Dashboard** — modo TV, sem login manual, exibe painel automático
- **Marketing** — acessa apenas a tela de marketing

---

## Glossário de Termos

| Termo | Significado |
|---|---|
| **Maleta** | Conjunto de joias enviado à revendedora em consignação |
| **Pedido** | Registro do envio de uma maleta. Pode estar "Aberto" (ativo) ou "Baixado" (fechado/acertado) |
| **Acerto** | Devolução do dinheiro pela revendedora ao final do prazo |
| **Pré-baixa** | Valor parcial já registrado em um pedido ainda aberto (sinaliza intenção de pagamento) |
| **Data de acerto** | Data prevista para o acerto, registrada no Jueri |
| **Data de baixa** | Data real em que o pedido foi fechado no Jueri |
| **Baixado** | Pedido encerrado — a revendedora já devolveu o valor |
| **Aberto** | Pedido em curso — a maleta ainda está com a revendedora |
| **Competência** | Mês ao qual uma venda é atribuída para fins de relatório |
| **Nível** | Classificação da revendedora: Pérola, Ouro ou Diamante — definida pela quantidade de peças na maleta |
| **Supervisora** | Líder de equipe que gerencia um grupo de revendedoras |

---

## Regra de Competência (central para quase tudo)

Esta regra define a qual mês uma venda pertence e é usada em todas as telas:

- **Pedido Baixado** → a venda entra no mês da `data_baixa` (data real do acerto). Valor usado: `valor_total`.
- **Pedido Aberto** → a venda entra no mês da `data_acerto` (data prevista). Valor usado: `valor_pre_baixa` (parcial).

> **Em termos simples:** um pedido fechado em agosto conta em agosto. Um pedido aberto com acerto previsto para agosto também aparece em agosto, mas com o valor parcial que a revendedora já informou — pode mudar.

---

## Tela: Dashboard (Admin)

**Objetivo:** Visão executiva rápida do negócio.

### O que exibe:
- Total de produtos ativos no catálogo
- Quantidade de produtos em estoque crítico (abaixo do mínimo cadastrado)
- Revendedoras ativas (status ativo no Jueri)
- Pedidos baixados nos últimos 30 dias

### Alerta automático:
Se houver produtos críticos, um banner vermelho aparece sugerindo acessar "Programação de Compras".

### Ticket médio por supervisora (últimos 30 dias):
Calculado como: `total vendido ÷ número de pedidos baixados` por supervisora. Exibido em cards e tabela.

---

## Tela: Estoque

**Objetivo:** Ver o que há em estoque físico e o que está na rua (dentro das maletas das revendedoras), identificar produtos críticos e os mais vendidos.

### Regras de situação por produto:

| Situação | Condição |
|---|---|
| 🔴 Crítico | Quantidade em estoque < estoque mínimo cadastrado |
| 🟡 Só na rua | Estoque físico = 0, mas há unidades em maletas abertas |
| ✅ OK | Tem em estoque físico e também na rua |
| ✅ Em estoque | Tem em estoque físico, nada na rua |
| ⚫ Zerado | Nada em estoque, nada na rua |

### Cálculo de "Na rua":
Soma de todos os itens de pedidos **abertos**, buscados no Jueri por pedido individualmente.

### Categoria:
Obtida do Jueri. Se não houver categoria registrada, o sistema infere pela descrição do produto usando palavras-chave (ex: "brinco", "colar", "anel").

### Abas da tela de Estoque:
1. **Visão Geral** — tabela completa com todos os produtos, filtros por categoria e situação
2. **Mais Vendidos** — ranking dos estilos com maior saída no período selecionado (histórico configurável)
3. **Análise ABC** — classifica estilos por volume de vendas: A (top 80%), B (80–95%), C (demais)

---

## Tela: Programação de Compras

**Objetivo:** Gerar uma sugestão de quantas peças comprar por estilo, categoria e cor, levando em conta o ritmo de vendas, o estoque atual e a quantidade de novas revendedoras esperadas.

### Parâmetros configuráveis:
- **Dias de cobertura:** quantos dias o estoque deve durar após a compra (padrão: 60)
- **Dias de histórico:** período usado para calcular a média de vendas (padrão: 90)
- **Lead time:** dias até a mercadoria chegar após o pedido (padrão: 14)
- **Novas revendedoras:** número estimado de novas entradas para o mês

### Como o estilo é definido:
O sistema agrupa produtos com a mesma base de nome + cor (campo `cor` do Jueri — Prata, Dourado ou Rosê). Tamanhos, materiais e preposições são ignorados na comparação.

### Fórmula de compra:
```
Mínimo recomendado = média_diária × lead_time × 1,5  (buffer de 50%)
A comprar = (média_diária × dias_cobertura) − disponível + mínimo
```

onde `disponível = em estoque + na rua`.

### Ajuste pela Curva ABC:
- **Curva A** (top 80% de vendas): usa 100% dos dias de cobertura
- **Curva B** (80–95%): usa 75% dos dias de cobertura
- **Curva C** (restante): usa 50% dos dias de cobertura

### Novas revendedoras:
As peças extras para novas revendedoras são distribuídas entre as categorias proporcionalmente ao volume histórico de vendas de cada categoria. Padrão: 40 peças por nova revendedora.

### Status de compra:

| Status | Condição |
|---|---|
| 🔴 Crítico | Disponível < mínimo recomendado E há quantidade a comprar |
| 🟡 Comprar A | Curva A com quantidade a comprar |
| 🟢 Planejar | Curva B ou C com quantidade a comprar |
| ✅ OK | Não precisa comprar agora |

### Abas da tela de Compras:
1. **Resumo por Categoria** — uma linha por categoria com totais, distribuição ABC e novas revendedoras
2. **Detalhe por Estilo** — uma linha por modelo+cor com sugestão de compra individual
3. **Top Vendidos** — ranking dos estilos mais vendidos por categoria no período

---

## Tela: Revendedoras

**Objetivo:** Centro de controle da equipe de revendedoras. Aqui se acompanha o desempenho mensal, os níveis, os alertas de risco, o controle de premiações e muito mais.

### Mínimo de permanência:
Toda revendedora precisa vender ao menos **R$ 300,00 por mês** para permanecer na equipe. Esse valor é o piso universal — independente do nível.

### Sistema de Níveis:

| Nível | Peças na maleta | Venda mínima do nível |
|---|---|---|
| 💎 Diamante | 80 a 500 peças | R$ 2.500,00 |
| 🥇 Ouro | 55 a 79 peças | R$ 1.000,00 |
| 🔮 Pérola | 40 a 54 peças | R$ 300,00 |

> O nível é definido pela **quantidade de peças na maleta** no momento do pedido, não pelo valor vendido.
> Em pedidos já fechados (Baixados), usa-se `quantidade_antes_baixa` (peças originais), não `quantidade` (que pode refletir só o que foi vendido).

### Tamanho da próxima maleta (por nível e venda):

**Pérola:**
- vendas > R$500: próxima maleta com 45 peças
- vendas ≤ R$500: próxima maleta com 40 peças

**Ouro:**
- vendas ≤ R$1.500: 55 peças
- vendas ≤ R$1.800: 60 peças
- vendas ≤ R$2.000: 65 peças
- vendas > R$2.000: 75 peças

**Diamante:**
- vendas > R$2.500: próxima maleta com 100 peças
- vendas ≤ R$2.500: próxima maleta com 90 peças

### Limiar de subida de nível:

| Nível atual | Venda necessária para subir |
|---|---|
| Pérola → Ouro | R$ 1.000,00 |
| Ouro → Diamante | R$ 2.500,00 |

---

### Abas da tela de Revendedoras:

#### Aba: Competência
**O que busca:** Visão geral do desempenho de todas as revendedoras no mês selecionado, separadas por supervisora.

- Agrupa pedidos pela regra de competência (data_baixa para Baixados, data_acerto para Abertos)
- Mostra: total baixado, pré-baixa, total (soma dos dois), número de pedidos
- Sinaliza riscos:
  - 🔴 Sem vendas: total = R$0
  - 🟡 Abaixo do mínimo: total > 0 mas < R$300
  - 🟢 OK: total ≥ R$300
- Exibe tabela por supervisora com expansão para ver cada revendedora individualmente
- Promissórias: identifica revendedoras que pagaram com promissória no mês (sinalizando risco de inadimplência)
- Pedidos com baixa zero: pedidos fechados com valor = R$0 (anomalias)
- Pedidos sem pré-baixa: pedidos abertos com acerto no mês mas sem nenhum valor registrado

#### Aba: Maletas em Aberto
**O que busca:** Monitorar as maletas que ainda estão com as revendedoras, identificando quem está atrasada ou com ritmo abaixo do esperado.

- Pedidos abertos classificados em faixas de tempo desde a criação
- Calcula a **média de vendas dos últimos 3 meses** de cada revendedora como ritmo esperado. Para revendedoras sem histórico, usa R$300 como referência
- Níveis de risco:
  - 🔴 Sem vendas: pré-baixa = R$0
  - 🟠 Abaixo do mínimo: pré-baixa < R$300
  - 🟡 Abaixo do ritmo: pré-baixa < 90% da média histórica
  - 🟢 No ritmo: pré-baixa ≥ 90% da média histórica

#### Aba: Níveis
**O que busca:** Ver em qual nível cada revendedora está e quais ações tomar.

- Lista todas as revendedoras com pedido no mês, separando "Baixado (fechado)" e "Em aberto"
- Quando há múltiplos pedidos do mesmo tipo para a mesma revendedora: o nível é definido pelo pedido com **mais peças**, e as vendas são **somadas**
- Exibe: nível, peças na maleta, vendas do mês, mínimo necessário para o nível, status

#### Aba: Subindo de Nível
**O que busca:** Identificar revendedoras próximas de atingir o próximo nível para estimular a chegada.

- Mostra revendedoras com vendas ≥ 75% do limiar do próximo nível
- Situação:
  - ✅ Já atingiu a meta: vendas já ultrapassaram o limiar
  - 🔜 Próxima de subir: entre 75% e 100% do limiar
- Exibe quanto falta e quantas peças teria na próxima maleta

#### Aba: Risco de Rebaixamento
**O que busca:** Antecipar quais revendedoras estão em trajetória de queda e podem perder o nível no mês seguinte.

- Analisa 3 meses: M-2, M-1 e mês atual (M0)
- Projeção para o mês seguinte:
  - 🔴 Risco de rebaixamento: M-1 **e** M0 ambos abaixo do mínimo do nível
  - 🟠 Atenção — tendência negativa: M-2 **e** M-1 abaixo (mas M0 ainda em curso)
  - 🟡 Monitorar: apenas M0 abaixo
- Só exibe revendedoras com pelo menos 1 mês abaixo do mínimo

#### Aba: Premiações
**O que busca:** Controlar quem ganhou os prêmios do mês, com suporte a múltiplos critérios.

**Colar personalizado (regra fixa):**
- Revendedora nova cujo **primeiro pedido** tem valor > R$1.000,00
- "Primeira maleta boa" — independente de meta mensal configurada
- Status:
  - ✅ Pedido finalizado: ganhou o colar (confirmado)
  - 📊 Pedido em aberto: pode ganhar se o pedido fechar no prazo

**Metas mensais (multi-tier):**
- O admin configura até N metas por mês, cada uma com valor e prêmio
- A partir da 2ª meta, pode-se marcar "acumula": quem atinge a Meta 2 também ganha o prêmio da Meta 1
- Para cada meta, o sistema classifica as revendedoras em:
  - **Ganhadora confirmada:** valor baixado (pedido fechado) já ≥ meta
  - **Potencial ganhadora:** total (baixado + pré-baixa) ≥ meta, mas ainda há pedido em aberto
  - **Próxima da meta** (exibido apenas para Meta 1): pré-baixa entre 70% e 99% da meta, sem pedido baixado
- Admin pode marcar o prêmio como "entregue" para cada ganhadora

#### Aba: Acompanhamento Individual
**O que busca:** Ver o histórico completo de uma revendedora específica para entender sua trajetória.

- Busca revendedoras pelo nome (busca parcial)
- Exibe todos os pedidos com valores e datas
- Calcula ticket médio: `total vendido ÷ número de acertos (maletas)`

---

## Tela: Controle de Acertos

**Objetivo:** Agendar e acompanhar os acertos (devolução das vendas) de cada pedido aberto.

### Como funciona:

Cada pedido aberto tem uma `data_acerto` (prazo previsto no Jueri). O sistema cruza isso com os agendamentos registrados pelo admin para criar uma visão de agenda.

### Situações possíveis de um acerto:

| Situação | Condição |
|---|---|
| 🔴 Vencido | Pedido aberto com data_acerto anterior a hoje e sem agendamento |
| 📅 Agendado | Tem data de agendamento registrada |
| ⬜ A agendar | Data_acerto futura, sem agendamento ainda |
| ✅ Realizado | Pedido baixado (fechado) |
| ⚠️ Atrasou Xd | Pedido baixado com data_baixa posterior à data_acerto (atrasou X dias) |

### Escopo dos pedidos mostrados:
- Baixados: apenas os dos últimos 90 dias
- Abertos: apenas os com data_acerto nos últimos 3 meses (evita listar pedidos muito antigos)

### Agendamento:
O admin registra para cada pedido:
- **Data agendada** — quando o acerto vai acontecer
- **Forma:** Presencial 🏪, Correios 📮, Disk Tenha 🚗, Motoboy 🏍️
- **Hora** e **Observação** (opcional)
- **Data de envio da maleta** — quando a maleta foi despachada

### Visão semanal:
Resumo da próxima semana mostrando total de acertos, quantos já agendados e quantos ainda a agendar.

---

## Tela: Entradas e Saídas

**Objetivo:** Entender o fluxo da equipe — quem entrou (recebeu a primeira maleta) e quem saiu (fechou o último pedido sem continuar) mês a mês.

### Regra de Entrada:
Uma revendedora "entra" quando recebe uma maleta no mês analisado E:
- **🆕 Nova:** nunca teve pedido anterior (primeiro contato)
- **🔄 Retorno:** havia saído e voltou — gap de 4 ou mais meses sem novo pedido

> Cada revendedora conta apenas uma vez por mês como entrada, mesmo que tenha múltiplos pedidos no período.

### Data de entrega da maleta:
- **Pedidos Baixados:** `data_baixa − 30 dias` (a supervisora registra a data_baixa como a entrega mais 30 dias de prazo)
- **Pedidos Abertos:** `data_criacao` (a maleta ainda está com ela)
- **Cancelados:** não contam como entrada

### Regra de Saída:
Uma revendedora "sai" quando:
1. Seu **último pedido** foi Baixado dentro do mês analisado
2. Não existe nenhum pedido criado a partir do início desse mesmo mês (ou seja, não veio nova maleta)

> Pedidos cancelados não configuram saída.

### Informações exibidas:
- Por mês: lista de entradas (tipo: Nova ou Retorno) e saídas
- Saldo mensal: entradas − saídas
- Tempo no time de cada revendedora que saiu (do 1º pedido ao último baixo)
- Insights automáticos baseados em métricas de desempenho de equipes de vendas

---

## Tela: Hoje (exclusiva para Supervisoras)

**Objetivo:** Painel diário rápido para a supervisora ver o que precisa de atenção imediatamente.

### O que exibe:

1. **Acertos do dia e da semana** — pedidos com data_acerto hoje ou nesta semana, com possibilidade de ir direto para o agendamento
2. **Ranking do mês** — posição de cada revendedora da equipe em relação à meta configurada (quando há meta)
3. **Revendedoras sem vendas** — pedidos abertos com pré-baixa = R$0
4. **Vencidos sem regularização** — pedidos abertos com data_acerto no passado

---

## Tela: Acompanhamento

**Objetivo:** Rastrear o status de cada pedido individualmente para uma revendedora específica.

- Busca por nome da revendedora
- Exibe todos os pedidos com status, valores, datas e pré-baixa
- Permite ver o histórico completo de uma revendedora

---

## Tela: Diagnóstico

**Objetivo:** Ferramenta técnica de suporte — verificar a integridade dos dados e detectar anomalias.

### O que verifica:
- Pedidos abertos muito antigos (possíveis dados sujos)
- Pedidos sem revendedora associada
- Valores zerados em situações inesperadas
- Revendedoras sem supervisora registrada

---

## Tela: Marketing

**Objetivo:** Geração de conteúdo para campanhas com base no contexto da Aureum.

- Criação de textos para redes sociais, mensagens para revendedoras, anúncios
- Usa modelos de template internos com a identidade da marca

---

## Tela: Dashboard TV

**Objetivo:** Painel em tela cheia para exibição em televisão no escritório, sem interação manual.

- Atualiza automaticamente
- Exibe ranking de revendedoras em tempo real
- Mostra métricas globais do mês corrente
- Acesso via login especial "dashboard" (sem acesso ao restante do sistema)

---

## Dados Salvos no Supabase (além do cache)

| Tabela | O que guarda |
|---|---|
| `agendamentos` | Data, forma, hora e observação de cada acerto agendado, por pedido |
| `premiacoes` | Configuração mensal de metas e prêmios (suporta multi-tier em JSON) |
| `entrega_premiacoes` | Registro de quais prêmios já foram entregues, por mês e revendedora |
| `cache_jueri` | Listas de pedidos, produtos, revendedoras e categorias (cache da API) |
| `cache_pedidos_detalhes` | Detalhes individuais de cada pedido (itens, quantidades) |

---

## Regras de Cache e Atualização

O sistema usa duas camadas de cache para não depender da velocidade da API Jueri a cada acesso:

1. **Supabase** (persistente): dados sobrevivem a reinicializações do servidor
2. **Memória do Streamlit** (em sessão): elimina consultas ao Supabase durante navegação

### TTL automático por horário (horário de Brasília):
| Período | Frequência de atualização |
|---|---|
| Seg–Sex, 8h–18h (horário comercial) | A cada 1 hora |
| Seg–Sex, fora do horário | A cada 4 horas |
| Sábado e Domingo | A cada 6 horas |

### Botões de atualização manual:
- **🔄 Atualizar dados** — relê o Supabase e recarrega a memória (~1 segundo)
- **⚙️ Sincronizar com API Jueri** — busca dados frescos do ERP Jueri e regrava o Supabase (pode levar 2–5 minutos na primeira vez; inclui detalhes de todos os pedidos abertos e baixados dos últimos 180 dias)
