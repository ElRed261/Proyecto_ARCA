from pydantic import BaseModel
from typing import Optional

class AccountBase(BaseModel):
    code: str
    name: str
    type: str

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    id: int

    class Config:
        from_attributes = True
