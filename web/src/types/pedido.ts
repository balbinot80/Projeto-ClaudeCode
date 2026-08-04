export interface Pedido {
  id: number
  codigo_pedido: string
  status: 'Aberto' | 'Baixado' | string
  fk_revendedor_id: number
  supervisor_nome: string | null
  data_acerto: string | null
  data_baixa: string | null
  data_criacao: string | null
  valor_total: number | string | null
  valor_pre_baixa: number | string | null
  valor_total_antes_baixa: number | string | null
  comprador?: { nome?: string } | null
}
