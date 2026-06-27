from pydantic import BaseModel


class FormField(BaseModel):
    selector: str
    field_type: str
    value: str | bool
