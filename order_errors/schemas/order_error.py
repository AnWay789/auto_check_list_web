from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class OrderError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    order_date: datetime = Field(alias='ts')
    number: str = Field(alias='number')

    customer_name: str = Field(alias='customer_name')
    customer_phone: str = Field(alias='customer_phone')

    rk_name: str | None = Field(alias='rk_name')
    store_id: str = Field(alias='store_id')
    store_address: str | None = Field(alias='store_address')

    products: list[str] = Field(default_factory=list)
    order_sum: float = Field(default=0.0)

    error: str = Field(alias='error')
    recommended_action: str | None = Field(default=None, alias='recommended_action')

class RawOrderError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    order_date: datetime = Field(alias='ts')
    number: str = Field(alias='number')

    customer_name: str = Field(alias='customer_name')
    customer_phone: str = Field(alias='customer_phone', default='')

    rk_name: str | None = Field(alias='rk_name', default=None)
    store_id: str = Field(alias='store_id', default='')
    store_address: str | None = Field(alias='store_address', default=None)

    product_guid: str = Field(alias='pr_guid')
    product_name: str = Field(alias='pr_name')
    product_code: str = Field(alias='pr_code')
    product_price: float = Field(alias='price', default=0.0)

    error: str = Field(alias='error')

    ordered: int = Field(alias='ordered_qty')
    one_s_stock: int = Field(alias='one_s_qty', default=0)
    ecom_stock: int = Field(alias='ecom_qty')
    stock_status: str = Field(alias='stock_status')
