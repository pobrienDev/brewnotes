from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """Base for every request and response model.

    NaN and infinity are rejected, unknown fields are rejected, and strings are stripped so
    bounds apply to what the user actually typed.
    """

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        str_strip_whitespace=True,
    )
