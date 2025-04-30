# Log Summary Feature Usage Examples

This document provides examples of how to use the new `log_summary` parameter in the `enricher.enrich` function to get insights into your enrichment operations.

## Basic Usage

Simply add the `log_summary=True` parameter to your existing `enrich` call:

```python
output_df = await enricher.enrich(
    input_df, 
    "path/to/preset.ts", 
    reasoning=True,
    log_summary=True  # Enable statistics summary
)
```

After the enrichment completes, a summary will be automatically printed to the console showing:
- Processing statistics (rows, successful API calls)
- Timing metrics (total time, API time, processing time)
- Token usage
- Cost estimates

## Example Output

```
========== Enrichment Summary ==========
Total Rows Processed: 10
Successful API Calls: 20
------------------------------------
Total Time Elapsed:   8.4532 s
Total API Time:       7.2134 s
Total Processing Time:1.2398 s (Total - API)
Avg. API Time/Call:   0.3607 s
Avg. Total Time/Row:  0.8453 s
------------------------------------
Input Tokens:         1250
Output Tokens:        2480
Total Tokens:         3730
------------------------------------
Estimated Input Cost: $0.006250 (@ $5.0/M)
Estimated Output Cost:$0.037200 (@ $15.0/M)
Estimated Total Cost: $0.043450
======================================
```

## Combining with log_requests

You can use both logging parameters together for detailed debugging:

```python
output_df = await enricher.enrich(
    input_df, 
    "path/to/preset.ts", 
    reasoning=True,
    log_requests=True,  # Log individual API requests/responses
    log_summary=True    # Show summary statistics at the end
)
```

## Cost Estimation

The cost estimation uses model-specific pricing from our pricing database. Supported models include:

### OpenAI Models
- gpt-4o: $5.0/M input, $15.0/M output
- gpt-4-turbo: $10.0/M input, $30.0/M output
- gpt-4: $30.0/M input, $60.0/M output
- gpt-3.5-turbo: $0.5/M input, $1.5/M output

### Anthropic Models
- claude-3-opus: $15.0/M input, $75.0/M output
- claude-3-sonnet: $3.0/M input, $15.0/M output
- claude-3-haiku: $0.25/M input, $1.25/M output

Pricing data is stored in `src/magicrowspy/utils/pricing.json` and can be updated as provider pricing changes.
