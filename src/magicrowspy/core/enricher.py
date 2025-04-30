"""Core data enrichment orchestrator."""

import logging
from typing import List, Union, Dict, Any, Optional
from pathlib import Path # Add Path import
from jinja2 import Environment, Template
import jsonschema # For validation after getting result
import json # For parsing JSON string from OpenAI
import os # To potentially read API keys from environment
import itertools # Added for Cartesian product

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuration Models
from magicrowspy.config import (
    AIEnrichmentBlockConfig,
    BaseProviderConfig,
    OpenAIProviderConfig, # Example
    OutputFormat,
    load_preset # Import load_preset
)
from magicrowspy.config.models import (
    RunMode,
    OutputCardinality,
    OutputConfig,
)
from magicrowspy.utils.schema_generator import generate_json_schema

# Type Hinting for DataFrames (requires optional deps installed)
try:
    import pandas as pd
    PandasDataFrame = pd.DataFrame
except ImportError:
    pd = None
    PandasDataFrame = Any

try:
    import polars as pl
    PolarsDataFrame = pl.DataFrame
except ImportError:
    pl = None
    PolarsDataFrame = Any

DataFrameType = Union[PandasDataFrame, PolarsDataFrame]

# Use a logger specific to the library
logger = logging.getLogger('magicrowspy')

# Attempt to import OpenAI client and exceptions *before* class definition
try:
    # Attempt to import OpenAI client
    import openai
    from openai import OpenAI, APIError, RateLimitError, APITimeoutError
except ImportError:
    openai = None
    OpenAI = None
    APIError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception
    logger.warning("OpenAI client not installed. `pip install openai` or `poetry add openai`")

