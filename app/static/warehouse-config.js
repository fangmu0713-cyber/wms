"use strict";
// Declarative forms and locale text for warehouse execution.
const warehouseConfig = {
  "zh": {
    "phase": "阶段 2 · 仓内作业",
    "waves": "波次与拣货任务",
    "waveDescription": "集中安排已预占订单，领取并扫描独立拣货任务。",
    "waveHelp": "选择同货主同仓已预占未拣订单，可多选。按库位代码、SKU、订单排序，逐单放入对应订单容器。先领取再扫码；波次完成仅表示拣货完成，仍须逐单复核、打包和交接。未拣可撤波次并保留预占；已拣不得直接释放。",
    "pickTasks": "拣货任务 · 按波次和路线排列",
    "waveCreate": "创建波次",
    "waveCancel": "撤销未拣波次",
    "taskClaim": "领取拣货任务",
    "taskRelease": "释放未拣任务",
    "taskScan": "扫描任务拣货",
    "wave_id": "波次",
    "task_id": "拣货任务",
    "order_ids": "选择订单（可多选）",
    "sequence": "路线序号",
    "assignee_id": "领取人",
    "movements": "补货与移位",
    "movementDescription": "库内搬运逐步确认，待搬与搬运中的数量独立核算。",
    "movementHelp": "仅同仓合格库存。建任务锁定待搬数量，订单不可重复预占；领取后核对来源库位、商品和整单数量再搬出。搬运中独立计数，到目标库位再次核对后入账。未搬出可释放领取或取消任务；已搬出不得直接取消。当前为人工补货/移位，不含自动补货策略、部分接收或跨仓调拨。",
    "movementCreate": "创建库内作业",
    "movementClaim": "领取搬运任务",
    "movementRelease": "释放未搬出任务",
    "movementCancel": "取消未搬出任务",
    "movementDispatch": "扫描来源并确认搬出",
    "movementReceive": "扫描目标并确认到位",
    "movementRecords": "补货与移位任务",
    "move_id": "搬运任务",
    "source_inventory_id": "来源库存（仅可用数量）",
    "source_location_id": "来源库位",
    "destination_location_id": "目标库位",
    "kind": "作业类型",
    "MOVE": "库内移位",
    "REPLENISHMENT": "人工补货",
    "move_reserved": "待搬锁定",
    "in_transit": "库内搬运中",
    "move_reserved_delta": "待搬锁定变化",
    "in_transit_delta": "搬运中变化",
    "availableMetric": "上架在库扣除订单预占与待搬锁定",
    "inventoryHelp": "已上架在库为库位实物；可分配=在库−订单预占−待搬锁定。库内搬运中单独计数且不可销售，仍计入实物保管总量。已拣属于订单预占，不重复扣减。",
    "waveScope": "波次与独立拣货任务",
    "moveScope": "人工补货与库内移位",
    "moveScopeHelp": "待搬锁定、扫码搬出、搬运中和目标到位；同仓实物总量守恒。",
    "efficiencyScope": "自动补货、盘点、跨仓调拨、箱托、组合装、部分发货与多包裹",
    "efficiencyScopeHelp": "后续分阶段交付。汇总拣货后二次分拣、实体回位和部分任务交接也尚未实现。",
    "insufficient_available_stock_for_movement": "可用库存不足，订单预占或其他待搬任务已占用数量。",
    "movement_wrong_barcode_location_or_quantity": "商品、库位或数量不符，请按任务整单数量核对。",
    "movement_requires_current_assignee": "请由该任务的领取人操作。",
    "movement_cancel_requires_not_dispatched": "货物已搬出，不能直接取消。",
    "movement_already_claimed": "任务已由其他人领取，请刷新。",
    "movement_wrong_physical_stage": "当前作业阶段不支持此操作，请刷新核对。",
    "pick_via_wave_task_required": "订单已入波次，请通过对应拣货任务扫码。"
  },
  "pt": {
    "phase": "Fase 2 · Operações internas",
    "waves": "Ondas e tarefas",
    "waveDescription": "Organize pedidos reservados e execute tarefas por endereço.",
    "waveHelp": "Selecione pedidos reservados não separados do mesmo proprietário e armazém. A rota usa endereço, SKU e pedido. Separe em recipiente por pedido. Assuma antes de bipar. Onda concluída indica separação; confira, embale e expeça cada pedido. Cancelar onda não iniciada mantém as reservas.",
    "pickTasks": "Tarefas · por onda e sequência",
    "waveCreate": "Criar onda",
    "waveCancel": "Cancelar onda não separada",
    "taskClaim": "Assumir tarefa de separação",
    "taskRelease": "Liberar tarefa não iniciada",
    "taskScan": "Bipar separação da tarefa",
    "wave_id": "Onda",
    "task_id": "Tarefa de separação",
    "order_ids": "Pedidos (seleção múltipla)",
    "sequence": "Sequência",
    "assignee_id": "Responsável",
    "movements": "Reposição e movimentação",
    "movementDescription": "Confirme cada etapa e acompanhe reservas e itens em movimentação.",
    "movementHelp": "Somente estoque aprovado no mesmo armazém. Criar tarefa bloqueia a quantidade para pedidos. Assuma, confira origem, produto e quantidade total e confirme a retirada. Itens em movimentação não estão disponíveis. Confira novamente no destino. Antes da retirada, pode liberar a atribuição ou cancelar a tarefa. Após a retirada, não pode cancelar. Reposição manual; sem regras automáticas, recebimento parcial ou transferência entre armazéns.",
    "movementCreate": "Criar movimentação interna",
    "movementClaim": "Assumir movimentação",
    "movementRelease": "Liberar antes da retirada",
    "movementCancel": "Cancelar antes da retirada",
    "movementDispatch": "Bipar origem e confirmar retirada",
    "movementReceive": "Bipar destino e confirmar chegada",
    "movementRecords": "Tarefas de reposição e movimentação",
    "move_id": "Movimentação",
    "source_inventory_id": "Estoque de origem (disponível)",
    "source_location_id": "Endereço de origem",
    "destination_location_id": "Endereço de destino",
    "kind": "Tipo de operação",
    "MOVE": "Movimentação interna",
    "REPLENISHMENT": "Reposição manual",
    "move_reserved": "Bloqueado para mover",
    "in_transit": "Em movimentação interna",
    "move_reserved_delta": "Variação bloqueada para mover",
    "in_transit_delta": "Variação em movimentação",
    "availableMetric": "Físico menos pedidos e bloqueios para movimentação",
    "inventoryHelp": "Disponível = físico armazenado − reservas de pedidos − bloqueios para movimentação. Itens em movimentação interna não estão à venda, mas continuam no total físico sob custódia. Separados fazem parte da reserva do pedido.",
    "waveScope": "Ondas e tarefas independentes",
    "moveScope": "Reposição manual e movimentação interna",
    "moveScopeHelp": "Bloqueio, retirada, movimentação e chegada; conservação do total físico no armazém.",
    "efficiencyScope": "Reposição automática, inventário, transferências, caixas, kits, expedição parcial e múltiplos pacotes",
    "efficiencyScopeHelp": "Entrega futura. Triagem após coleta agregada, retorno físico e transferência parcial de tarefas também não implementados.",
    "insufficient_available_stock_for_movement": "Estoque disponível insuficiente; verifique reservas e outras movimentações.",
    "movement_wrong_barcode_location_or_quantity": "Produto, endereço ou quantidade incorreta. Confira a quantidade total da tarefa.",
    "movement_requires_current_assignee": "Somente o responsável atual pode executar esta etapa.",
    "movement_cancel_requires_not_dispatched": "Os itens já foram retirados; não é possível cancelar diretamente.",
    "movement_already_claimed": "Outro operador assumiu a tarefa. Atualize os dados.",
    "movement_wrong_physical_stage": "Etapa incompatível. Atualize e confira o estado da tarefa.",
    "pick_via_wave_task_required": "Pedido em onda: utilize a tarefa de separação correspondente."
  },
  "states": {
    "OPEN": [
      "待拣货",
      "Aguardando separação"
    ],
    "COMPLETED": [
      "已完成",
      "Concluído"
    ],
    "READY": [
      "待领取",
      "Disponível"
    ],
    "CLAIMED": [
      "已领取",
      "Assumida"
    ],
    "DONE": [
      "已完成",
      "Concluída"
    ],
    "PLANNED": [
      "待领取搬运",
      "Aguardando operador"
    ],
    "IN_TRANSIT": [
      "库内搬运中",
      "Em movimentação interna"
    ]
  },
  "roles": {
    "wave": [
      "staff"
    ],
    "wave-cancel": [
      "staff"
    ],
    "task-claim": [
      "staff",
      "picker"
    ],
    "task-release": [
      "staff",
      "picker"
    ],
    "task-scan": [
      "staff",
      "picker"
    ],
    "movement": [
      "staff"
    ],
    "movement-cancel": [
      "staff"
    ],
    "movement-claim": [
      "staff",
      "picker",
      "receiver"
    ],
    "movement-release": [
      "staff",
      "picker",
      "receiver"
    ],
    "movement-dispatch": [
      "staff",
      "picker",
      "receiver"
    ],
    "movement-receive": [
      "staff",
      "picker",
      "receiver"
    ]
  },
  "descriptions": {
    "waves": "waveDescription",
    "movements": "movementDescription"
  },
  "schemas": [
    {
      "id": "wave",
      "area": "wave",
      "title": "waveCreate",
      "path": "/api/waves",
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
          "name": "reference",
          "type": "text"
        },
        {
          "name": "order_ids",
          "type": "select",
          "source": "orders",
          "statuses": [
            "RESERVED"
          ],
          "multiple": true
        }
      ]
    },
    {
      "id": "wave-cancel",
      "area": "wave",
      "title": "waveCancel",
      "path": "/api/waves/:wave_id/cancel",
      "fields": [
        {
          "name": "wave_id",
          "type": "select",
          "source": "waves",
          "statuses": [
            "OPEN",
            "PICKING"
          ]
        }
      ]
    },
    {
      "id": "task-claim",
      "area": "wave",
      "title": "taskClaim",
      "path": "/api/pick_tasks/:task_id/claim",
      "fields": [
        {
          "name": "task_id",
          "type": "select",
          "source": "pick_tasks",
          "statuses": [
            "READY"
          ]
        }
      ]
    },
    {
      "id": "task-release",
      "area": "wave",
      "title": "taskRelease",
      "path": "/api/pick_tasks/:task_id/release",
      "fields": [
        {
          "name": "task_id",
          "type": "select",
          "source": "pick_tasks",
          "statuses": [
            "CLAIMED"
          ]
        }
      ]
    },
    {
      "id": "task-scan",
      "area": "wave",
      "title": "taskScan",
      "path": "/api/pick_tasks/:task_id/scan",
      "fields": [
        {
          "name": "task_id",
          "type": "select",
          "source": "pick_tasks",
          "statuses": [
            "CLAIMED"
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
          "min": 1,
          "value": 1
        }
      ],
      "help": "scanQtyHelp"
    },
    {
      "id": "movement",
      "area": "movement",
      "title": "movementCreate",
      "path": "/api/movements",
      "fields": [
        {
          "name": "source_inventory_id",
          "type": "select",
          "source": "inventory"
        },
        {
          "name": "destination_location_id",
          "type": "select",
          "source": "locations"
        },
        {
          "name": "kind",
          "type": "select",
          "options": [
            "REPLENISHMENT",
            "MOVE"
          ]
        },
        {
          "name": "reference",
          "type": "text"
        },
        {
          "name": "qty",
          "type": "number",
          "min": 1,
          "value": 1
        }
      ]
    },
    {
      "id": "movement-claim",
      "area": "movement",
      "title": "movementClaim",
      "path": "/api/movements/:move_id/claim",
      "fields": [
        {
          "name": "move_id",
          "type": "select",
          "source": "movements",
          "statuses": [
            "PLANNED"
          ]
        }
      ]
    },
    {
      "id": "movement-release",
      "area": "movement",
      "title": "movementRelease",
      "path": "/api/movements/:move_id/release",
      "fields": [
        {
          "name": "move_id",
          "type": "select",
          "source": "movements",
          "statuses": [
            "CLAIMED"
          ]
        }
      ]
    },
    {
      "id": "movement-cancel",
      "area": "movement",
      "title": "movementCancel",
      "path": "/api/movements/:move_id/cancel",
      "fields": [
        {
          "name": "move_id",
          "type": "select",
          "source": "movements",
          "statuses": [
            "PLANNED",
            "CLAIMED"
          ]
        }
      ]
    },
    {
      "id": "movement-dispatch",
      "area": "movement",
      "title": "movementDispatch",
      "path": "/api/movements/:move_id/dispatch",
      "fields": [
        {
          "name": "move_id",
          "type": "select",
          "source": "movements",
          "statuses": [
            "CLAIMED"
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
          "min": 1,
          "value": 1
        }
      ]
    },
    {
      "id": "movement-receive",
      "area": "movement",
      "title": "movementReceive",
      "path": "/api/movements/:move_id/receive",
      "fields": [
        {
          "name": "move_id",
          "type": "select",
          "source": "movements",
          "statuses": [
            "IN_TRANSIT"
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
          "min": 1,
          "value": 1
        }
      ]
    }
  ]
};
