from pydantic import BaseModel


class PaginationResponse(BaseModel):
    page: int
    limit: int
    total_data: int
    total_page: int
