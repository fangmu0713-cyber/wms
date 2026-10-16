from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictInt

Text = Annotated[str, Field(min_length=1, max_length=160, strip_whitespace=True)]
Qty = Annotated[StrictInt, Field(gt=0, le=1_000_000)]
Count = Annotated[StrictInt, Field(ge=0, le=1_000_000)]

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Named(Input):
    name: Text

class Warehouse(Named):
    timezone: Text = 'America/Sao_Paulo'

class Location(Input):
    warehouse_id: Text
    code: Text

class SKU(Input):
    owner_id: Text
    code: Text
    barcode: Text
    name: Text

class Store(Named):
    owner_id: Text

class Receipt(Input):
    owner_id: Text
    warehouse_id: Text
    sku_id: Text
    reference: Text
    qty: Qty

class QC(Input):
    accepted_qty: Count
    rejected_qty: Count

class Putaway(Input):
    location_id: Text

class Line(Input):
    sku_id: Text
    qty: Qty

class Order(Input):
    owner_id: Text
    warehouse_id: Text
    store_id: Text
    reference: Text
    lines: Annotated[list[Line], Field(min_length=1,max_length=200)]

class Pick(Input):
    barcode: Text
    location_id: Text
    qty: Qty

class Verify(Input):
    barcode: Text
    qty: Qty

class Pack(Input):
    package_reference: Text

class Ship(Input):
    tracking_number: Text
    carrier: Text

class Return(Input):
    order_id: Text
    sku_id: Text
    qty: Qty
    reference: Text

class Fee(Input):
    order_id: Text
    code: Text
    amount_cents: Annotated[StrictInt,Field(gt=0,le=1_000_000_000)]

class Empty(Input):
    pass
