"use strict";
const transferConfig = {
  "zh": {
    "transfers": "跨仓调拨",
    "transferDescription": "按实际发出和分批到货记账，逐笔核对在途余量。",
    "transferHelp": "同一货主、单SKU，从一个源库位发往另一仓库。主管建单需两仓权限；发出人需源仓权限，接收人需目标仓权限。创建先锁定库存，整单扫码发出后转为在途。每批合格到货核对商品、目标库位、件数并填写唯一签收批次号；未到或有争议的货物继续留在途，不得虚报接收。仅管理员可根据确认丢失的凭据填写原因，将全部剩余在途结案；该操作不是残次品报废或财务赔付，后续找回暂不支持直接撤销。",
    "transferCreate": "创建跨仓调拨",
    "transferDispatch": "确认整单实际发出",
    "transferReceive": "确认一批合格到货",
    "transferCancel": "取消尚未发出的调拨",
    "transferLoss": "管理员确认剩余在途丢失",
    "transferRecords": "调拨单与在途数量",
    "transferEvents": "不可改写的发出、接收与结案记录",
    "transfer_id": "调拨单",
    "source_warehouse_id": "源仓库",
    "destination_warehouse_id": "目标仓库",
    "receipt_reference": "签收批次号（同一调拨内唯一）",
    "received_qty": "已接收",
    "lost_qty": "确认丢失",
    "remaining_qty": "剩余在途",
    "transfer_in_transit": "跨仓在途（源仓归集）",
    "transfer_lost": "累计确认在途丢失",
    "transfer_transit_delta": "跨仓在途变化",
    "transfer_lost_delta": "确认在途丢失变化",
    "DISPATCH": "实际发出",
    "RECEIVE": "分批接收",
    "LOSS": "确认在途丢失",
    "CANCEL": "发出前取消",
    "transferScope": "跨仓调拨、分批接收与在途丢失结案",
    "transferScopeHelp": "单货主单SKU，两端分权执行；在途不可售，确认接收才增加目标仓库存。",
    "efficiencyScope": "自动补货、箱托、组合装、部分销售发货与多包裹",
    "inventoryHelp": "可分配=已上架在库−订单预占−待搬/待调拨锁定−盘点差异锁定。实盘测量暂停所选库存。库内搬运中和跨仓在途均不可售；跨仓在途仅在源仓归集一次，确认丢失不再计入保管实物。",
    "move_reserved": "待搬/待调拨锁定",
    "insufficient_available_stock_for_transfer": "可分配库存不足，请核对订单、搬运、调拨和盘点差异锁定。",
    "transfer_requires_different_warehouses": "目标必须是另一个仓库；同仓请使用补货与移位。",
    "transfer_requires_not_dispatched": "该操作只允许在实际发出前执行。",
    "transfer_requires_in_transit": "请先完成实际发出，再登记到货或丢失。",
    "transfer_wrong_barcode_or_location": "商品条码或库位不符，请核对调拨单。",
    "transfer_wrong_destination_location": "请选择目标仓库内的实际到货库位。",
    "transfer_dispatch_requires_full_quantity": "本版本需按调拨单完整数量发出。",
    "transfer_quantity_exceeds_remaining": "本次数量超过剩余在途数量。",
    "transfer_loss_must_settle_remaining": "确认丢失须核对全部剩余在途数量后结案。",
    "transfer_receipt_reference_already_used": "该批次已登记，请刷新核对，勿换键或换人重复接收。",
    "transfer_already_terminal": "调拨已完成或结案，不能再次操作。"
  },
  "pt": {
    "transfers": "Transferências entre armazéns",
    "transferDescription": "Registre saída, recebimentos parciais e saldo em trânsito.",
    "transferHelp": "Um proprietário e SKU, de um endereço para outro armazém. Criar exige supervisor com acesso aos dois armazéns; saída exige acesso à origem, recebimento ao destino. A criação bloqueia o estoque; confirme a saída integral por leitura. Cada lote aprovado recebido exige produto, endereço, quantidade e referência de recebimento única. Itens ausentes ou em disputa continuam em trânsito. Somente administrador pode encerrar todo o saldo restante como perda confirmada, com motivo. Não representa descarte de avaria nem indenização financeira. Reversão por localização posterior não implementada.",
    "transferCreate": "Criar transferência",
    "transferDispatch": "Confirmar saída integral",
    "transferReceive": "Confirmar lote aprovado recebido",
    "transferCancel": "Cancelar antes da saída",
    "transferLoss": "Administrador: encerrar saldo perdido",
    "transferRecords": "Transferências e saldo em trânsito",
    "transferEvents": "Histórico imutável de saída, recebimento e encerramento",
    "transfer_id": "Transferência",
    "source_warehouse_id": "Armazém de origem",
    "destination_warehouse_id": "Armazém de destino",
    "receipt_reference": "Referência única do lote recebido",
    "received_qty": "Recebido",
    "lost_qty": "Perda confirmada",
    "remaining_qty": "Saldo em trânsito",
    "transfer_in_transit": "Trânsito entre armazéns (origem)",
    "transfer_lost": "Perda acumulada em trânsito",
    "transfer_transit_delta": "Variação em trânsito entre armazéns",
    "transfer_lost_delta": "Variação de perda confirmada",
    "DISPATCH": "Saída efetiva",
    "RECEIVE": "Recebimento parcial",
    "LOSS": "Perda confirmada",
    "CANCEL": "Cancelamento antes da saída",
    "transferScope": "Transferência, recebimento parcial e perda em trânsito",
    "transferScopeHelp": "Um proprietário e SKU; acesso por ponta. Somente a confirmação de chegada aumenta o estoque do destino.",
    "efficiencyScope": "Reposição automática, caixas, kits, expedição parcial de vendas e múltiplos pacotes",
    "inventoryHelp": "Disponível = armazenado − pedidos − bloqueios de movimentação/transferência − faltas de inventário. Medição pausa o saldo. Movimentação interna e trânsito entre armazéns não estão à venda. Trânsito entre armazéns é somado uma única vez na origem; perda confirmada sai da custódia física.",
    "move_reserved": "Bloqueado para mover/transferir",
    "insufficient_available_stock_for_transfer": "Saldo disponível insuficiente. Confira pedidos, movimentações, transferências e inventário.",
    "transfer_requires_different_warehouses": "Escolha outro armazém. Para endereços do mesmo armazém, use movimentação interna.",
    "transfer_requires_not_dispatched": "Esta operação exige que a saída ainda não tenha ocorrido.",
    "transfer_requires_in_transit": "Confirme a saída antes de receber ou encerrar perda.",
    "transfer_wrong_barcode_or_location": "Código de barras ou endereço incorreto.",
    "transfer_wrong_destination_location": "Selecione o endereço real no armazém de destino.",
    "transfer_dispatch_requires_full_quantity": "Confirme a quantidade integral da transferência.",
    "transfer_quantity_exceeds_remaining": "Quantidade maior que o saldo em trânsito.",
    "transfer_loss_must_settle_remaining": "Confira e encerre todo o saldo restante como perda confirmada.",
    "transfer_receipt_reference_already_used": "Lote já registrado. Atualize e confira; não repita com outra chave ou operador.",
    "transfer_already_terminal": "Transferência concluída ou encerrada; operação não permitida."
  },
  "schemas": [
    {
      "id": "transfer-create",
      "title": "transferCreate",
      "path": "/api/transfers",
      "fields": [
        {
          "name": "source_inventory_id",
          "type": "select",
          "source": "inventory"
        },
        {
          "name": "destination_warehouse_id",
          "type": "select",
          "source": "warehouses"
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
      ],
      "area": "transfer"
    },
    {
      "id": "transfer-dispatch",
      "title": "transferDispatch",
      "path": "/api/transfers/:transfer_id/dispatch",
      "fields": [
        {
          "name": "transfer_id",
          "type": "select",
          "source": "transfers",
          "statuses": [
            "TRANSFER_PLANNED"
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
        },
        {
          "name": "carrier",
          "type": "text"
        },
        {
          "name": "tracking_number",
          "type": "text"
        }
      ],
      "area": "transfer"
    },
    {
      "id": "transfer-receive",
      "title": "transferReceive",
      "path": "/api/transfers/:transfer_id/receive",
      "fields": [
        {
          "name": "transfer_id",
          "type": "select",
          "source": "transfers",
          "statuses": [
            "DISPATCHED",
            "PART_RECEIVED"
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
        },
        {
          "name": "receipt_reference",
          "type": "text"
        }
      ],
      "area": "transfer"
    },
    {
      "id": "transfer-cancel",
      "title": "transferCancel",
      "path": "/api/transfers/:transfer_id/cancel",
      "fields": [
        {
          "name": "transfer_id",
          "type": "select",
          "source": "transfers",
          "statuses": [
            "TRANSFER_PLANNED"
          ]
        },
        {
          "name": "reason",
          "type": "text"
        }
      ],
      "area": "transfer"
    },
    {
      "id": "transfer-loss",
      "title": "transferLoss",
      "path": "/api/transfers/:transfer_id/close_loss",
      "fields": [
        {
          "name": "transfer_id",
          "type": "select",
          "source": "transfers",
          "statuses": [
            "DISPATCHED",
            "PART_RECEIVED"
          ]
        },
        {
          "name": "qty",
          "type": "number",
          "min": 1,
          "value": 1
        },
        {
          "name": "reason",
          "type": "text"
        }
      ],
      "area": "transfer"
    }
  ],
  "roles": {
    "transfer-create": [
      "staff"
    ],
    "transfer-dispatch": [
      "staff",
      "picker"
    ],
    "transfer-receive": [
      "staff",
      "receiver"
    ],
    "transfer-cancel": [
      "staff"
    ],
    "transfer-loss": []
  },
  "states": {
    "TRANSFER_PLANNED": [
      "待跨仓发出",
      "Aguardando saída"
    ],
    "DISPATCHED": [
      "跨仓在途",
      "Em trânsito entre armazéns"
    ],
    "PART_RECEIVED": [
      "部分接收",
      "Parcialmente recebido"
    ],
    "CLOSED_WITH_LOSS": [
      "在途丢失结案",
      "Encerrada com perda"
    ]
  }
};
for (const key of ["zh","pt","roles","states"]) Object.assign(warehouseConfig[key],transferConfig[key]);
warehouseConfig.schemas.push(...transferConfig.schemas);
warehouseConfig.descriptions.transfers = "transferDescription";
