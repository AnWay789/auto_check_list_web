from pydantic import BaseModel
from datetime import datetime

class PhoneNumber(BaseModel):
    number: str
    code: str

class CustomFormDefault(BaseModel):
    Data_zakaza: list[str]
    order: list[str]
    RK: list[str]
    Adres: list[str]
    Naimenovanie: list[str]
    sum: list[str]
    prichina: list[str]
    comment: list[str]

class CustomForm(BaseModel):
    default: CustomFormDefault

class NaumenErrorRequest(BaseModel):
    title: str
    state: str
    scheduledTime: datetime
    comment: str
    phoneNumbers: list[PhoneNumber]
    customForm: CustomForm
