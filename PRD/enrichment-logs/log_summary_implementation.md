# Enrichment Log Summary Feature

This document tracks the implementation of the `log_summary` parameter for the `enricher.enrich` function to provide statistics about API calls, processing time, and cost estimation.

## Overview

The feature will add an optional `log_summary=False` parameter to the existing `enricher.enrich` function that, when enabled, will output a detailed summary of:
- Total rows processed
- Successful API calls
- Processing time metrics (total, API, and processing)
- Token counts
- Cost estimates based on token usage

## Implementation Tasks

- [x] Create pricing configuration in `utils/pricing.json`
- [x] Create a `CallStats` dataclass for tracking metrics
- [x] Modify the `enrich()` method to accept `log_summary` parameter
- [x] Update `_enrich_pandas` and `_enrich_polars` methods to accept and use the parameter
- [x] Refactor `_call_provider` to track timing and token usage
- [x] Create the summary printing utility function
- [x] Update documentation with examples
- [x] Add tests for the new feature

## Implementation Details

### 1. Pricing Configuration

A `pricing.json` file has been created in the `utils` directory with default pricing for various models. This file allows:
- Setting default per-million token prices
- Specifying model-specific pricing
- Supporting multiple providers (OpenAI, Anthropic, etc.)

### 2. CallStats Data Structure

```python
@dataclass
class CallStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_time: float = 0.0      # seconds
    success: bool = True
```

### 3. Enrich Method Modification

The public API change will be minimal, only adding an optional boolean parameter with a default value of `False`:

```python
async def enrich(
    self,
    input_df: DataFrameType,
    config_source: Union[str, Path, AIEnrichmentBlockConfig],
    reasoning: bool = True,
    log_requests: bool = False,
    log_summary: bool = False
) -> DataFrameType:
```

### 4. Summary Format

```
========== Enrichment Summary ==========
Total Rows Processed: {rows}
Successful API Calls: {successful_calls}
------------------------------------
Total Time Elapsed:   {elapsed:.4f} s
Total API Time:       {api_time:.4f} s
Total Processing Time:{proc_time:.4f} s (Total - API)
Avg. API Time/Call:   {avg_call_time:.4f} s
Avg. Total Time/Row:  {avg_row_time:.4f} s
------------------------------------
Input Tokens:         {input_tokens}
Output Tokens:        {output_tokens}
Total Tokens:         {total_tokens}
------------------------------------
Estimated Input Cost: ${input_cost:.6f} (@ ${price_in}/M)
Estimated Output Cost:${output_cost:.6f} (@ ${price_out}/M)
Estimated Total Cost: ${total_cost:.6f}
======================================
```

## Notes

- The feature will be non-invasive and maintain compatibility with existing code
- The price estimates are based on the pricing configuration, which can be updated as provider prices change
- The implementation leverages existing timing and token usage information available in provider responses
