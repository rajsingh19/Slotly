from pydantic import BaseModel, ConfigDict


class HospitalBase(BaseModel):
    name: str
    address: str
    contact_number: str


class HospitalCreate(HospitalBase):
    pass


class HospitalOut(HospitalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
