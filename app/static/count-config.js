"use strict";
const countConfig = {
  "zh": {
    "counts": "盘点与复盘",
    "countDescription": "限定SKU与库位，独立盲盘和复盘；审批只过账差额。",
    "countHelp": "先由管理员签发专用盘点账号。选单一货主、仓库、SKU和库位范围；实盘时暂停所选库存作业，提交后解除测量锁。短少数量单独锁定，其他可用数量可继续作业。差异需不同人员连续两次得到相同差额，管理员填写原因后审批。取消不会修正实物差异，须继续调查。",
    "blindCountHelp": "仅查看分配给你的任务；账面数量和其他人的读数均不可访问。核对库位、商品和实际件数，可填0；确认后不能改数。请在本任务暂停的库存范围内完成实盘，不放入或移走货物。结果未确认时重试原提交，不刷新页面。",
    "countCreate": "建立盘点范围",
    "countSubmit": "提交盲盘读数",
    "countRecount": "分配独立复盘",
    "countApprove": "审批并过账差额",
    "countCancel": "取消盘点并保留调查记录",
    "countSessions": "盘点单",
    "countLines": "库位差异与审批依据",
    "countAttempts": "实盘任务与读数",
    "blindCountTasks": "我的盲盘任务",
    "session_id": "盘点单",
    "attempt_id": "实盘任务",
    "counter_id": "专用盘点员",
    "location_ids": "盘点库位（可多选）",
    "line_id": "盘点库位行",
    "reason": "审批/取消原因",
    "baseline_on_hand": "截点账面",
    "cutoff_seq": "流水截点",
    "counted_qty": "实盘数量",
    "accepted_delta": "待过账差额",
    "delta": "本次差额",
    "hold_qty": "短少锁定",
    "round": "实盘轮次",
    "count_reserved": "盘点差异锁定",
    "count_reserved_delta": "盘点锁定变化",
    "countScope": "盘点截点、盲盘、独立复盘与差异审批",
    "countScopeHelp": "单SKU多库位，实盘暂停范围内作业，读数提交后允许继续；审批增减差额并保留后续流水。",
    "efficiencyScope": "自动补货、跨仓调拨、箱托、组合装、部分发货与多包裹",
    "availableMetric": "在库扣除订单、待搬和盘点差异锁定",
    "inventoryHelp": "可分配=已上架在库−订单预占−待搬锁定−盘点差异锁定。实盘测量中的库位暂停作业；搬运中单独计入保管总量且不能销售。",
    "inventory_locked_for_count": "该库存正在实盘测量，请等待读数提交或管理员取消后再作业。",
    "count_requires_unencumbered_inventory": "所选库存仍有订单或搬运占用，请先完成/释放相关作业。",
    "authorized_count_only_operator_required": "请选择该仓有权限的有效专用盘点账号。",
    "count_wrong_barcode_or_location": "商品或库位与盘点任务不符。",
    "recount_requires_different_operator": "复盘必须由另一名盘点员执行。",
    "count_requires_confirmed_lines": "全部库位完成核对后才能审批；差异需独立复盘一致。",
    "count_attempt_already_closed": "该实盘读数已提交或取消；不能再改数。",
    "count_only_credential_scope": "此凭证仅可读取和提交自己的盲盘任务。",
    "count_only_credential_required": "请使用分配的专用盘点账号提交读数。"
  },
  "pt": {
    "counts": "Inventário e recontagem",
    "countDescription": "Conte por SKU e endereço; a aprovação lança somente a diferença.",
    "countHelp": "O administrador deve emitir credenciais exclusivas de contagem. Selecione proprietário, armazém, SKU e endereços. A medição pausa as operações nesses saldos; após enviar, o bloqueio de medição é liberado. Faltas ficam bloqueadas, e o restante disponível pode operar. Diferenças exigem duas leituras consecutivas com o mesmo ajuste, por pessoas distintas, e aprovação do administrador com motivo. Cancelar não corrige divergências físicas.",
    "blindCountHelp": "Acesso somente às suas tarefas. Saldos contábeis e leituras de outras pessoas são inacessíveis. Confira endereço, produto e quantidade real, inclusive zero. A leitura enviada não pode ser alterada. Não retire nem guarde itens no escopo durante a medição. Se o resultado não for confirmado, repita o envio original sem recarregar.",
    "countCreate": "Criar escopo de inventário",
    "countSubmit": "Enviar contagem cega",
    "countRecount": "Atribuir recontagem independente",
    "countApprove": "Aprovar e lançar diferença",
    "countCancel": "Cancelar e manter registro",
    "countSessions": "Inventários",
    "countLines": "Diferenças por endereço",
    "countAttempts": "Tarefas e leituras",
    "blindCountTasks": "Minhas tarefas de contagem",
    "session_id": "Inventário",
    "attempt_id": "Tarefa de contagem",
    "counter_id": "Operador exclusivo de contagem",
    "location_ids": "Endereços (seleção múltipla)",
    "line_id": "Linha do inventário",
    "reason": "Motivo da aprovação/cancelamento",
    "baseline_on_hand": "Saldo no corte",
    "cutoff_seq": "Corte do histórico",
    "counted_qty": "Quantidade contada",
    "accepted_delta": "Ajuste a lançar",
    "delta": "Diferença da leitura",
    "hold_qty": "Falta bloqueada",
    "round": "Rodada",
    "count_reserved": "Bloqueado por inventário",
    "count_reserved_delta": "Variação bloqueada por inventário",
    "countScope": "Corte, contagem cega, recontagem e aprovação",
    "countScopeHelp": "Um SKU em vários endereços. A medição pausa o escopo; após enviar, operações retomam. O ajuste preserva os movimentos posteriores.",
    "efficiencyScope": "Reposição automática, transferências, caixas, kits, expedição parcial e múltiplos pacotes",
    "availableMetric": "Físico menos pedidos, movimentações e faltas de inventário",
    "inventoryHelp": "Disponível = armazenado − pedidos − bloqueios de movimentação − faltas de inventário. Endereços em medição ficam pausados. Itens em movimentação interna integram a custódia, mas não estão disponíveis.",
    "inventory_locked_for_count": "Saldo em medição. Aguarde o envio da leitura ou o cancelamento autorizado.",
    "count_requires_unencumbered_inventory": "O saldo tem pedidos ou movimentações em aberto; conclua ou libere essas operações.",
    "authorized_count_only_operator_required": "Selecione credencial exclusiva de contagem válida e autorizada neste armazém.",
    "count_wrong_barcode_or_location": "Produto ou endereço diferente da tarefa.",
    "recount_requires_different_operator": "Outra pessoa deve realizar a recontagem.",
    "count_requires_confirmed_lines": "Confirme todos os endereços. Diferenças exigem recontagem independente consistente.",
    "count_attempt_already_closed": "A leitura foi enviada ou cancelada e não pode ser alterada.",
    "count_only_credential_scope": "Credencial restrita às próprias tarefas de contagem.",
    "count_only_credential_required": "Use a credencial exclusiva atribuída para enviar leituras."
  },
  "schemas": [
    {
      "id": "count-create",
      "area": "count",
      "title": "countCreate",
      "path": "/api/stock_counts",
      "fields": [
        {
          "name": "owner_id",
          "type": "select",
          "source": "owners"
        },
        {
          "name": "warehouse_id",
          "type": "select",
          "source": "warehouses"
        },
        {
          "name": "sku_id",
          "type": "select",
          "source": "skus"
        },
        {
          "name": "location_ids",
          "type": "select",
          "source": "locations",
          "multiple": true
        },
        {
          "name": "reference",
          "type": "text"
        },
        {
          "name": "counter_id",
          "type": "select",
          "source": "count_operators"
        }
      ]
    },
    {
      "id": "count-submit",
      "area": "count",
      "title": "countSubmit",
      "path": "/api/count_attempts/:attempt_id/submit",
      "fields": [
        {
          "name": "attempt_id",
          "type": "select",
          "source": "count_attempts",
          "statuses": [
            "ACTIVE"
          ]
        },
        {
          "name": "barcode",
          "type": "text"
        },
        {
          "name": "location_id",
          "type": "select",
          "source": "locations"
        },
        {
          "name": "qty",
          "type": "number",
          "min": 0,
          "value": 0
        }
      ]
    },
    {
      "id": "count-recount",
      "area": "count",
      "title": "countRecount",
      "path": "/api/count_lines/:line_id/recount",
      "fields": [
        {
          "name": "line_id",
          "type": "select",
          "source": "count_lines",
          "statuses": [
            "RECOUNT_REQUIRED"
          ]
        },
        {
          "name": "counter_id",
          "type": "select",
          "source": "count_operators"
        }
      ]
    },
    {
      "id": "count-approve",
      "area": "count",
      "title": "countApprove",
      "path": "/api/stock_counts/:session_id/approve",
      "fields": [
        {
          "name": "session_id",
          "type": "select",
          "source": "stock_counts",
          "statuses": [
            "REVIEW"
          ]
        },
        {
          "name": "reason",
          "type": "text"
        }
      ]
    },
    {
      "id": "count-cancel",
      "area": "count",
      "title": "countCancel",
      "path": "/api/stock_counts/:session_id/cancel",
      "fields": [
        {
          "name": "session_id",
          "type": "select",
          "source": "stock_counts",
          "statuses": [
            "OPEN",
            "REVIEW"
          ]
        },
        {
          "name": "reason",
          "type": "text"
        }
      ]
    }
  ],
  "roles": {
    "count-create": [
      "staff"
    ],
    "count-submit": [
      "picker"
    ],
    "count-recount": [
      "staff"
    ],
    "count-approve": [],
    "count-cancel": [
      "staff"
    ]
  },
  "states": {
    "OPEN": [
      "进行中",
      "Em andamento"
    ],
    "REVIEW": [
      "待审批",
      "Aguardando aprovação"
    ],
    "APPROVED": [
      "已审批",
      "Aprovado"
    ],
    "COUNTING": [
      "实盘中",
      "Em contagem"
    ],
    "RECOUNT_REQUIRED": [
      "待复盘",
      "Recontagem necessária"
    ],
    "CONFIRMED": [
      "已核对",
      "Conferido"
    ],
    "ACTIVE": [
      "待实盘",
      "Aguardando leitura"
    ],
    "SUBMITTED": [
      "读数已提交",
      "Leitura enviada"
    ]
  }
};
for (const key of ["zh","pt","roles","states"]) Object.assign(warehouseConfig[key],countConfig[key]);
warehouseConfig.schemas.push(...countConfig.schemas);
warehouseConfig.descriptions.counts = "countDescription";

Object.assign(warehouseConfig.zh,{count_locked:"实盘测量暂停",locked:"实盘暂停",unlocked:"可作业"});
Object.assign(warehouseConfig.pt,{count_locked:"Pausa de medição",locked:"Em medição",unlocked:"Liberado"});