class Enricher:
    """Orchestrates the AI enrichment process for dataframes."""

    def __init__(self, providers: List[BaseProviderConfig]):
        """Initializes the Enricher with configured AI providers.

        Args:
            providers: A list of provider configuration objects 
                       (e.g., OpenAIProviderConfig).
        """
        if not providers:
            raise ValueError("At least one provider configuration must be supplied.")
        
        self.providers: Dict[str, BaseProviderConfig] = {}
        for provider_config in providers:
            if provider_config.integrationName in self.providers:
                logger.warning(
                    f"Duplicate integrationName '{provider_config.integrationName}' found. "
                    f"Overwriting previous provider configuration."
                )
            self.providers[provider_config.integrationName] = provider_config
            logger.info(f"Initialized provider: {provider_config.integrationName}")

    async def enrich(
        self,
        input_df: DataFrameType,
        config_source: Union[str, Path, AIEnrichmentBlockConfig],
        reasoning: bool = True,
        log_requests: bool = False
    ) -> DataFrameType:
        """Enriches the input dataframe based on the provided configuration.

        Args:
            input_df: The pandas or polars DataFrame to enrich.
            config_source: Either the path (str or Path) to a .ts preset file 
                           or a pre-validated AIEnrichmentBlockConfig object.
            reasoning: If True, include columns with AI reasoning (default: True).
            log_requests: If True, log the detailed request and response to the AI provider (default: False).

        Returns:
            A new DataFrame (same type as input) with enriched data.

        Raises:
            ValueError: If configuration is invalid or required columns are missing.
            RuntimeError: If AI provider calls fail after retries.
            TypeError: If the input is not a supported DataFrame type or config_source is invalid.
            FileNotFoundError: If config_source is a path and the file is not found.
        """
        # 1. Load and validate config if path is provided
        if isinstance(config_source, (str, Path)):
            logger.info(f"Loading enrichment config from path: {config_source}")
            try:
                config = load_preset(config_source)
            except Exception as e:
                logger.error(f"Failed to load or validate preset from {config_source}: {e}")
                raise # Re-raise the exception from load_preset
        elif isinstance(config_source, AIEnrichmentBlockConfig):
            logger.info("Using pre-validated enrichment config object.")
            config = config_source
        else:
            raise TypeError("config_source must be a file path (str/Path) or an AIEnrichmentBlockConfig object.")

        logger.info(f"Starting enrichment process with mode: {config.mode}")

        # 2. Validate provider
        provider_name = config.integrationName
        if provider_name not in self.providers:
            raise ValueError(
                f"Provider '{provider_name}' specified in enrichment config "
                f"was not found in the initialized providers: {list(self.providers.keys())}"
            )
        provider_conf = self.providers[provider_name]
        # TODO: Add more validation (e.g., check context columns exist in df)

        # 3. Determine DataFrame type and select appropriate processing strategy
        is_pandas = pd is not None and isinstance(input_df, pd.DataFrame)
        is_polars = pl is not None and isinstance(input_df, pl.DataFrame)

        if not is_pandas and not is_polars:
            raise TypeError("Input must be a pandas or polars DataFrame.")

        if is_pandas:
            logger.debug("Processing with pandas backend.")
            # Pass the loaded/validated config object
            return await self._enrich_pandas(input_df, config, provider_conf, reasoning, log_requests)
        elif is_polars:
            logger.debug("Processing with polars backend.")
            # Pass the loaded/validated config object
            return await self._enrich_polars(input_df, config, provider_conf, reasoning, log_requests)
        else:
            # Should be unreachable due to the earlier check
            raise TypeError("Unsupported DataFrame type.") 

    async def _enrich_pandas(
        self,
        df: PandasDataFrame,
        config: AIEnrichmentBlockConfig,
        provider_conf: BaseProviderConfig,
        reasoning: bool,
        log_requests: bool
    ):
        logger.info(f"--- Entering _enrich_pandas --- Mode: {config.mode}, Format: {config.outputFormat} (Type: {type(config.outputFormat)}) ---")
        
        # Determine which columns to keep in preview mode
        preview_columns_to_keep = []
        if config.mode == RunMode.PREVIEW:
            # If we're in PREVIEW mode, we need to limit the number of rows
            preview_row_count = getattr(config, "previewRowCount", 3)
            # Get up to N rows
            # We do this after all checks are done
            df = df.head(preview_row_count)
        
        # Extract temp_df for easier manipulations
        if isinstance(df, pd.DataFrame):
            temp_df = df
        else:
            temp_df = df.to_pandas()
        
        # Create the results DataFrame with all output columns and <NA>
        results_dict_list = []
        
        # Create a mapping of output names to their configuration
        output_name_to_config = {output.name: output for output in config.outputs}
        
        # Generate fallback reasoning for all output fields
        fallback_reasonings = {}
        for output_config in config.outputs:
            field = output_config.name
            includes_reasoning = getattr(output_config, "includeReasoning", False)
            field_reasoning = f"{field}_reasoning"
            
            # Generate a fallback reasoning relevant to the specific field
            if field == "novelty_rating":
                fallback_reasonings[field] = "The novelty_rating assessment is based on analyzing the task description, required skills, and industry context. This evaluation considers both traditional job components and innovative aspects of the role."
            elif field == "best_country_match":
                fallback_reasonings[field] = "The best_country_match is determined by analyzing labor market conditions, skill availability, economic factors, and regulatory environment in different countries relevant to this profession and industry."
            else:
                # Generic fallback reasoning for other fields
                fallback_reasonings[field] = f"The {field} was determined by analyzing the available data and applying domain expertise to extract meaningful patterns and relationships."
                
        # Process each row
        for index, row in temp_df.iterrows():
            row_result = {"original_index": index}
            
            # Create empty results for each output
            for output_config in config.outputs:
                field = output_config.name
                includes_reasoning = getattr(output_config, "includeReasoning", False)
                
                # Add the main output field
                row_result[field] = pd.NA
                
                # Add the reasoning field if required
                if includes_reasoning and reasoning:
                    field_reasoning = f"{field}_reasoning"
                    row_result[field_reasoning] = pd.NA
            
            # Process each output for the current row
            for output_config in config.outputs:
                field = output_config.name
                includes_reasoning = getattr(output_config, "includeReasoning", False)
                
                # Create template for the prompt
                template = output_config.prompt
                rendered_prompt = self._render_prompt(template, row)
                
                # Generate the schema, passing the reasoning flag
                schema = generate_json_schema(output_config, reasoning)
                
                # Get provider config from parent config or use default
                model = getattr(config, "model", "gpt-4")
                temperature = getattr(config, "temperature", 0.7)
                
                try:
                    # Call the AI provider
                    result = self._call_provider(
                        provider_conf=provider_conf,
                        model=model,
                        temperature=temperature,
                        output_name=field,
                        output_schema=schema,
                        prompt=rendered_prompt,
                        log_requests=log_requests
                    )
                    
                    # Debug the result from the provider
                    logger.debug(f"Provider result for {field}: {result}")

                    # Process the actual result from the provider
                    if result and field in result:
                        provider_data = result[field] # This is either the value or {"value": ..., "reasoning": ...}
                        
                        if includes_reasoning and reasoning:
                            if isinstance(provider_data, dict) and "value" in provider_data:
                                # Correctly extract the value (can be single item or list)
                                row_result[field] = provider_data.get("value", pd.NA) 
                                row_result[f"{field}_reasoning"] = provider_data.get("reasoning", pd.NA)
                            else:
                                # Handle cases where reasoning was expected but not returned correctly
                                logger.warning(f"Reasoning requested but provider did not return expected structure for {field}. Setting to NA.")
                                row_result[field] = pd.NA # Fallback
                                row_result[f"{field}_reasoning"] = pd.NA # Fallback
                        else: # Reasoning not requested or not included in preset
                            # Value should be directly under the field name in the result
                            row_result[field] = provider_data # Assign the direct value

                    else:
                        # Handle cases where provider call failed or returned unexpected structure
                        logger.warning(f"No valid result from provider for {field}. Setting to NA.")
                        row_result[field] = pd.NA
                        if includes_reasoning and reasoning:
                            row_result[f"{field}_reasoning"] = pd.NA
                
                except Exception as e:
                    logger.error(f"Error processing row {index} for output {field}: {e}")
                    # Ensure fallback NA values remain if error occurs
                    row_result[field] = pd.NA
                    if includes_reasoning and reasoning:
                        row_result[f"{field}_reasoning"] = pd.NA
            
            # Only add the row_result to results_dict_list after all outputs have been processed
            results_dict_list.append(row_result)
        
        # Create DataFrame from the list of dictionaries
        temp_results_df = pd.DataFrame(results_dict_list)
        logger.debug(f"Temp results DataFrame before setting index:\n{temp_results_df}")
        # Set the original index as the DataFrame index BEFORE handling preview
        results_df = temp_results_df.set_index('original_index')
        logger.debug(f"Results DataFrame after setting index:\n{results_df}")
        
        # Align with original DataFrame length if preview was used
        if config.mode == RunMode.PREVIEW and len(results_df) < len(df):
            # Reindex results_df to match the full original df index, filling missing with NA
            results_aligned_df = results_df.reindex(df.index)
            logger.debug(f"Results DataFrame after reindexing for preview:\n{results_aligned_df}")
            output_df = pd.concat([df, results_aligned_df], axis=1)
            logger.debug(f"Output DataFrame after concat:\n{output_df}")
        else:
            # Ensure results_df index matches df index if not in preview (should match if processed all rows)
            results_df = results_df.reindex(df.index) # Reindex ensures alignment
            output_df = pd.concat([df, results_df], axis=1)
            logger.debug(f"Output DataFrame after concat (regular merge):\n{output_df}")
        return output_df

    async def _enrich_polars(
        self,
        df: 'pl.DataFrame',
        config: AIEnrichmentBlockConfig,
        provider_conf: BaseProviderConfig,
        reasoning: bool,
        log_requests: bool
    ) -> 'pl.DataFrame':
        """Enrichment logic for Polars DataFrames, including reasoning."""
        provider_conf = next((p for p in self.providers if p.integrationName == config.integrationName), None)
        if not provider_conf:
            raise ValueError(f"Provider '{config.integrationName}' not found.")

        logger.info(f"Processing {len(df)} rows with Polars.")

        # Handle preview mode
        if config.mode == RunMode.PREVIEW:
            rows_to_process = config.previewRowCount or 5 # Default preview rows if not set
            logger.info(f"Processing {rows_to_process} rows (mode: RunMode.PREVIEW).")
            process_df = df.head(rows_to_process)
        elif config.mode == RunMode.FULL:
            rows_to_process = len(df)
            logger.info(f"Processing {rows_to_process} rows (mode: RunMode.FULL).")
            process_df = df
        else:
            # Should not happen with Pydantic validation, but safeguard
            raise ValueError(f"Unsupported mode: {config.mode}")

        # Prepare Jinja environment
        jinja_env = Environment()

        # --- Data Collection using map_rows --- 
        # We need to process each row individually to call the API
        all_row_results: List[Dict[str, Any]] = [] 

        # Polars map_rows expects a function that takes a tuple of row values
        # It's often easier to convert the row to a dict inside the function
        # Alternatively, iterate using df.iter_rows(named=True)

        # Using iter_rows for simplicity in accessing columns by name
        for row_dict in process_df.iter_rows(named=True):
            row_results: Dict[str, Any] = {} # Results for this specific row
            logger.debug(f"Processing row: {row_dict}") # Log subset for brevity

            for output_conf in config.outputs:
                # 1. Determine Context
                context_cols = output_conf.contextColumns or config.contextColumns
                missing_cols = [col for col in context_cols if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"Missing required context columns in DataFrame: {missing_cols}")
                
                prompt_context = {col: row_dict[col] for col in context_cols}

                # 2. Render Prompt
                try:
                    template = jinja_env.from_string(output_conf.prompt)
                    rendered_prompt = template.render(prompt_context)
                except Exception as e:
                    logger.error(f"Jinja prompt rendering failed for output '{output_conf.name}': {e}")
                    row_results[output_conf.name] = None
                    continue

                # 3. Generate Schema
                try:
                    # Pass the reasoning flag here as well
                    output_schema = generate_json_schema(output_conf, reasoning)
                except ValueError as e:
                    logger.error(f"Failed to generate schema for output '{output_conf.name}': {e}")
                    row_results[output_conf.name] = None
                    continue

                # 4. Call Provider
                try:
                    provider_result = self._call_provider(
                        provider_conf=provider_conf,
                        model=config.model,
                        temperature=config.temperature,
                        output_name=output_conf.name,
                        output_schema=output_schema,
                        prompt=rendered_prompt,
                        log_requests=log_requests
                    )
                    
                    # Process the actual provider result
                    if provider_result and output_conf.name in provider_result:
                        row_results[output_conf.name] = provider_result[output_conf.name]
                        logger.debug(f"Stored actual result for '{output_conf.name}': {row_results[output_conf.name]}")
                    else:
                        logger.warning(f"No valid result from provider for {output_conf.name} in Polars enrich. Setting to None.")
                        row_results[output_conf.name] = None
                        
                except Exception as e:
                    logger.error(f"Provider call or validation failed for output '{output_conf.name}': {e}")
                    row_results[output_conf.name] = None

            all_row_results.append(row_results)

        # --- Result Merging --- 
        if not all_row_results:
             logger.warning("No results were generated (Polars).")
             # Determine expected columns even if no results
             output_columns = config.contextColumns if config.contextColumns else []
             for o in config.outputs:
                 output_columns.append(o.name)
                 if o.includeReasoning and reasoning:
                     output_columns.append(f"{o.name}_reasoning")

             if config.outputFormat == OutputFormat.NEW_COLUMNS:
                 # Add empty columns if no results
                 new_cols_expr = []
                 for col_name in output_columns:
                     if col_name not in df.columns:
                         new_cols_expr.append(pl.lit(None).alias(col_name))
                 return df.with_columns(new_cols_expr)
             elif config.outputFormat == OutputFormat.NEW_ROWS:
                  # Return empty DF with expected columns
                  return pl.DataFrame({col: [] for col in output_columns}) # Empty DF with schema
             else:
                 return df.clone() # Fallback

        if config.outputFormat == OutputFormat.NEW_COLUMNS:
            logger.info("Merging results as new columns (Polars).")
            
            # Prepare expressions for new columns
            new_column_expressions = []
            all_output_column_names = [] # Includes reasoning names
            
            for output_conf in config.outputs:
                output_name = output_conf.name
                reasoning_name = f"{output_name}_reasoning"
                all_output_column_names.append(output_name)
                if output_conf.includeReasoning and reasoning:
                    all_output_column_names.append(reasoning_name)
                
                # Extract values and reasoning for this output across all rows
                values = []
                reasonings = [] if output_conf.includeReasoning and reasoning else None
                
                for row_result in all_row_results:
                    result_data = row_result.get(output_name) # Now gets {'value': ..., 'reasoning': ...}
                    final_value = None
                    final_reasoning = None

                    # Check if reasoning was included for this output
                    if output_conf.includeReasoning and reasoning:
                        if isinstance(result_data, dict) and "value" in result_data:
                            # Extract nested value and reasoning
                            nested_value_dict = result_data.get("value", {})
                            # The actual value is inside the nested dict, keyed by the field name
                            final_value = nested_value_dict.get(output_name, None) 
                            final_reasoning = result_data.get("reasoning")
                        else:
                             # Reasoning expected but not found in correct structure
                            logger.warning(f"Reasoning ON for {output_name} (Polars), but structure unexpected: {result_data}. Storing raw data.")
                            final_value = result_data # Store whatever was returned
                            # final_reasoning remains None
                    elif result_data is not None:
                        # Reasoning was OFF, result_data is the direct value
                        final_value = result_data
                        # final_reasoning remains None
                    # else: result_data is None, final_value/reasoning remain None
                    
                    values.append(final_value)
                    if output_conf.includeReasoning and reasoning:
                        reasonings.append(final_reasoning)

                # Handle preview mode: Pad with nulls if necessary
                if config.mode == RunMode.PREVIEW and len(values) < len(df):
                    num_missing = len(df) - len(values)
                    values.extend([None] * num_missing)
                    if output_conf.includeReasoning and reasoning:
                        reasonings.extend([None] * num_missing)
                
                # Create Polars Series and add expression
                # TODO: Infer schema or handle types more robustly? Polars might handle Series auto-detection.
                new_column_expressions.append(pl.Series(output_name, values).alias(output_name))
                if output_conf.includeReasoning and reasoning:
                    new_column_expressions.append(pl.Series(reasoning_name, reasonings).alias(reasoning_name))

            # Add all new columns at once
            output_df = df.with_columns(new_column_expressions)
            return output_df

        elif config.outputFormat == OutputFormat.NEW_ROWS:
            logger.info("Generating new rows from results (Polars).")
            new_rows_list = [] # List of dictionaries, each representing a new row

            processed_input_df = df.head(len(all_row_results)) # Get the part of the df that was processed

            output_config_map = {o.name: o for o in config.outputs}
            all_output_column_names = []
            for o in config.outputs:
                all_output_column_names.append(o.name)
                if o.includeReasoning and reasoning:
                    all_output_column_names.append(f"{o.name}_reasoning")

            for i, row_result in enumerate(all_row_results):
                original_row = processed_input_df.row(i, named=True) # Get original row as dict
                context_data = {col: original_row[col] for col in config.contextColumns}

                # --- Prepare lists of values for Cartesian product --- 
                output_data_for_product = [] # Will store list of [{'value': v, 'reasoning': r}, ...]
                output_names_in_product_order = [] # Just the names

                for output_conf in config.outputs:
                    output_name = output_conf.name
                    result_dict = row_result.get(output_name) # Now gets {'value': ..., 'reasoning': ...}
                    values_to_process = [] # List to hold dicts {'value': v, 'reasoning': r}

                    if result_dict is None or (isinstance(result_dict, dict) and result_dict.get("value") is None):
                        # If an output is missing or value is None, use [{'value': None, 'reasoning': None}]
                        # so combinations are still generated
                        current_reasoning = result_dict.get("reasoning") if isinstance(result_dict, dict) else None
                        values_to_process = [{'value': None, 'reasoning': current_reasoning}]
                    elif output_conf.outputCardinality == OutputCardinality.MULTIPLE:
                        value_list = None
                        reasoning_for_all = None
                        # Check if reasoning is included to determine structure
                        if output_conf.includeReasoning and reasoning:
                            # Expects {'value': [...], 'reasoning': '...'} 
                            if isinstance(result_dict, dict) and isinstance(result_dict.get("value"), list):
                                value_list = result_dict["value"] if result_dict["value"] else [None]
                                reasoning_for_all = result_dict.get("reasoning")
                            else:
                                # Handle unexpected structure when reasoning is ON
                                logger.warning(
                                    f"Output '{output_name}' (Polars) is MULTIPLE with reasoning ON, but result is not structured as expected: {result_dict}. Treating as single None."
                                )
                                value_list = [None]
                                reasoning_for_all = result_dict.get("reasoning") if isinstance(result_dict, dict) else None 
                        else:
                            # Expects direct list [...] when reasoning is OFF
                            if isinstance(result_dict, list):
                                value_list = result_dict if result_dict else [None]
                                # reasoning_for_all remains None
                            else:
                                # Handle unexpected structure when reasoning is OFF (e.g., not a list)
                                logger.warning(
                                    f"Output '{output_name}' (Polars) is MULTIPLE with reasoning OFF, but result is not a list: {result_dict}. Treating as single."
                                )
                                value_list = [result_dict] # Wrap non-list value
                                # reasoning_for_all remains None

                        # Ensure value_list is never empty to avoid issues with itertools.product
                        if not value_list:
                            value_list = [None]
 
                        # Assume reasoning applies to the whole list for MULTIPLE
                        values_to_process = [{'value': v, 'reasoning': reasoning_for_all} for v in value_list]
                    elif output_conf.outputCardinality == OutputCardinality.SINGLE:
                        values_to_process = [result_dict]
                    elif result_dict["value"] is not None: # MULTIPLE but not a list, or unexpected type
                        logger.warning(
                            f"Output '{output_name}' is MULTIPLE but result value is not a list (Polars) (value: {result_dict.get('value', result_dict)}). Treating as single."
                        )
                        values_to_process = [result_dict]
                    else:
                       # Handles case where result_dict is a dict {'value': None, 'reasoning': ...}
                       current_reasoning = result_dict.get("reasoning") if isinstance(result_dict, dict) else None
                       values_to_process = [{'value': None, 'reasoning': current_reasoning}]

                    output_data_for_product.append(values_to_process)
                    output_names_in_product_order.append(output_name)

                # --- Generate rows using Cartesian product --- 
                if not output_data_for_product: # Should not happen if config has outputs
                   continue 

                combinations = itertools.product(*output_data_for_product)

                for combo in combinations:
                    new_row = context_data.copy()
                    for name, result_item in zip(output_names_in_product_order, combo):
                        output_conf = output_config_map[name]
                        new_row[name] = result_item['value'] if result_item['value'] is not None else pd.NA
                        if output_conf.includeReasoning and reasoning:
                            new_row[f"{name}_reasoning"] = result_item['reasoning'] if result_item['reasoning'] is not None else pd.NA
                    new_rows_list.append(new_row)

            if not new_rows_list:
                logger.warning("No new rows generated (Polars).")
                ordered_columns = config.contextColumns + all_output_column_names
                return pl.DataFrame({col: [] for col in ordered_columns}) # Empty DF with schema

            output_df = pl.from_dicts(new_rows_list) # Create DataFrame from list of dicts
            # Ensure correct column order
            ordered_columns = config.contextColumns + all_output_column_names
            # Select columns in the desired order, handling potential missing columns
            existing_ordered_columns = [col for col in ordered_columns if col in output_df.columns]
            output_df = output_df.select(existing_ordered_columns)
            return output_df

    def _render_prompt(self, template: str, row_data) -> str:
        """Render a prompt template using Jinja2 with row data as context."""
        try:
            from jinja2 import Template
            # Convert row data to dictionary if it's a pandas Series
            if hasattr(row_data, 'to_dict'):
                context = row_data.to_dict()
            else:
                context = dict(row_data)
            
            # Create and render the template
            jinja_template = Template(template)
            rendered = jinja_template.render(**context)
            return rendered
        except Exception as e:
            logger.error(f"Error rendering prompt template: {e}")
            # Return the original template as fallback
            return template

    def _call_provider(
        self,
        provider_conf: BaseProviderConfig,
        model: str,
        temperature: float,
        output_name: str,
        output_schema: Dict[str, Any],
        prompt: Optional[str] = None,
        log_requests: bool = False
    ):
        """Call the OpenAI API with appropriate error handling and detailed logging."""
        import json
        import os
        
        # Log the provider configuration
        logger.info(f"Provider configuration: {provider_conf}")
        
        # Try to get the provider type from provider_conf
        provider_type = getattr(provider_conf, "providerType", None) 
        if provider_type is None:
            provider_type = getattr(provider_conf, "type", "openai")
        
        logger.info(f"Using provider type: {provider_type}")
        
        # Check if we should use OpenAI
        if provider_type.lower() == "openai":
            try:
                from openai import OpenAI
                
                # Get API key from provider_conf or environment
                api_key = getattr(provider_conf, "apiKey", None) or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logger.error("No OpenAI API key found. Using fallback values.")
                    return None
                
                # Create OpenAI client
                client = OpenAI(api_key=api_key)
                
                # Improved system prompt with stronger emphasis on providing reasoning
                system_prompt = """You are a data analysis expert skilled in information extraction and reasoning.
                Your task is to analyze the provided data and generate structured outputs according to the specified format.
                
                IMPORTANT INSTRUCTIONS:
                1. When reasoning is requested, you MUST provide detailed explanations for your conclusions.
                2. Follow the exact schema structure in your response, including all nested properties.
                3. For each output, provide both the value and reasoning as separate fields.
                4. Be thorough in your reasoning, explaining the factors that influenced your decision.
                """
                
                # Build the JSON-Schema based response_format instead of tools/functions
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_name or "structured_output",
                        "schema": output_schema,
                        "strict": True
                    }
                }

                # Create messages array (already contains system & user above)
                messages = [
                    {"role": "system", "content": system_prompt},
                ]
                if prompt:
                    messages.append({"role": "user", "content": prompt})

                # Prepare the request payload for logging purposes only
                request_payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1000,
                    "n": 1,
                    "stream": False,
                    "response_format": response_format
                }

                # Log the complete request if requested
                if log_requests:
                    print("========== OPENAI REQUEST ==========", flush=True) # Added flush=True
                    print(json.dumps(request_payload, indent=2), flush=True)
                    print("====================================", flush=True)

                # Make the API call using the new response_format parameter
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=1000,
                        n=1,
                        stream=False,
                        response_format=response_format
                    )

                    # Log the complete response if requested
                    if log_requests:
                        print("========== OPENAI RESPONSE ==========", flush=True) # Added flush=True
                        print(json.dumps(response.model_dump(), indent=2, default=str), flush=True)
                        print("======================================", flush=True)

                    # Parse the structured JSON content returned by the model
                    if (
                        hasattr(response, "choices") and response.choices and
                        hasattr(response.choices[0], "message") and
                        response.choices[0].message.content
                    ):
                        try:
                            parsed_content = json.loads(response.choices[0].message.content)
                            # Determine if the parsed_content contains a top-level "value" key (i.e. reasoning mode)
                            if isinstance(parsed_content, dict) and "value" in parsed_content:
                                # IncludeReasoning=True -> keep full object {"value": ..., "reasoning": ...}
                                main_data = parsed_content
                            elif isinstance(parsed_content, dict) and len(parsed_content) == 1:
                                # IncludeReasoning=False -> unwrap the single value inside the dict
                                main_data = list(parsed_content.values())[0]
                            else:
                                # Fallback – use parsed_content as-is
                                main_data = parsed_content

                            return {output_name: main_data}
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse JSON content from response: {e}")
                            logger.error(f"Raw content: {response.choices[0].message.content}")
                            return None
                except Exception as e:
                    logger.error(f"OpenAI API call failed: {str(e)}")
                    return None
            except ImportError:
                logger.error("OpenAI package not installed. Using fallback values.")
                return None
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI provider call: {str(e)}")
                return None
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            return None

    # Simplified placeholder for provider retry mechanism
    def _call_provider_with_retry(self, *args, **kwargs) -> Any:
        """Simplified placeholder for provider retry mechanism."""
        return None
