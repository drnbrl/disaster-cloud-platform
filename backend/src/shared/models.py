from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PriorityLevel = Literal["low", "medium", "high", "critical"]
RequestStatus = Literal["RECEIVED", "REVIEWED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"]


class CreateRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    city: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=5, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    message: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def coordinates_are_paired(self) -> "CreateRequestInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class Needs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    water: bool = False
    food: bool = False
    shelter: bool = False
    medical: bool = False
    electricity: bool = False
    baby_support: bool = False


class AiAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people_count: int | None = Field(default=None, ge=0, le=1_000_000)
    injured_count: int | None = Field(default=None, ge=0, le=1_000_000)
    needs: Needs
    vulnerable_groups: list[str] = Field(default_factory=list, max_length=20)
    risk_signals: list[str] = Field(default_factory=list, max_length=30)
    location_text: str | None = Field(default=None, max_length=300)
    summary: str = Field(min_length=3, max_length=500)
    confidence: float = Field(ge=0, le=1)


class StatusUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: RequestStatus


class ResourceInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    waterLiters: int = Field(default=0, ge=0, le=1_000_000_000)
    tents: int = Field(default=0, ge=0, le=10_000_000)
    medicalStaff: int = Field(default=0, ge=0, le=1_000_000)
    blankets: int = Field(default=0, ge=0, le=100_000_000)


class CustomResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=60)
    quantity: Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
    unit: str = Field(min_length=1, max_length=30)


class AllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resources: ResourceInventory
    customResources: list[CustomResourceInput] = Field(default_factory=list, max_length=100)
    cities: list[str] | None = Field(default=None, max_length=100)

    def inventory_payload(self) -> dict[str, Any]:
        payload = self.resources.model_dump()
        if self.customResources:
            payload["customResources"] = [resource.model_dump() for resource in self.customResources]
        return payload
