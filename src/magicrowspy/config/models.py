"""Pydantic models for configuration."""

from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl


# --- Enums based on PRD --- 

class OutputType(str, Enum):
    """Type of data expected in the output."""
    TEXT = "text"
    CATEGORY = "category"
    NUMBER = "number"
    JSON = "json" # Retaining JSON as a potential type

class OutputCardinality(str, Enum):
    """Whether a single value or multiple values are expected."""
    SINGLE = "single"
    MULTIPLE = "multiple"

class OutputFormat(str, Enum):
    """How enriched data should be added to the dataframe."""
    NEW_COLUMNS = "newColumns"
    NEW_ROWS = "newRows"

class RunMode(str, Enum):
    """Execution mode."""
    PREVIEW = "preview"
    FULL = "full"

# --- Nested Models --- 

class OutputCategory(BaseModel):
    """Definition of a possible category for 'category' output type."""
    name: str = Field(..., description="The specific category value.")
    description: str = Field(..., description="Description of the category for the LLM.")


class OutputConfig(BaseModel):
    """Configuration for a single enrichment output (column or row set)."""
    name: str = Field(..., description="Base name for the output column(s) or row key.")
    prompt: str = Field(..., description="Jinja2 template string for the LLM prompt.")
    outputType: OutputType = Field(..., alias="outputType")
    outputCardinality: OutputCardinality = Field(..., alias="outputCardinality")
    outputCategories: Optional[List[OutputCategory]] = Field(
        default=None, 
        alias="outputCategories",
        description="List of possible categories (required if outputType is 'category')."
    )
    contextColumns: Optional[List[str]] = Field(
        default=None, 
        alias="contextColumns",
        description="Specific context columns for this output, overriding block-level."
    )
    includeReasoning: bool = Field(
        default=True,
        description="If True, requests the AI to provide reasoning for its answer for this output."
    )
    # Note: strict_validation is not part of the config model itself,
    # but a processing parameter potentially.

    class Config:
        populate_by_name = True # Allows using both camelCase and snake_case
        extra = 'forbid' # Forbid unexpected fields during parsing

# --- Provider Config Models --- 

class BaseProviderConfig(BaseModel):
    """Base configuration for any AI provider."""
    integrationName: str = Field(..., alias="integrationName", description="Unique identifier for this provider configuration instance.")

class OpenAIProviderConfig(BaseProviderConfig):
    """Configuration specific to OpenAI providers."""
    apiKey: str = Field(..., alias="apiKey", description="OpenAI API key.")
    # Add other OpenAI specific settings like baseURL, organization, etc. if needed
    # Example:
    # baseURL: Optional[HttpUrl] = Field(default=None, alias="baseURL")
    # organization: Optional[str] = Field(default=None)

    class Config:
        populate_by_name = True
        extra = 'forbid'

# --- Main Enrichment Block Config --- 

class AIEnrichmentBlockConfig(BaseModel):
    """Main configuration block for an enrichment job."""
    integrationName: str = Field(..., alias="integrationName", description="ID of the provider instance to use (must match a configured provider).")
    model: str = Field(..., description="Model ID string (e.g., 'gpt-4o-mini').")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="Sampling temperature (0-1).")
    mode: RunMode = Field(default=RunMode.PREVIEW, description="'preview' or 'full' run.")
    previewRowCount: Optional[int] = Field(
        default=5, 
        alias="previewRowCount", 
        ge=1,
        description="Number of rows to process in 'preview' mode."
    )
    outputFormat: OutputFormat = Field(..., alias="outputFormat", description="'newColumns' or 'newRows'.")
    contextColumns: List[str] = Field(..., alias="contextColumns", description="Default list of input column names for prompt context.")
    outputs: List[OutputConfig] = Field(..., description="List of individual enrichment tasks.")
    budget: Optional[float] = Field(default=None, ge=0.0, description="Optional maximum spend in USD.")

    class Config:
        populate_by_name = True # Allow camelCase field names from TS/JSON
        extra = 'forbid' 
