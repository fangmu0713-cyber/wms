"use strict";

// Authentication and business data are deliberately held in memory only.
let token = "", user = null, snapshot = null, language = "zh-CN", currentView = "overview", fetching = false, sessionVersion = 0, lastRefreshed = null;
const submissions = new WeakMap();
const zh = {
  skip:"跳转到主内容",brandSub:"海外仓协同系统",workspace:"工作空间",overview:"工作总览",masters:"基础资料",inbound:"收货与上架",orders:"订单管理",pda:"PDA 扫码作业",inventory:"库存与流水",returns:"退货处理",finance:"费用与对账",connections:"连接与能力",integrations:"官方 ERP 中心",roadmap:"交付范围",phase:"阶段 1 · 内部业务闭环",language:"语言",disconnected:"未连接",logout:"退出",refresh:"刷新数据",loginTitle:"连接你的仓库",loginHelp:"使用管理员签发的访问令牌登录。令牌仅保存在当前页面内存中，刷新页面后需重新登录。",accessToken:"访问令牌",connect:"连接工作空间",today:"此刻 · 实时业务",heroTitle:"货物流转，清晰有序。",heroText:"收货、预占、拣货、复核与出库使用独立状态，库存以实际交接为准。",startReceiving:"开始收货 ↗",fulfillmentFlow:"履约路径",liveData:"数据库实时数据",flowHelp:"预占、拣货和打包不减少实物库存；仅实际交接出库扣减一次。",integrity:"库存核对",seeLedger:"查看库存与流水 →",recentOrders:"最近订单",allOrders:"全部订单 →",masterHelp:"先建立货主和仓库，再建立库位、SKU 与店铺。所有资料均受服务端权限控制。",masterRecords:"基础资料列表",receive:"01 实际收货",quality:"02 质量检验",putaway:"03 合格上架",receipts:"入库单据",orderHelp:"手工订单直接写入本系统数据库。ERP 推单须取得官方授权后另行启用。",allocationDetail:"订单行与预占明细",scanTitle:"扫描、核对、交接",scanHelp:"支持条码枪键盘输入。逐次提交等待服务端确认；断网不会显示成功。相机、打印机与实物 PDA 待验收。",inventoryHelp:"在库为实物余额；已拣属于已预占数量的一部分，不再次扣减可用库存。库存流水只读。",inventoryBalance:"库存余额",readOnly:"只读 · 服务端核算",ledger:"库存流水",reconciliation:"余额与账本核对",returnHelp:"仅支持关联已出库订单的退货。退货申请与签收不增加可售库存，合格上架后才入账。",returnRecords:"退货记录",feeHelp:"当前支持管理员手工登记订单费用，金额以 BRL 分为单位。相同订单和收费代码禁止重复收费；自动报价、仓租与账单尚未实现。",feeRecords:"费用记录 · BRL",pendingAuthorization:"待真实授权",erpTitle:"官方接入，逐项验证。",erpHelp:"卖家自用 API、海外仓服务商接入、本系统开放 API 是三种不同路径。当前未完成任何 ERP 真实闭环，不使用模拟成功响应。",deliveryBoundary:"交付范围与后续能力",awaitConnection:"等待连接真实后端",description:"从实际收货到交接出库，让每一件库存都有依据。",omsDescription:"独立货主访问，管理授权范围内的订单、商品与库存。",pdaDescription:"面向仓内现场的扫码、复核与交接工作台。",name:"名称",owner_id:"货主",warehouse_id:"仓库",location_id:"库位",sku_id:"SKU",store_id:"店铺",code:"代码",barcode:"条码",reference:"业务参考号",qty:"数量（件）",accepted_qty:"合格数量",rejected_qty:"不合格数量",receipt_id:"入库单",order_id:"订单",return_id:"退货单",package_reference:"包裹参考号",tracking_number:"运单号",carrier:"承运商",amount_cents:"金额（BRL 分）",owner:"货主",warehouse:"仓库",location:"库位",sku:"SKU",store:"店铺",ownerCreate:"建立货主",warehouseCreate:"建立仓库",locationCreate:"建立库位",skuCreate:"建立 SKU",storeCreate:"建立店铺",receiptCreate:"登记实际收货",receiptQc:"登记入库质检",receiptPutaway:"合格品上架",orderCreate:"创建手工订单",reserve:"预占库存",pick:"扫描拣货",verify:"扫描复核",pack:"打包确认",ship:"实际交接出库",cancel:"取消未拣订单",returnCreate:"申请关联退货",returnReceive:"实际签收退货",returnQc:"退货质检",returnPutaway:"退货合格上架",feeCreate:"登记订单费用",submit:"提交并写入数据库",addLine:"＋ 添加订单行",removeLine:"删除订单行",lines:"订单行",choose:"请选择",noOptions:"暂无可选记录",empty:"暂无记录，完成相应业务后在此显示。",loading:"正在读取数据库…",sending:"正在提交…",success:"已由服务端确认",unknown:"响应未确认，请保留原字段后重试；将复用原幂等键。",networkError:"网络异常或请求超时，尚未确认处理结果。",failure:"请求失败",needLogin:"请先连接工作空间。",refreshFailed:"操作已确认，但数据刷新失败，请点击刷新数据。",updated:"最近刷新",noStockIssues:"核对通过",stockIssues:"存在待处理差异",reconcileHelp:"余额、库存流水与有效预占在服务端核对。",unavailable:"暂无核对结果",on_hand:"在库",reserved:"已预占",picked:"已拣",available:"可分配",status:"状态",id:"记录 ID",created_at:"创建时间",type:"事件类型",delta:"在库变化",on_hand_delta:"在库变化",reserved_delta:"预占变化",picked_delta:"已拣变化",source_id:"来源单据",event_type:"事件类型",event_id:"事件 ID",amount:"金额",currency:"币种",total:"合计",line_id:"订单行",verified_qty:"已复核",allocated_qty:"已分配",picked_qty:"已拣",verified:"已复核",shipped_qty:"已出库",inboundPending:"待质检 / 上架",orderActive:"履约中订单",dbScope:"当前账号授权数据",receiptMetric:"实际收货 · 尚未上架",orderMetric:"已创建至已打包",skuMetric:"合格上架的实物数量",availableMetric:"在库扣除当前预占",allocation:"预占记录",orderLines:"订单行",adminOnly:"该功能仅管理员可用。",unsupported:"尚未实现",implemented:"当前可用",devicePending:"待实机验收",coreScope:"基础主数据、实际收货、质检上架、手工订单、预占、扫码拣货复核、打包交接、库存账本与核对",coreScopeHelp:"所有写入通过真实 API 与数据库执行，服务端控制租户、货主与仓库范围。",extendedScope:"关联退货与手工费用",extendedScopeHelp:"退货须收货、质检与上架；当前费用为管理员手工登记，不代表完成自动计费与完整账单。",efficiencyScope:"波次、补货、盘点、调拨、箱托、组合装、部分发货与多包裹",efficiencyScopeHelp:"后续分阶段交付，当前不提供空页面操作。",financeScope:"报价版本、自动仓租、账单确认、收款与财务导出",advancedScope:"B2B、平台仓补货、分销配额、提拆派与代理仓",devicesScope:"相机扫码、打印机、电子秤与实物 PDA",productionScope:"生产部署与 ERP 实际授权闭环",productionHelp:"未获生产环境授权，不声明已上线；ERP 按账户、接口和环境逐项验收。",officialDocs:"官方文档",capabilities:"适配能力",integrationStatus:"接入状态",evidence:"验证说明",notConnected:"待接入 · 无真实账户闭环证据",sessionEnded:"已退出。页面内的认证与业务数据已清除。",authFailed:"令牌无效或会话已撤销，请重新登录。",qcHelp:"合格与不合格数量之和必须等于实际收货数量。",cancelHelp:"仅未拣货订单可取消。已拣货需实际回位流程（尚未实现）；已出库必须走退货。",feeFormHelp:"最小货币单位：100 分 = R$ 1,00。同一订单与代码不可重复。",scanQtyHelp:"每次扫描明确提交件数，不将同一条码的不同实物自动判为重复。传输重试复用幂等键。",orderLineHelp:"仅选择同货主 SKU 与店铺；服务端再次校验归属。",operationId:"业务 ID",serverError:"服务端未返回有效数据。"
};
const pt = {
  skip:"Ir para o conteúdo",brandSub:"OPERAÇÕES LOGÍSTICAS",workspace:"Espaço de trabalho",overview:"Visão geral",masters:"Cadastros",inbound:"Recebimento",orders:"Pedidos",pda:"Operação PDA",inventory:"Estoque e registros",returns:"Devoluções",finance:"Custos e conciliação",connections:"Conexões e recursos",integrations:"Central de ERP",roadmap:"Escopo da entrega",phase:"Fase 1 · Fluxo interno",language:"Idioma",disconnected:"Desconectado",logout:"Sair",refresh:"Atualizar dados",loginTitle:"Conecte seu armazém",loginHelp:"Entre com um token emitido pelo administrador. O token fica apenas na memória desta página e é removido ao recarregar.",accessToken:"Token de acesso",connect:"Conectar espaço de trabalho",today:"AGORA · DADOS REAIS",heroTitle:"Cada movimento, sob controle.",heroText:"Recebimento, reserva, separação, conferência e expedição têm estados independentes. A saída física define a baixa.",startReceiving:"Receber mercadorias ↗",fulfillmentFlow:"Fluxo de atendimento",liveData:"Dados reais do banco",flowHelp:"Reserva, separação e embalagem não reduzem o estoque físico; a expedição realiza uma única baixa.",integrity:"Conciliação de estoque",seeLedger:"Ver estoque e registros →",recentOrders:"Pedidos recentes",allOrders:"Todos os pedidos →",masterHelp:"Cadastre proprietário e armazém antes de endereços, SKUs e lojas. O servidor controla o acesso a todos os dados.",masterRecords:"Registros cadastrais",receive:"01 Receber",quality:"02 Inspecionar",putaway:"03 Armazenar",receipts:"Recebimentos",orderHelp:"Pedidos manuais são gravados no banco deste sistema. A integração de pedidos ERP exige autorização oficial.",allocationDetail:"Itens e reservas dos pedidos",scanTitle:"Bipar, conferir, expedir",scanHelp:"Leitores com entrada de teclado são aceitos. Aguarde a confirmação do servidor após cada envio. Câmera, impressora e PDA físico aguardam validação.",inventoryHelp:"Estoque físico representa o saldo real. Itens separados fazem parte da reserva e não são deduzidos novamente do disponível. Registros são somente leitura.",inventoryBalance:"Saldos de estoque",readOnly:"Somente leitura · Cálculo do servidor",ledger:"Registro de movimentações",reconciliation:"Conciliação de saldos e registros",returnHelp:"Somente devoluções de pedidos expedidos vinculados. Solicitação e recebimento não aumentam o disponível; é necessário inspecionar e armazenar.",returnRecords:"Registros de devolução",feeHelp:"Administradores podem registrar custos por pedido em centavos de BRL. Pedido e código de cobrança não podem se repetir. Tarifas automáticas, armazenagem e faturas não foram implementadas.",feeRecords:"Registros de custos · BRL",pendingAuthorization:"Aguardando autorização real",erpTitle:"Integrações oficiais, verificadas por recurso.",erpHelp:"API do vendedor, integração de operador de armazém e API deste sistema são caminhos distintos. Nenhum fluxo ERP real está concluído. Não há respostas simuladas de sucesso.",deliveryBoundary:"Escopo da entrega e próximos recursos",awaitConnection:"Aguardando conexão ao servidor",description:"Do recebimento à expedição, cada unidade tem um registro verificável.",omsDescription:"Acesso do proprietário aos pedidos, produtos e estoques autorizados.",pdaDescription:"Estação de leitura, conferência e expedição no armazém.",name:"Nome",owner_id:"Proprietário",warehouse_id:"Armazém",location_id:"Endereço",sku_id:"SKU",store_id:"Loja",code:"Código",barcode:"Código de barras",reference:"Referência",qty:"Quantidade (un.)",accepted_qty:"Quantidade aprovada",rejected_qty:"Quantidade rejeitada",receipt_id:"Recebimento",order_id:"Pedido",return_id:"Devolução",package_reference:"Referência do pacote",tracking_number:"Código de rastreio",carrier:"Transportadora",amount_cents:"Valor (centavos de BRL)",owner:"Proprietário",warehouse:"Armazém",location:"Endereço",sku:"SKU",store:"Loja",ownerCreate:"Cadastrar proprietário",warehouseCreate:"Cadastrar armazém",locationCreate:"Cadastrar endereço",skuCreate:"Cadastrar SKU",storeCreate:"Cadastrar loja",receiptCreate:"Registrar recebimento físico",receiptQc:"Inspecionar recebimento",receiptPutaway:"Armazenar itens aprovados",orderCreate:"Criar pedido manual",reserve:"Reservar estoque",pick:"Bipar separação",verify:"Bipar conferência",pack:"Confirmar embalagem",ship:"Confirmar expedição física",cancel:"Cancelar pedido não separado",returnCreate:"Solicitar devolução vinculada",returnReceive:"Receber devolução física",returnQc:"Inspecionar devolução",returnPutaway:"Armazenar devolução aprovada",feeCreate:"Registrar custo do pedido",submit:"Enviar e gravar no banco",addLine:"＋ Adicionar item",removeLine:"Remover item",lines:"Itens do pedido",choose:"Selecione",noOptions:"Sem registros disponíveis",empty:"Nenhum registro. Os dados aparecerão após as operações.",loading:"Consultando o banco…",sending:"Enviando…",success:"Confirmado pelo servidor",unknown:"Resultado não confirmado. Mantenha os campos e tente novamente; a chave de idempotência será reutilizada.",networkError:"Falha de rede ou tempo esgotado. O resultado ainda não foi confirmado.",failure:"Falha na solicitação",needLogin:"Conecte o espaço de trabalho primeiro.",refreshFailed:"Operação confirmada, mas os dados não foram atualizados. Clique em Atualizar dados.",updated:"Atualizado em",noStockIssues:"Conciliação aprovada",stockIssues:"Divergências pendentes",reconcileHelp:"Saldos, movimentações e reservas ativas são conciliados no servidor.",unavailable:"Conciliação indisponível",on_hand:"Físico",reserved:"Reservado",picked:"Separado",available:"Disponível",status:"Estado",id:"ID do registro",created_at:"Criado em",type:"Tipo de evento",delta:"Variação física",on_hand_delta:"Variação física",reserved_delta:"Variação reservada",picked_delta:"Variação separada",source_id:"Documento de origem",event_type:"Tipo de evento",event_id:"ID do evento",amount:"Valor",currency:"Moeda",total:"Total",line_id:"Item do pedido",verified_qty:"Conferido",allocated_qty:"Alocado",picked_qty:"Separado",verified:"Conferido",shipped_qty:"Expedido",inboundPending:"Inspeção / armazenagem pendentes",orderActive:"Pedidos em atendimento",dbScope:"Dados autorizados desta conta",receiptMetric:"Recebido, ainda não armazenado",orderMetric:"De criado a embalado",skuMetric:"Unidades físicas aprovadas",availableMetric:"Físico menos reserva ativa",allocation:"Reservas",orderLines:"Itens do pedido",adminOnly:"Recurso exclusivo para administradores.",unsupported:"Não implementado",implemented:"Disponível",devicePending:"Validação física pendente",coreScope:"Cadastros, recebimento físico, inspeção, armazenagem, pedidos manuais, reserva, separação, conferência, embalagem, expedição e conciliação de estoque",coreScopeHelp:"Todas as operações usam API e banco reais. O servidor controla empresa, proprietário e armazém.",extendedScope:"Devoluções vinculadas e custos manuais",extendedScopeHelp:"Devoluções exigem recebimento, inspeção e armazenagem. Custos são manuais; cobrança automática e faturamento completo não estão incluídos.",efficiencyScope:"Ondas, reposição, inventário, transferências, caixas, paletes, kits, expedição parcial e múltiplos pacotes",efficiencyScopeHelp:"Entrega em fases futuras. Não há páginas vazias apresentadas como funções prontas.",financeScope:"Versões de tarifas, armazenagem automática, aprovação de faturas, pagamentos e exportação financeira",advancedScope:"B2B, reposição de plataformas, cotas de distribuição, contêineres e armazéns parceiros",devicesScope:"Câmera, impressora, balança e PDA físico",productionScope:"Produção e fluxo ERP com autorização real",productionHelp:"Sem autorização de produção, não se declara publicação. Cada integração exige validação por conta, interface e ambiente.",officialDocs:"Documentação oficial",capabilities:"Recursos do adaptador",integrationStatus:"Estado da integração",evidence:"Evidências",notConnected:"Pendente · sem evidência de fluxo em conta real",sessionEnded:"Sessão encerrada. Credenciais e dados foram removidos da memória.",authFailed:"Token inválido ou revogado. Entre novamente.",qcHelp:"A soma de aprovados e rejeitados deve ser igual à quantidade recebida.",cancelHelp:"Apenas pedidos não separados podem ser cancelados. Separados exigem retorno físico (não implementado); expedidos exigem devolução.",feeFormHelp:"Unidade mínima: 100 centavos = R$ 1,00. Pedido e código não podem se repetir.",scanQtyHelp:"Informe a quantidade em cada envio. Unidades distintas podem ter o mesmo código; novas tentativas de transmissão reutilizam a chave de idempotência.",orderLineHelp:"Selecione SKUs e loja do mesmo proprietário. O servidor valida os vínculos.",operationId:"ID da operação",serverError:"O servidor não retornou dados válidos."
};
const states = {
  RECEIVED:["已收货","Recebido"],QC_DONE:["已质检","Inspecionado"],PUTAWAY:["已上架","Armazenado"],CREATED:["已创建","Criado"],RESERVED:["已预占","Reservado"],PICKING:["拣货中","Em separação"],PICKED:["已拣货","Separado"],VERIFIED:["已复核","Conferido"],PACKED:["已打包","Embalado"],SHIPPED:["已出库","Expedido"],CANCELLED:["已取消","Cancelado"],EXPECTED:["待退货收货","Aguardando devolução"],pending_authorization:["待授权","Aguardando autorização"],not_configured:["未配置","Não configurado"]
};
const actionRoles = {
  owner:[],warehouse:[],location:["staff","owner"],sku:["staff","owner"],store:["staff","owner"],
  receipt:["staff","receiver"],"receipt-qc":["staff","receiver"],"receipt-putaway":["staff","receiver"],
  order:["staff","owner"],reserve:["staff","owner"],cancel:["staff","owner"],pick:["staff","picker"],
  verify:["staff","packer"],pack:["staff","packer"],ship:["staff","packer"],
  return:["staff","receiver","owner"],"return-receive":["staff","receiver"],"return-qc":["staff","receiver"],"return-putaway":["staff","receiver"],fee:["finance"]
};
const integrationBlockerPt = {
  upseller:"A documentação de autenticação e resposta contém imagens não verificadas neste ambiente. Faltam autorização da conta e plano elegível. Pedidos de operador de armazém exigem contrato e documentação próprios.",
  dianxiaomi:"A página oficial de exemplo não pôde ser lida. Admissão do operador, contrato, documentação técnica e conta de teste aguardam confirmação.",
  lingxing:"Faltam AppID/AppSecret da empresa, permissões aprovadas e IP público estável autorizado. Recursos de negócio exigem verificação individual.",
  mabang:"O portal oficial não pôde ser lido. A versão atual, permissões, credenciais e o protocolo de negócio aguardam confirmação.",
  bling:"Faltam aplicativo OAuth e autorização da conta. Recursos, permissões e efeitos de alterações no estoque exigem validação. Aplicativos públicos podem exigir aprovação."
};
zh.timezone = "仓库时区（IANA）"; pt.timezone = "Fuso horário do armazém (IANA)";
Object.assign(zh,{on_hand:"已上架在库",stockQuality:"实物数量与质量状态",pending_qc:"待质检",qualified_unstored:"合格未上架",rejected:"不合格待处置",physical_total:"实物总量",datesTimezone:"单据日期按对应仓库时区显示；悬停时间查看时区。",inventoryHelp:"在库为合格上架余额；待检、合格未上架和不合格品单独统计，不能销售。已拣属于已预占数量，不重复扣减可用库存。",skuMetric:"合格且已上架的实物数量"});
Object.assign(pt,{on_hand:"Físico armazenado",stockQuality:"Quantidade física e qualidade",pending_qc:"A inspecionar",qualified_unstored:"Aprovado, não armazenado",rejected:"Rejeitado, aguardando destino",physical_total:"Total físico",datesTimezone:"Datas de documentos usam o fuso do armazém. Passe o cursor sobre a data para consultar o fuso.",inventoryHelp:"O saldo físico inclui apenas itens aprovados e armazenados. Pendentes, aprovados não armazenados e rejeitados são contados separadamente e não estão disponíveis para venda. Separados fazem parte da reserva e não são deduzidos novamente.",skuMetric:"Unidades aprovadas e armazenadas"});
zh.submit = "确认提交"; pt.submit = "Confirmar envio";
zh.retryPending = "重试待确认的原提交"; pt.retryPending = "Repetir envio pendente original";
zh.feeHelp = "管理员和财务可手工登记已出库订单费用，金额以 BRL 分为单位。相同订单和收费代码禁止重复收费；自动报价、仓租与账单尚未实现。";
pt.feeHelp = "Administradores e financeiro podem registrar custos de pedidos expedidos em centavos de BRL. Pedido e código de cobrança não podem se repetir. Tarifas automáticas, armazenagem e faturas não foram implementadas.";
const descriptions = {overview:"description",masters:"masterHelp",inbound:"masterHelp",orders:"orderHelp",pda:"pdaDescription",inventory:"inventoryHelp",returns:"returnHelp",finance:"feeHelp",integrations:"erpHelp",roadmap:"productionHelp"};
Object.assign(zh,warehouseConfig.zh); Object.assign(pt,warehouseConfig.pt); Object.assign(states,warehouseConfig.states); Object.assign(actionRoles,warehouseConfig.roles); Object.assign(descriptions,warehouseConfig.descriptions);
const t = key => (language === "pt-BR" ? pt[key] : zh[key]) || zh[key] || key;
const $ = selector => document.querySelector(selector);
function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = String(text); if (className) el.className = className; return el; }
function statusLabel(value) { return states[value] ? states[value][language === "pt-BR" ? 1 : 0] : value; }
function message(text, error = false) { const el = $("#notice"); el.textContent = text; el.className = `notice${error ? " error" : ""}`; el.hidden = false; }
function array(key) { return Array.isArray(snapshot?.[key]) ? snapshot[key] : []; }
function recordLabel(record) { return [record.name || record.reference || record.code || record.barcode || record.id, record.status ? statusLabel(record.status) : "", record.id].filter((v, i, all) => v && all.indexOf(v) === i).join(" · "); }
function lookup(key, id) { const row = array(key).find(item => item.id === id); return row ? `${row.name || row.code || row.reference || row.id} · ${id}` : (id ?? "—"); }
function translate() {
  document.documentElement.lang = language;
  document.title = language === "pt-BR" ? "Atlas · Operações logísticas" : "Atlas · 海外仓作业台";
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  if (user) $("#identity").textContent = `${user.name} · ${user.role}`;
  updateRefreshLabel();
  document.querySelectorAll('.form-result[data-record-id]').forEach(result => { result.textContent = `${t("success")} · ${result.dataset.recordId}${result.dataset.recordStatus ? ` · ${statusLabel(result.dataset.recordStatus)}` : ""}`; });
  $("#page-title").textContent = t(currentView);
  $("#page-description").textContent = t(descriptions[currentView]);
  $("#navigation").setAttribute("aria-label", t("workspace"));
  $("#language").setAttribute("aria-label", t("language"));
  document.querySelectorAll(".remove-line").forEach(el => el.setAttribute("aria-label", t("removeLine")));
  if (snapshot) { populateSelects(); renderData(); }
}
function updateRefreshLabel() {
  $("#last-refresh").textContent = lastRefreshed ? `${t("updated")} ${new Intl.DateTimeFormat(language, {dateStyle:"short", timeStyle:"medium", timeZone:"Asia/Shanghai"}).format(lastRefreshed)} · Asia/Shanghai` : t("awaitConnection");
}
function showView(view) {
  currentView = descriptions[view] ? view : "overview";
  document.querySelectorAll("[data-panel]").forEach(el => { el.hidden = el.dataset.panel !== currentView; });
  document.querySelectorAll("[data-view]").forEach(el => { const active = el.dataset.view === currentView; el.classList.toggle("active", active); if (active) el.setAttribute("aria-current", "page"); else el.removeAttribute("aria-current"); });
  $("#page-title").textContent = t(currentView);
  $("#page-description").textContent = t(descriptions[currentView]);
}
async function api(path, body, key, loginToken) {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = {Authorization:`Bearer ${loginToken || token}`};
    if (body !== undefined) { headers["Content-Type"] = "application/json"; headers["Idempotency-Key"] = key; }
    const response = await fetch(path, {method:body === undefined ? "GET" : "POST", headers, ...(body === undefined ? {} : {body:JSON.stringify(body)}), signal:controller.signal, cache:"no-store", credentials:"same-origin"});
    let data; try { data = await response.json(); } catch { throw new Error(t("serverError")); }
    if (!response.ok) { const error = new Error(typeof data.detail === "string" ? t(data.detail) : JSON.stringify(data.detail || t("failure"))); error.status = response.status; throw error; }
    return data;
  } catch (error) { if (error.name === "AbortError" || error instanceof TypeError) { const unknown = new Error(`${t("networkError")} ${t("unknown")}`); unknown.uncertain = true; throw unknown; } throw error; }
  finally { clearTimeout(timeout); }
}
async function refresh() {
  if (!token || fetching) return;
  const version = sessionVersion;
  fetching = true; $("#refresh").disabled = true; $("#refresh").setAttribute("aria-busy", "true");
  try { const next = await api("/api/snapshot"); if (version !== sessionVersion) return; if (!next || !Array.isArray(next.orders)) throw new Error(t("serverError")); snapshot = next; populateSelects(); renderData(); lastRefreshed = new Date(); updateRefreshLabel(); }
  finally { fetching = false; $("#refresh").disabled = !token; $("#refresh").removeAttribute("aria-busy"); }
}
const field = (name, type = "text", extra = {}) => ({name, type, ...extra});
const select = (name, source, statuses) => field(name, "select", {source, statuses});
const qty = (name = "qty", min = 1) => field(name, "number", {min, value:min === 0 ? 0 : 1});
const schemas = [
  ...warehouseConfig.schemas,
  {id:"owner",area:"master",title:"ownerCreate",path:"/api/owners",admin:true,fields:[field("name")]},
  {id:"warehouse",area:"master",title:"warehouseCreate",path:"/api/warehouses",admin:true,fields:[field("name"),field("timezone","text",{value:"America/Sao_Paulo"})]},
  {id:"location",area:"master",title:"locationCreate",path:"/api/locations",staff:true,fields:[select("warehouse_id","warehouses"),field("code")]},
  {id:"sku",area:"master",title:"skuCreate",path:"/api/skus",fields:[select("owner_id","owners"),field("code"),field("barcode"),field("name")]},
  {id:"store",area:"master",title:"storeCreate",path:"/api/stores",fields:[select("owner_id","owners"),field("name")]},
  {id:"receipt",area:"inbound",title:"receiptCreate",path:"/api/receipts",staff:true,fields:[select("owner_id","owners"),select("warehouse_id","warehouses"),select("sku_id","skus"),field("reference"),qty()]},
  {id:"receipt-qc",area:"inbound",title:"receiptQc",path:"/api/receipts/:receipt_id/qc",staff:true,help:"qcHelp",fields:[select("receipt_id","receipts",["RECEIVED"]),qty("accepted_qty",0),qty("rejected_qty",0)]},
  {id:"receipt-putaway",area:"inbound",title:"receiptPutaway",path:"/api/receipts/:receipt_id/putaway",staff:true,fields:[select("receipt_id","receipts",["QC_DONE"]),select("location_id","locations")]},
  {id:"order",area:"order",title:"orderCreate",path:"/api/orders",help:"orderLineHelp",fields:[select("owner_id","owners"),select("warehouse_id","warehouses"),select("store_id","stores"),field("reference")],lines:true},
  {id:"reserve",area:"order",title:"reserve",path:"/api/orders/:order_id/reserve",staff:true,fields:[select("order_id","orders",["CREATED"])]},
  {id:"cancel",area:"order",title:"cancel",path:"/api/orders/:order_id/cancel",help:"cancelHelp",fields:[select("order_id","orders",["CREATED","RESERVED"])]},
  {id:"pick",area:"pda",title:"pick",path:"/api/orders/:order_id/pick",staff:true,help:"scanQtyHelp",fields:[select("order_id","orders",["RESERVED","PICKING"]),field("barcode"),select("location_id","locations"),qty()]},
  {id:"verify",area:"pda",title:"verify",path:"/api/orders/:order_id/verify",staff:true,fields:[select("order_id","orders",["PICKED"]),field("barcode"),qty()]},
  {id:"pack",area:"pda",title:"pack",path:"/api/orders/:order_id/pack",staff:true,fields:[select("order_id","orders",["VERIFIED"]),field("package_reference")]},
  {id:"ship",area:"pda",title:"ship",path:"/api/orders/:order_id/ship",staff:true,fields:[select("order_id","orders",["PACKED"]),field("tracking_number"),field("carrier")]},
  {id:"return",area:"return",title:"returnCreate",path:"/api/returns",fields:[select("order_id","orders",["SHIPPED"]),select("sku_id","skus"),qty(),field("reference")]},
  {id:"return-receive",area:"return",title:"returnReceive",path:"/api/returns/:return_id/receive",staff:true,fields:[select("return_id","returns",["EXPECTED"])]},
  {id:"return-qc",area:"return",title:"returnQc",path:"/api/returns/:return_id/qc",staff:true,help:"qcHelp",fields:[select("return_id","returns",["RECEIVED"]),qty("accepted_qty",0),qty("rejected_qty",0)]},
  {id:"return-putaway",area:"return",title:"returnPutaway",path:"/api/returns/:return_id/putaway",staff:true,fields:[select("return_id","returns",["QC_DONE"]),select("location_id","locations")]},
  {id:"fee",area:"fee",title:"feeCreate",path:"/api/fees",admin:true,help:"feeFormHelp",fields:[select("order_id","orders",["SHIPPED"]),field("code"),qty("amount_cents")]}
];
function makeField(spec, prefix) {
  const wrapper = node("div", undefined, "field"), id = `${prefix}-${spec.name}`;
  const label = node("label", t(spec.name)); label.htmlFor = id; label.dataset.i18n = spec.name; wrapper.append(label);
  const input = document.createElement(spec.type === "select" ? "select" : "input"); input.name = spec.name; input.id = id; input.required = true; input.dataset.testid = id;
  if (spec.type === "select") {
    if (spec.options) { input.dataset.options = JSON.stringify(spec.options); spec.options.forEach(value => { const option = node("option",t(value)); option.value = value; input.append(option); }); }
    else input.dataset.source = spec.source;
    if (spec.statuses) input.dataset.statuses = spec.statuses.join(",");
    if (spec.multiple) { input.multiple = true; input.size = 6; }
  }
  else { input.type = spec.type; input.autocomplete = "off"; input.maxLength = 200; if (spec.value !== undefined) { input.value = spec.value; input.defaultValue = spec.value; } if (spec.type === "number") { input.min = spec.min; input.max = 1000000000; input.step = "1"; input.inputMode = "numeric"; } if (spec.name === "barcode") { input.spellcheck = false; input.setAttribute("autocapitalize","off"); } }
  wrapper.append(input); return wrapper;
}
function addOrderLine() {
  const wrap = $("#order-lines"), index = Number(wrap.dataset.count || 0) + 1; wrap.dataset.count = index;
  const row = node("div", undefined, "order-line"); row.dataset.testid = "order-line";
  const skuField = makeField(select("sku_id","skus"), `line-${index}`), qtyField = makeField(qty(), `line-${index}`), remove = node("button","×","remove-line"); remove.type = "button"; remove.setAttribute("aria-label",t("removeLine")); remove.addEventListener("click", () => { if (wrap.children.length > 1) row.remove(); });
  row.append(skuField, qtyField, remove); wrap.append(row); if (snapshot) populateSelects(row);
}
function buildForms() {
  schemas.forEach((schema, index) => {
    const card = node("article", undefined,"card form-card"); card.dataset.schema = schema.id;
    const heading = node("div",undefined,"form-head"), title = node("h2",t(schema.title)); title.dataset.i18n = schema.title; heading.append(node("span",String(index + 1).padStart(2,"0"),"form-number"),title); card.append(heading);
    const form = document.createElement("form"); form.className = "business-form"; form.id = `${schema.id}-form`; form.dataset.action = schema.id; form.dataset.testid = form.id;
    schema.fields.forEach(spec => form.append(makeField(spec,schema.id)));
    if (schema.lines) { const fieldset = document.createElement("fieldset"), legend = node("legend",t("lines")), lines = node("div"), add = node("button",t("addLine"),"text-button add-line"); legend.dataset.i18n = "lines"; lines.id = "order-lines"; fieldset.append(legend,lines); form.append(fieldset); add.type = "button"; add.id = "add-order-line"; add.dataset.i18n = "addLine"; add.addEventListener("click",addOrderLine); form.append(add); }
    if (schema.help) { const help = node("p",t(schema.help),"form-help"); help.dataset.i18n = schema.help; form.append(help); }
    const submit = node("button",t("submit"),"button"); submit.type = "submit"; submit.dataset.i18n = "submit"; submit.dataset.testid = `${schema.id}-submit`; form.append(submit);
    const result = node("div",undefined,"form-result"); result.dataset.testid = `${schema.id}-result`; result.setAttribute("role","status"); result.setAttribute("aria-live","polite"); form.append(result);
    form.addEventListener("submit",event => { event.preventDefault(); submitForm(form,schema); }); card.append(form); $(`#${schema.area}-forms`).append(card);
  });
  addOrderLine();
}
function populateSelects(root = document) {
  $('[data-view="waves"]').hidden = !user || !["admin","staff","picker"].includes(user.role);
  $('[data-view="movements"]').hidden = !user || !["admin","staff","picker","receiver"].includes(user.role);
  root.querySelectorAll("select[data-options]").forEach(selectEl => [...selectEl.options].forEach(option => { option.textContent = t(option.value); }));
  root.querySelectorAll("select[data-source]").forEach(selectEl => {
    const previous = selectEl.value, statuses = selectEl.dataset.statuses?.split(","), selected = new Set([...selectEl.selectedOptions].map(option => option.value));
    let items = array(selectEl.dataset.source); if (statuses) items = items.filter(record => statuses.includes(record.status));
    const form = selectEl.closest("form"), ownerId = form?.querySelector('[name="owner_id"]')?.value, warehouseId = form?.querySelector('[name="warehouse_id"]')?.value;
    if (["skus","stores"].includes(selectEl.dataset.source) && ownerId) items = items.filter(item => item.owner_id === ownerId);
    if (selectEl.dataset.source === "locations" && warehouseId) items = items.filter(item => item.warehouse_id === warehouseId);
    if (selectEl.name === "order_ids") items = items.filter(item => (!ownerId || item.owner_id === ownerId) && (!warehouseId || item.warehouse_id === warehouseId) && !array("wave_orders").some(link => link.order_id === item.id && link.active));
    if (selectEl.dataset.source === "pick_tasks" && ["task-scan-form","task-release-form"].includes(form?.id)) items = items.filter(item => item.assignee_id === user?.id && (form.id !== "task-release-form" || item.picked_qty === 0));
    if (form?.id === "pick-form" && selectEl.name === "order_id") items = items.filter(item => !array("wave_orders").some(link => link.order_id === item.id && link.active));
    if (selectEl.name === "source_inventory_id") items = items.filter(item => item.available > 0);
    if (selectEl.name === "destination_location_id") { const sourceId = form?.querySelector('[name="source_inventory_id"]')?.value, source = array("inventory").find(item => item.id === sourceId); if (source) items = items.filter(item => item.warehouse_id === source.warehouse_id && item.id !== source.location_id); }
    if (selectEl.dataset.source === "movements" && ["movement-dispatch-form","movement-receive-form","movement-release-form"].includes(form?.id)) items = items.filter(item => item.assignee_id === user?.id);
    selectEl.replaceChildren(); const placeholder = node("option",items.length ? t("choose") : t("noOptions")); placeholder.value = ""; selectEl.append(placeholder);
    if (selectEl.multiple) selectEl.replaceChildren();
    items.forEach(record => {
      let label = recordLabel(record);
      if (selectEl.dataset.source === "inventory") label = `${shortLookup("owners",record.owner_id)} · ${shortLookup("warehouses",record.warehouse_id)} · ${shortLookup("skus",record.sku_id)} · ${shortLookup("locations",record.location_id)} · ${t("available")}: ${record.available}`;
      if (selectEl.dataset.source === "pick_tasks") label = `${shortLookup("waves",record.wave_id)} · #${record.sequence} · ${shortLookup("orders",record.order_id)} · ${shortLookup("locations",record.location_id)} · ${shortLookup("skus",record.sku_id)} · ${record.picked_qty}/${record.qty}`;
      const option = node("option",label); option.value = record.id; if (selectEl.multiple) option.selected = selected.has(record.id); selectEl.append(option);
    });
    if (selectEl.multiple) return;
    if (items.some(item => item.id === previous)) selectEl.value = previous;
    else if (items.length === 1) selectEl.value = items[0].id;
  });
  schemas.forEach(schema => { const card = document.querySelector(`[data-schema="${schema.id}"]`); card.hidden = Boolean(user && user.role !== "admin" && !actionRoles[schema.id].includes(user.role)); });
}
async function submitForm(form,schema) {
  if (!token) { message(t("needLogin"),true); return; }
  if (form.dataset.busy === "true") return;
  const values = {}; schema.fields.forEach(spec => { const control = form.elements.namedItem(spec.name), raw = control.value; values[spec.name] = spec.multiple ? [...control.selectedOptions].map(option => option.value) : spec.type === "number" ? Number(raw) : raw.trim(); });
  let path = schema.path; const body = {...values};
  const match = path.match(/:([a-z_]+)/); if (match) { path = path.replace(match[0],encodeURIComponent(values[match[1]])); delete body[match[1]]; }
  if (schema.lines) body.lines = [...form.querySelectorAll(".order-line")].map(row => ({sku_id:row.querySelector('[name="sku_id"]').value,qty:Number(row.querySelector('[name="qty"]').value)}));
  const signature = `${path}|${JSON.stringify(body)}`; let operation = submissions.get(form);
  if (!operation || (!operation.uncertain && operation.signature !== signature)) { operation = {signature,path,body,key:crypto.randomUUID(),uncertain:false}; submissions.set(form,operation); }
  const version = sessionVersion;
  form.dataset.busy = "true"; form.setAttribute("aria-busy","true");
  const submit = form.querySelector('[type="submit"]'), result = form.querySelector(".form-result"); submit.disabled = true; submit.textContent = t("sending"); result.textContent = ""; result.className = "form-result"; delete result.dataset.recordId; delete result.dataset.recordStatus;
  try {
    const record = await api(operation.path,operation.body,operation.key); if (version !== sessionVersion) return; submissions.delete(form); operation.uncertain = false;
    result.className = "form-result success"; result.dataset.recordId = record.id || values.order_id || values.receipt_id || values.return_id || "✓"; result.dataset.recordStatus = record.status || ""; result.textContent = `${t("success")} · ${result.dataset.recordId}${record.status ? ` · ${statusLabel(record.status)}` : ""}`;
    try { await refresh(); } catch (error) { message(`${t("refreshFailed")} ${error.message}`,true); }
  } catch (error) { if (version !== sessionVersion) return; operation.uncertain = Boolean(error.uncertain || error.status >= 500); result.className = "form-result error"; result.textContent = error.message; if (error.status === 401) message(t("authFailed"),true); }
  finally { form.dataset.busy = "false"; form.removeAttribute("aria-busy"); submit.disabled = false; submit.dataset.i18n = operation.uncertain ? "retryPending" : "submit"; submit.textContent = t(submit.dataset.i18n); form.querySelectorAll("input,select,button[type=button]").forEach(control => { control.disabled = operation.uncertain; }); }
}
function rowTimezone(record) { return array("warehouses").find(item => item.id === record.warehouse_id)?.timezone || "America/Sao_Paulo"; }
function shortLookup(key,id) { const row = array(key).find(item => item.id === id); return row ? row.name || row.code || row.reference || row.id : id; }
function formatValue(key,value,record = {},compact = false) {
  if (value === undefined || value === null || value === "") return "—";
  const linked = {owner_id:"owners",warehouse_id:"warehouses",sku_id:"skus",location_id:"locations",store_id:"stores",order_id:"orders",wave_id:"waves",source_location_id:"locations",destination_location_id:"locations"};
  if (linked[key]) return compact ? shortLookup(linked[key],value) : lookup(linked[key],value);
  if (key === "assignee_id" && value === user?.id) return user.name;
  if (key === "kind") return t(value);
  if (key === "amount_cents") return new Intl.NumberFormat(language,{style:"currency",currency:"BRL"}).format(value / 100);
  if (key.endsWith("_at")) { const date = new Date(value); if (!Number.isNaN(date.getTime())) return new Intl.DateTimeFormat(language,{dateStyle:"short",timeStyle:"short",timeZone:rowTimezone(record)}).format(date); }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
function table(target,rows,columns) {
  const el = typeof target === "string" ? $(target) : target; el.replaceChildren();
  if (!rows.length) { el.append(node("div",t("empty"),"empty")); return; }
  const wrap = node("div",undefined,"table-wrap"), tableEl = document.createElement("table"), head = document.createElement("thead"), header = document.createElement("tr");
  columns.forEach(key => { const th = node("th",t(key === "amount_cents" ? "amount" : key)); th.scope = "col"; header.append(th); }); head.append(header); tableEl.append(head);
  const tbody = document.createElement("tbody"); rows.forEach(record => { const row = document.createElement("tr"); if (record.id) row.dataset.recordId = record.id; columns.forEach(key => { const cell = document.createElement("td"); if (key === "status") { cell.append(node("span",statusLabel(record[key] || "—"),`badge status${["CANCELLED","EXPECTED"].includes(record[key]) ? " pending" : ""}`)); } else { cell.textContent = formatValue(key,record[key],record,["wave-records","task-records","movement-records"].includes(el.id)); if (key === "id") cell.className = "id-cell"; if (key.endsWith("_at")) cell.title = rowTimezone(record); } cell.dataset.column = key; row.append(cell); }); tbody.append(row); }); tableEl.append(tbody); wrap.append(tableEl); el.append(wrap);
}
function renderData() {
  if (!snapshot) return;
  const activeOrders = array("orders").filter(item => !["SHIPPED","CANCELLED"].includes(item.status));
  const inventory = array("inventory"), received = array("receipts").filter(item => item.status !== "PUTAWAY");
  const metrics = [["inboundPending",received.length,"receiptMetric","↙"],["orderActive",activeOrders.length,"orderMetric","↗"],["on_hand",inventory.reduce((sum,item) => sum + item.on_hand,0),"skuMetric","▥"],["available",inventory.reduce((sum,item) => sum + item.available,0),"availableMetric","✓"]];
  $("#metrics").replaceChildren(...metrics.map(([label,value,help,icon]) => { const card = node("article",undefined,"metric"), labelEl = node("div",undefined,"metric-label"); labelEl.append(node("span",t(label)),node("span",icon)); card.append(labelEl,node("div",new Intl.NumberFormat(language).format(value),"metric-value"),node("div",t(help),"metric-foot")); return card; }));
  const stages = [["CREATED","orderCreate"],["RESERVED","reserve"],["PICKING","pick"],["PICKED","verify"],["VERIFIED","pack"],["PACKED","ship"]];
  $("#flow").replaceChildren(...stages.map(([status,key]) => { const stage = node("div",undefined,"flow-stage"); stage.append(node("strong",array("orders").filter(row => row.status === status).length),node("span",t(key))); return stage; }));
  const check = snapshot.reconciliation, valid = check?.ok === true;
  $("#integrity-dot").className = `status-dot ${valid ? "good" : "bad"}`;
  $("#reconciliation-summary").replaceChildren(node("div",t(check ? valid ? "noStockIssues" : "stockIssues" : "unavailable"),"integrity-value"),node("p",t("reconcileHelp"),"integrity-copy"));
  const issues = $("#reconciliation-records"); issues.replaceChildren(node("div",t(check ? valid ? "noStockIssues" : "stockIssues" : "unavailable"),valid ? "badge" : "badge warning"));
  if (Array.isArray(check?.issues)) check.issues.forEach(issue => issues.append(node("div",typeof issue === "string" ? issue : JSON.stringify(issue),"issue")));
  const orderColumns = ["reference","owner_id","warehouse_id","store_id","status","id"];
  table("#recent-orders",array("orders").slice(-5).reverse(),orderColumns);
  table("#order-records",array("orders").slice().reverse(),orderColumns);
  table("#wave-records",array("waves"),["reference","owner_id","warehouse_id","status","created_at","id"]);
  table("#task-records",array("pick_tasks"),["wave_id","sequence","location_id","sku_id","order_id","qty","picked_qty","status","assignee_id","id"]);
  table("#movement-records",array("movements").slice().reverse(),["reference","kind","source_location_id","destination_location_id","sku_id","qty","status","assignee_id","id"]);
  table("#receipt-records",array("receipts").slice().reverse(),["reference","owner_id","warehouse_id","sku_id","qty","accepted_qty","rejected_qty","status","id"]);
  table("#inventory-records",inventory,["owner_id","warehouse_id","sku_id","location_id","on_hand","reserved","picked","move_reserved","available"]);
  table("#stock-quality-records",array("stock_summary"),["owner_id","warehouse_id","sku_id","on_hand","move_reserved","in_transit","pending_qc","qualified_unstored","rejected","physical_total"]);
  const ledgerCols = ["created_at","owner_id","warehouse_id","sku_id","location_id","event_type","on_hand_delta","reserved_delta","picked_delta","move_reserved_delta","in_transit_delta","source_id","id"];
  const ledgerRows = array("ledger").map(item => ({...item,event_type:item.event_type || item.type || item.kind,on_hand_delta:item.on_hand_delta ?? item.delta_on_hand ?? item.delta,reserved_delta:item.reserved_delta ?? item.delta_reserved,picked_delta:item.picked_delta ?? item.delta_picked,source_id:item.source_id || item.reference_id || item.event_id}));
  table("#ledger-records",ledgerRows.slice().reverse(),ledgerCols);
  const masterRecords = $("#master-records"); masterRecords.replaceChildren();
  [["owners","owner",["name","id"]],["warehouses","warehouse",["name","id"]],["locations","location",["code","warehouse_id","id"]],["skus","sku",["code","name","barcode","owner_id","id"]],["stores","store",["name","owner_id","id"]]].forEach(([key,title,cols]) => { const group = node("div",undefined,"master-group"), data = node("div"); group.append(node("h3",t(title)),data); table(data,array(key),cols); masterRecords.append(group); });
  const allocations = $("#allocation-records"); allocations.replaceChildren();
  [["order_lines","orderLines",["order_id","sku_id","qty","verified_qty","id"]],["allocations","allocation",["order_id","sku_id","location_id","qty","picked_qty","id"]]].forEach(([key,title,cols]) => { allocations.append(node("h3",t(title))); const container = node("div"), rows = key === "allocations" ? array(key).map(item => { const inventory = array("inventory").find(inv => inv.id === item.inventory_id); return {...item,sku_id:inventory?.sku_id,location_id:inventory?.location_id}; }) : array(key); table(container,rows,cols); allocations.append(container); });
  table("#return-records",array("returns").slice().reverse(),["reference","order_id","sku_id","qty","accepted_qty","rejected_qty","status","id"]);
  table("#fee-records",array("fees").slice().reverse(),["order_id","code","amount_cents","currency","created_at","id"]);
  renderIntegrations(); renderRoadmap();
}
function safeLink(value) { try { const url = new URL(value); return url.protocol === "https:" ? url.href : null; } catch { return null; } }
function renderIntegrations() {
  const el = $("#integration-records"); el.replaceChildren();
  const integrations = snapshot.integrations;
  const records = Array.isArray(integrations) ? integrations : Object.entries(integrations || {}).map(([name,value]) => ({name,...(typeof value === "object" ? value : {status:value})}));
  if (!records.length) { el.append(node("div",t("notConnected"),"empty")); return; }
  records.forEach(integration => {
    const card = node("article",undefined,"card integration-card"); card.append(node("h2",integration.name || integration.id || integration.provider || "ERP"),node("span",t("pendingAuthorization"),"badge warning"));
    const dl = document.createElement("dl");
    const entries = [["integrationStatus",(language === "pt-BR" ? integration.status_pt : integration.status_zh) || t("notConnected")],["capabilities",t("notConnected")],["evidence",language === "pt-BR" ? integrationBlockerPt[integration.id] || t("notConnected") : integration.blockers || integration.blocker || integration.notes || integration.evidence || t("notConnected")]];
    entries.forEach(([key,value]) => { dl.append(node("dt",t(key)),node("dd",Array.isArray(value) ? value.map(v => typeof v === "string" ? v : JSON.stringify(v)).join(" · ") || t("unsupported") : typeof value === "object" ? JSON.stringify(value) : statusLabel(value))); });
    card.append(dl);
    const sources = integration.sources || integration.official_docs || integration.documentation || integration.docs || integration.official_sources || integration.official_url || integration.documentation_url || [];
    (Array.isArray(sources) ? sources : [sources]).forEach(source => { const href = safeLink(typeof source === "object" ? source.url : source); if (!href) return; const link = node("a",t("officialDocs")); link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer"; card.append(link,node("br")); });
    el.append(card);
  });
}
function renderRoadmap() {
  const rows = [["coreScope","coreScopeHelp","implemented"],["extendedScope","extendedScopeHelp","implemented"],["waveScope","waveHelp","implemented"],["moveScope","moveScopeHelp","implemented"],["efficiencyScope","efficiencyScopeHelp","unsupported"],["financeScope",null,"unsupported"],["advancedScope",null,"unsupported"],["devicesScope",null,"devicePending"],["productionScope","productionHelp","pendingAuthorization"]];
  $("#roadmap-records").replaceChildren(...rows.map(([title,help,status]) => { const row = node("div",undefined,"roadmap-row"), text = node("div"); text.append(node("strong",t(title))); if (help) text.append(node("p",t(help))); row.append(text,node("span",t(status),`badge${status === "implemented" ? "" : " warning"}`)); return row; }));
}
function logout() {
  $('[data-view="waves"]').hidden = true; $('[data-view="movements"]').hidden = true;
  ["#wave-records","#task-records","#movement-records"].forEach(selector => $(selector).replaceChildren());
  showView("overview");
  sessionVersion++; token = ""; user = null; snapshot = null; lastRefreshed = null; $("#api-token").value = ""; $("#connected-content").hidden = true; $("#login-panel").hidden = false; $("#logout").hidden = true; $("#identity").textContent = t("disconnected"); $("#refresh").disabled = true;
  document.querySelectorAll(".form-result").forEach(el => { el.textContent = ""; delete el.dataset.recordId; delete el.dataset.recordStatus; });
  document.querySelectorAll(".business-form").forEach(form => { submissions.delete(form); form.reset(); form.querySelectorAll("input,select,button").forEach(control => { control.disabled = false; }); const submit = form.querySelector('[type="submit"]'); submit.dataset.i18n = "submit"; submit.textContent = t("submit"); });
  document.querySelectorAll("select[data-source]").forEach(el => el.replaceChildren());
  ["#metrics","#flow","#reconciliation-summary","#master-records","#receipt-records","#order-records","#allocation-records","#inventory-records","#stock-quality-records","#ledger-records","#reconciliation-records","#return-records","#fee-records","#integration-records","#recent-orders"].forEach(selector => $(selector).replaceChildren());
  $("#last-refresh").textContent = t("awaitConnection"); message(t("sessionEnded"));
}
buildForms(); translate();
document.addEventListener("click",event => { const view = event.target.closest("[data-view],[data-go]"); if (view) showView(view.dataset.view || view.dataset.go); const mode = event.target.closest("[data-mode]"); if (mode) { document.querySelectorAll("[data-mode]").forEach(el => el.classList.toggle("active",el === mode)); showView(mode.dataset.mode === "pda" ? "pda" : mode.dataset.mode === "oms" ? "orders" : "overview"); } });
document.addEventListener("change",event => { if (["owner_id","warehouse_id","source_inventory_id"].includes(event.target.name) && snapshot) populateSelects(event.target.closest("form")); });
$("#language").addEventListener("change",event => { language = event.target.value; translate(); });
$("#logout").addEventListener("click",logout);
$("#refresh").addEventListener("click",async () => { try { await refresh(); $("#notice").hidden = true; } catch (error) { message(error.message,true); } });
$("#login-form").addEventListener("submit",async event => {
  event.preventDefault(); const button = event.target.querySelector("button"), candidate = $("#api-token").value.trim().replace(/^Bearer\s+/i,""); button.disabled = true; button.textContent = t("loading");
  try {
    const me = await api("/api/me",undefined,undefined,candidate); token = candidate; user = me; $("#api-token").value = "";
    await refresh(); $("#login-panel").hidden = true; $("#connected-content").hidden = false; $("#logout").hidden = false; $("#identity").textContent = `${user.name} · ${user.role}`; $("#notice").hidden = true;
    const preferredMode = user.role.startsWith("owner") ? "oms" : "wms";
    document.querySelectorAll("[data-mode]").forEach(el => el.classList.toggle("active",el.dataset.mode === preferredMode));
    if (preferredMode === "oms") showView("orders");
  } catch (error) { token = ""; user = null; snapshot = null; $("#refresh").disabled = true; message(error.message,true); }
  finally { button.disabled = false; button.textContent = t("connect"); }
});
