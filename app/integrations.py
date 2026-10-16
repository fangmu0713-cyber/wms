"""Explicit ERP capability boundaries; no configured vendor transport in phase 1.

Documentation availability is deliberately separate from implementation and account
authorization. This module never converts a pending connector into a successful call.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


VERIFIED_ON = "2026-10-16"


class Capability(str, Enum):
    PRODUCTS = "products"
    WAREHOUSES = "warehouses"
    CHANNELS = "channels"
    INVENTORY_READ = "inventory_read"
    INVENTORY_WRITE = "inventory_write"
    ORDERS_READ = "orders_read"
    ORDERS_RECEIVE = "orders_receive"
    RECEIPTS = "receipts"
    RETURNS = "returns"
    LABELS = "labels"
    CANCELLATIONS = "cancellations"
    SHIPMENTS = "shipments"
    BILLING = "billing"
    ATTACHMENTS = "attachments"


class IntegrationError(RuntimeError):
    """Safe public message: no credential or supplier response contents."""


class UnsupportedCapability(IntegrationError):
    pass


class ConnectorNotConfigured(IntegrationError):
    pass


@dataclass(frozen=True)
class ExternalWarehouse:
    external_id: str
    name: str


@dataclass(frozen=True)
class InventoryObservation:
    """External reconciliation input, never an instruction to overwrite stock."""

    warehouse_external_id: str
    sku_external_id: str
    quantity: int
    quantity_basis: str  # Supplier's documented basis, e.g. sellable, not assumed.
    observed_at: str


@dataclass(frozen=True)
class ExternalOrderLine:
    sku_external_id: str
    quantity: int


@dataclass(frozen=True)
class ExternalOrder:
    external_id: str
    store_external_id: str
    lines: tuple[ExternalOrderLine, ...]
    external_version: str


@dataclass(frozen=True)
class ShipmentNotice:
    order_external_id: str
    package_external_id: str
    tracking_number: str
    carrier: str
    lines: tuple[ExternalOrderLine, ...]
    source_event_id: str


@runtime_checkable
class ERPAdapter(Protocol):
    provider: str

    def list_warehouses(self) -> tuple[ExternalWarehouse, ...]: ...

    def read_inventory(self, *, warehouse_external_ids: tuple[str, ...], cursor: str | None = None) -> tuple[tuple[InventoryObservation, ...], str | None]: ...

    def read_orders(self, *, cursor: str | None = None) -> tuple[tuple[ExternalOrder, ...], str | None]: ...

    def send_shipment(self, notice: ShipmentNotice) -> None: ...

    def execute(self, capability: Capability, payload: Mapping[str, Any]) -> Any: ...


_SOURCES = {
    "upseller": ["https://www.upseller.com/zh-CN/help-doc-article-3403", "https://www.upseller.com/zh-CN/help-doc-article-3365"],
    "dianxiaomi": ["https://help.dianxiaomi.com/article/freightForwarderAuthorization/3075"],
    "lingxing": ["https://apidoc.lingxing.com/new/guides/new-instructions/"],
    "mabang": ["https://help.mabangerp.com/nested/details?id=3034&resource_id=1"],
    "bling": ["https://developer.bling.com.br/bling-api", "https://developer.bling.com.br/referencia", "https://developer.bling.com.br/aplicativos", "https://developer.bling.com.br/limites"],
}

_NAMES = {"upseller": "UpSeller", "dianxiaomi": "店小秘", "lingxing": "领星", "mabang": "马帮", "bling": "Bling"}
_BLOCKERS = {
    "upseller": "待接入：官方鉴权头和响应字段为图片，本环境未能读取；未提供符合套餐的主账号授权。海外仓服务商推单另需商务协议和技术文档。",
    "dianxiaomi": "待接入：官方示例页面本次读取失败；服务商准入、协议、接口文档和测试账号待确认。",
    "lingxing": "待接入：缺少企业 AppID/AppSecret、获批 API 范围及稳定公网 IP 白名单；业务接口逐项待核验。",
    "mabang": "待接入：官方入口读取失败，仅索引找到历史企业凭证指引；当前版本、接口权限、凭证和业务协议待确认。",
    "bling": "待接入：缺少 OAuth 应用与账户授权；资源目录未展开，具体接口、权限和库存状态副作用待核验。公开应用另需审核。",
}

# Exact public URL facts only; no guessed authentication fields or response maps.
_UPSELLER_READ_ENDPOINTS = {
    Capability.WAREHOUSES: "https://openapi.upseller.com/erp/inventory/getWarehouseList/v1",
    Capability.INVENTORY_READ: "https://openapi.upseller.com/erp/inventory/pageWarehouseSku/v1",
}


def get_registry() -> list[dict[str, Any]]:
    """Fresh, JSON-serializable public metadata, safe for tenant-scoped snapshots."""
    result = []
    for provider, name in _NAMES.items():
        capabilities = []
        for capability in Capability:
            documented = provider == "upseller" and capability in _UPSELLER_READ_ENDPOINTS
            capabilities.append({
                "name": capability.value,
                "documented": documented,
                "implemented": False,
                "enabled": False,
                "live_tested": False,
                "endpoint": _UPSELLER_READ_ENDPOINTS[capability] if documented else None,
                "method": "POST" if documented else None,
            })
        result.append({
            "id": provider,
            "name": name,
            "status": "pending_integration",
            "status_zh": "待接入",
            "status_pt": "Integração pendente",
            "verified_on": VERIFIED_ON,
            "configured": False,
            "production_enabled": False,
            "implemented_methods": [],
            "live_tested_methods": [],
            "sources": deepcopy(_SOURCES[provider]),
            "blocker": _BLOCKERS[provider],
            "paths": {"seller_api": "pending", "warehouse_provider": "pending", "own_api": "separate_system_api"},
            "capabilities": capabilities,
        })
    return result


class PendingAdapter:
    """Fail closed until an actual, reviewed provider adapter is implemented."""

    def __init__(self, provider: str):
        if provider not in _NAMES:
            raise ValueError("Unknown ERP provider")
        self.provider = provider

    def execute(self, capability: Capability, payload: Mapping[str, Any]) -> Any:
        # Never echo payload: it may contain customer details or credentials.
        try:
            requested = Capability(capability)
        except (TypeError, ValueError):
            raise UnsupportedCapability("Unsupported ERP capability") from None
        if self.provider == "upseller" and requested in _UPSELLER_READ_ENDPOINTS:
            raise ConnectorNotConfigured(_BLOCKERS[self.provider])
        raise UnsupportedCapability(f"{_NAMES[self.provider]}: {requested.value} 未实现或官方业务协议尚未核验")

    def list_warehouses(self) -> tuple[ExternalWarehouse, ...]:
        return self.execute(Capability.WAREHOUSES, {})

    def read_inventory(self, *, warehouse_external_ids: tuple[str, ...], cursor: str | None = None) -> tuple[tuple[InventoryObservation, ...], str | None]:
        return self.execute(Capability.INVENTORY_READ, {"warehouse_external_ids": warehouse_external_ids, "cursor": cursor})

    def read_orders(self, *, cursor: str | None = None) -> tuple[tuple[ExternalOrder, ...], str | None]:
        return self.execute(Capability.ORDERS_READ, {"cursor": cursor})

    def send_shipment(self, notice: ShipmentNotice) -> None:
        self.execute(Capability.SHIPMENTS, {"notice": notice})


def create_adapter(provider: str) -> ERPAdapter:
    return PendingAdapter(provider)
