# MagicRows Python Enrichment Library (`magicrowspy`)

This Python library provides tools to enrich your data (Pandas or Polars DataFrames) using AI models like OpenAI, based on flexible configuration presets.

## Key Features

*   **AI-Powered Enrichment:** Leverage LLMs (initially OpenAI) to add new columns or insights to your data.
*   **Configuration Presets:** Define enrichment tasks, prompts, context columns, output schemas, and AI parameters in separate `.ts` (TypeScript) configuration files.
*   **Flexible Input:** Accepts configuration either via a path to a preset file or a pre-validated `AIEnrichmentBlockConfig` object.
*   **Pandas & Polars Support:** Works seamlessly with both popular DataFrame libraries.
*   **Reasoning Control:** Option to include (or exclude) additional columns containing the AI's reasoning behind its generated values.
*   **Multiple Output Modes:** Supports different ways to structure the output (e.g., adding new columns, creating new rows).

## Installation

Assuming you are using `uv` (as seen in project usage):

```bash
# Ensure you are in your project's root directory or virtual environment
uv pip install -e .
# Or if installing from a package source (adjust source as needed):
# uv pip install magicrowspy 
```

## Configuration

1.  **Provider Configuration:** Set up your AI provider credentials. Currently supports OpenAI:

    ```python
    import os
    from magicrowspy.config import OpenAIProviderConfig

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    openai_provider = OpenAIProviderConfig(
        integrationName="myOpenAI", # Must match 'integrationName' in your preset files
        apiKey=api_key,
        # Other provider-specific options can go here
    )
    ```

2.  **Enrichment Presets:** Define the enrichment logic in `.ts` files (likely located in a `presets/` directory relative to your script or a known path). These files contain `AIEnrichmentBlockConfig` definitions, specifying:
    *   `integrationName`: Matches the provider config (e.g., "myOpenAI").
    *   `model`, `temperature`: AI model parameters.
    *   `mode`: `RunMode.FULL` or `RunMode.PREVIEW`.
    *   `outputFormat`: How to structure output (e.g., `OutputFormat.NEW_COLUMNS`).
    *   `contextColumns`: Input columns needed for the prompt.
    *   `outputs`: A list defining each new column to generate:
        *   `name`: Name of the output column.
        *   `prompt`: Jinja2 template for the AI prompt.
        *   `outputType`: e.g., `OutputType.TEXT`, `OutputType.NUMBER`, `OutputType.CATEGORY`.
        *   `outputCardinality`: `OutputCardinality.SINGLE` or `OutputCardinality.MULTIPLE`.
        *   `includeReasoning`: `true` or `false`.
        *   `outputCategories` (if `outputType` is `CATEGORY`).

## Usage

Basic workflow involves:
1.  Setting up your provider configurations (e.g., OpenAI API key).
2.  Loading your input data (e.g., from a CSV) into a pandas DataFrame.
3.  Initializing the `Enricher` with your provider configurations.
4.  Calling the `enricher.enrich()` method, passing your DataFrame and the desired preset configuration.
5.  Processing or saving the resulting enriched DataFrame.

### Loading Preset Configurations

The `enricher.enrich(config_source=...)` method accepts the preset configuration in several ways:

*   **Bundled Preset (Recommended):** Specify the preset name as a string relative to the library's internal `presets` directory. This is the simplest way to use the standard presets provided with `magicrowspy`.
    ```python
    # Assumes 'ISCO/ISCOTasks_preset.ts' exists within magicrowspy's installed presets
    output_df = await enricher.enrich(input_df, "ISCO/ISCOTasks_preset.ts")
    ```

*   **External Preset (Absolute Path):** Provide the full, absolute path to your custom `.ts` preset file as a string.
    ```python
    output_df = await enricher.enrich(input_df, "/Users/you/my_magicrows_configs/custom_analysis.ts")
    ```

*   **External Preset (Relative Path):** Provide a path relative to the *current working directory* where you run your Python script.
    ```python
    # Assumes 'my_presets/custom_analysis.ts' exists relative to where you run python
    output_df = await enricher.enrich(input_df, "my_presets/custom_analysis.ts")
    ```

*   **External Preset (Path Object):** Use a `pathlib.Path` object for more robust path handling.
    ```python
    from pathlib import Path
    preset_path = Path("../configs/shared_preset.ts").resolve()
    output_df = await enricher.enrich(input_df, preset_path)
    ```

*   **Pre-loaded Config Object:** You can also manually load and validate a config object using `magicrowspy.config.load_preset` and pass the resulting `AIEnrichmentBlockConfig` object directly (though this is less common for typical usage).

### Example Script

See `magicrowspy/scripts_examples/simple_enrichment_script.py` for a runnable example.

## Core Usage

```python
import asyncio
import pandas as pd
from pathlib import Path
from magicrowspy import Enricher
from magicrowspy.config import OpenAIProviderConfig

# --- Configuration ---
PRESET_FILE_PATH = "../presets/your_preset.ts" # Path relative to script
CSV_INPUT_PATH = "path/to/your/input_data.csv"
API_KEY = "your_openai_api_key" # Ideally load from environment

# --- Main Async Function ---
asynchronous def main():
    # --- Load Input Data ---
    input_df = pd.read_csv(CSV_INPUT_PATH)
    print(f"Loaded {len(input_df)} rows from {CSV_INPUT_PATH}")

    # --- Configure Provider & Enricher ---
    openai_provider = OpenAIProviderConfig(
        integrationName="myOpenAI", # Ensure this matches the preset
        apiKey=API_KEY,
    )
    enricher = Enricher(providers=[openai_provider])

    # --- Run Enrichment ---
    print(f"Starting enrichment using preset: {PRESET_FILE_PATH}...")

    # Example 1: Run enrichment with reasoning (default)
    # output_df_with_reasoning = await enricher.enrich(
    #     input_df.copy(), # Pass a copy if you want to preserve the original
    #     PRESET_FILE_PATH
    # )

    # Example 2: Run enrichment WITHOUT reasoning columns
    output_df_no_reasoning = await enricher.enrich(
        input_df.copy(),
        PRESET_FILE_PATH,
        reasoning=False # Explicitly disable reasoning columns
    )

    print("Enrichment completed.")

    # --- Export Results ---
    output_filename = f"{Path(CSV_INPUT_PATH).stem}_enriched_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = Path.home() / "Desktop" / output_filename
    output_df_no_reasoning.to_csv(output_path, index=False)
    print(f"Successfully wrote enriched data to: {output_path}")

# --- Run ---
if __name__ == "__main__":
    # Check if running in a Jupyter environment
    try:
        get_ipython()
        # If in Jupyter/IPython, run the async function using nest_asyncio
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.run(main())
    except NameError:
        # If not in Jupyter, run normally
        asyncio.run(main())

## Notes

*   The `.enrich()` method is asynchronous and needs to be awaited.
*   Ensure your `integrationName` in the `OpenAIProviderConfig` matches the `integrationName` used within your `.ts` preset files.
*   The `reasoning` parameter in `.enrich()` controls whether reasoning columns are included *and* whether reasoning is requested from the AI (if `includeReasoning: true` is set in the preset for that output).
