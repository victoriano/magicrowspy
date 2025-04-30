"""Functions for loading configurations from files."""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Union
import importlib.resources

from .models import AIEnrichmentBlockConfig

logger = logging.getLogger('magicrowspy')

# Helper function to get path to a built-in preset
def _get_bundled_preset_path(preset_name: str) -> Path:
    """Gets the absolute path to a preset file bundled with the package."""
    try:
        # Use importlib.resources to find the file within the package's 'presets' dir
        # Ensures it works even if the package is installed (zipped or not)
        resource_path = importlib.resources.files('magicrowspy.presets').joinpath(preset_name)
        
        # Need context manager to get a usable file path, especially from zip installs
        with importlib.resources.as_file(resource_path) as file_path:
            logger.debug(f"Resolved bundled preset '{preset_name}' to path: {file_path}")
            return file_path # Return the Path object from the context
            
    except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError, Exception) as e:
         # Catch potential errors during resource resolution
        logger.error(f"Error locating bundled preset '{preset_name}': {e}", exc_info=True)
        raise FileNotFoundError(
            f"Could not locate the built-in preset '{preset_name}'. "
            f"Ensure 'magicrowspy' is installed correctly and the 'presets' directory is included as package data. "
            f"Original error: {type(e).__name__}: {e}"
        )

def load_preset(config_source: Union[str, Path, AIEnrichmentBlockConfig]) -> AIEnrichmentBlockConfig:
    """Loads and validates the AI enrichment configuration.

    Args:
        config_source: 
            - A string filename (e.g., "ISCOTasks_preset.ts") assumed to be a bundled preset.
            - A string absolute/relative path to a .ts file.
            - A Path object pointing to a .ts file.
            - A pre-validated AIEnrichmentBlockConfig object (passed through).

    Returns:
        A validated AIEnrichmentBlockConfig object.

    Raises:
        FileNotFoundError: If the specified file cannot be found.
        InvalidConfigurationError: If validation fails.
        TypeError: If config_source is of an unsupported type.
    """
    if isinstance(config_source, AIEnrichmentBlockConfig):
        logger.debug("Configuration source is already a validated object.")
        # TODO: Potentially re-validate here? For now, assume it's valid if passed.
        return config_source

    ts_path: Path
    if isinstance(config_source, Path):
        logger.debug(f"Configuration source is a Path object: {config_source}")
        ts_path = config_source.resolve()
    elif isinstance(config_source, str):
        logger.debug(f"Configuration source is a string: '{config_source}'")
        potential_path = Path(config_source)
        # Check if it's an absolute path OR an existing file relative to CWD
        if potential_path.is_absolute() or potential_path.is_file():
            logger.info(f"Treating string source '{config_source}' as an explicit file path.")
            ts_path = potential_path.resolve()
        else:
            # Assume it's a path relative to the bundled presets directory
            logger.info(f"Assuming '{config_source}' is a bundled preset path relative to 'magicrowspy.presets'. Locating...")
            ts_path = _get_bundled_preset_path(config_source) # Pass the relative path (e.g., "ISCO/file.ts")
    else:
        raise TypeError(
            "config_source must be a string (filename or path), Path, or AIEnrichmentBlockConfig object."
        )

    logger.info(f"Attempting to load preset configuration from: {ts_path}")
    if not ts_path.is_file():
        # Log before raising
        logger.error(f"Preset file not found at resolved path: {ts_path}")
        raise FileNotFoundError(f"TypeScript config file not found: {ts_path}")

    try:
        content = ts_path.read_text(encoding='utf-8')
    except Exception as e:
        raise IOError(f"Error reading TypeScript file {ts_path}: {e}") from e

    # Attempt to find the start of the first object literal assignment matching the pattern:
    # `export const anyVariableName ... = {`
    # This regex looks for 'export const', captures the variable name, allows for an optional type hint,
    # finds the equals sign, and expects an opening brace.
    start_pattern = re.compile(r"export\s+const\s+(\w+)(?:\s*:\s*\w+)?\s*=\s*\{", re.MULTILINE)
    match = start_pattern.search(content)

    if not match:
        raise ValueError(f"Could not find an exported config object assignment like 'export const name = {{' in {ts_path}")
    
    # Extract the inferred variable name (mainly for potential error messages)
    inferred_config_name = match.group(1)
    start_index = match.end() -1 # Index of the starting '{'

    # Find the matching closing '}' - basic brace counting
    brace_level = 1
    end_index = -1
    for i in range(start_index + 1, len(content)):
        if content[i] == '{':
            brace_level += 1
        elif content[i] == '}':
            brace_level -= 1
            if brace_level == 0:
                end_index = i
                break
    
    if end_index == -1:
        raise ValueError(f"Could not find matching closing brace '}}' for config object starting near '{inferred_config_name}' in {ts_path}")

    # Extract the object literal content
    object_literal = content[start_index : end_index + 1]

    # Basic cleaning: Attempt to remove trailing commas before '}' or ']'
    # This is a common difference between JS objects and strict JSON.
    # More sophisticated cleaning might be needed for other cases (e.g., comments).
    cleaned_literal = re.sub(r",(\s*[\]\}])", r"\1", object_literal)

    try:
        config_dict: Dict[str, Any] = json.loads(cleaned_literal)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse the extracted content from {ts_path} as JSON. "
            f"Ensure the object literal for the config export uses JSON-compatible syntax. "
            f"Error: {e}\nExtracted content snippet:\n{cleaned_literal[:500]}..."
        ) from e

    try:
        # Validate the dictionary using the Pydantic model
        return AIEnrichmentBlockConfig.model_validate(config_dict)
    except Exception as e:
        # Catch Pydantic validation errors or other issues
        raise ValueError(f"Validation failed for config loaded from {ts_path}: {e}") from e
