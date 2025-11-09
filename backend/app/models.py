from pydantic import BaseModel


class ExtractResponse(BaseModel):
    pages: int
    kind: str
    language: str
    text_preview: str

