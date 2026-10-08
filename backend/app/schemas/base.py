from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """Base for every request and response model.

    NaN and infinity are rejected, unknown fields are rejected, strings are stripped so
    bounds apply to what the user actually typed, and ORM objects can be read directly.
    """

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        str_strip_whitespace=True,
        from_attributes=True,
    )
