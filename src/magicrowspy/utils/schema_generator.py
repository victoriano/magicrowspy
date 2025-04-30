"""Generates standard JSON Schema from OutputConfig."""

from typing import Dict, Any, List

from magicrowspy.config.models import OutputConfig, OutputType, OutputCardinality, OutputCategory


def generate_json_schema(output_config: OutputConfig, reasoning: bool) -> Dict[str, Any]:
    """Translates an OutputConfig object into a JSON Schema dictionary.

    Args:
        output_config: The configuration for a single output.
        reasoning: If True, include the reasoning field in the schema.

    Returns:
        A dictionary representing the JSON Schema for the expected output.

    Raises:
        ValueError: If the configuration is invalid (e.g., category type 
                    without categories defined).
    """
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        # Make the single property required by default
        "required": [output_config.name],
        # Disallow any additional properties not defined in the schema
        "additionalProperties": False 
    }
    properties = schema["properties"]

    prop_schema: Dict[str, Any] = {}

    # Determine base type based on OutputType
    if output_config.outputType == OutputType.TEXT:
        prop_schema["type"] = "string"
        prop_schema["description"] = f"Text output for {output_config.name}"
    elif output_config.outputType == OutputType.NUMBER:
        prop_schema["type"] = "number" # Could be 'integer' if needed, 'number' is more general
        prop_schema["description"] = f"Numeric output for {output_config.name}"
        # Potential enhancements: add min/max based on prompt/config?
    elif output_config.outputType == OutputType.CATEGORY:
        if not output_config.outputCategories:
            raise ValueError(
                f"Output '{output_config.name}' is type 'category' but has no outputCategories defined."
            )
        prop_schema["type"] = "string"
        prop_schema["description"] = f"Categorical output for {output_config.name}"
        prop_schema["enum"] = [cat.name for cat in output_config.outputCategories]
        # Could add category descriptions to the main schema description if helpful
        # schema["description"] = "Available categories:\n" + "\n".join([f"- {c.name}: {c.description}" for c in output_config.outputCategories])

    elif output_config.outputType == OutputType.JSON:
        # For JSON, we expect the LLM to return a string that *is* JSON.
        # Validation that the *content* of the string is valid JSON happens later.
        # The schema here just validates that the *output field itself* is a string.
        prop_schema["type"] = "string"
        prop_schema["description"] = f"JSON string output for {output_config.name}. The content should be valid JSON."
    else:
        # Should not happen with Enum validation, but good practice
        raise ValueError(f"Unsupported outputType: {output_config.outputType}")

    # Handle Cardinality
    if output_config.outputCardinality == OutputCardinality.MULTIPLE:
        # Wrap the determined prop_schema in an array definition
        properties[output_config.name] = {
            "type": "array",
            "description": f"List of {output_config.outputType.value} values for {output_config.name}",
            "items": prop_schema
            # Potential enhancements: add minItems/maxItems based on prompt/config?
            # e.g., if prompt says "list 5 items", add "minItems": 5, "maxItems": 5
        }
    else: # SINGLE cardinality
        properties[output_config.name] = prop_schema

    # Conditionally add reasoning structure to the schema
    if output_config.includeReasoning and reasoning:
        # The 'properties' dict currently holds the schema for the output value itself
        # e.g., properties = { output_config.name: {"type": "string", "enum": [...]}}
        # We need to wrap this value schema and add a reasoning schema:
        # final_schema = {
        #   "type": "object",
        #   "properties": {
        #       output_config.name: {
        #           "type": "object",
        #           "properties": {
        #               "value": <original_value_schema>,
        #               "reasoning": <reasoning_schema>
        #           },
        #           "required": ["value", "reasoning"],
        #           "additionalProperties": False
        #       }
        #   },
        #   "required": [output_config.name]
        # }

        # Extract the original schema for the value
        original_value_schema = properties[output_config.name]

        # Create the schema for the 'reasoning' property
        reasoning_prop_schema = {
            "type": "string",
            "description": "Explanation for why the value was chosen or generated."
        }

        # Build the new wrapped schema for the output property
        wrapped_prop_schema = {
            "type": "object",
            "description": f"Output value and reasoning for {output_config.name}",
            "properties": {
                "value": original_value_schema,
                "reasoning": reasoning_prop_schema
            },
            "required": ["value", "reasoning"],
            "additionalProperties": False
        }

        # Replace the original property schema with the new wrapped one
        properties[output_config.name] = wrapped_prop_schema

    # Final schema structure remains the same, but the property schema inside might be wrapped
    return schema

def generate_combined_json_schema(outputs: List[OutputConfig]) -> Dict[str, Any]:
    """Generates a combined JSON schema for multiple OutputConfig objects."""
    combined_properties = {}
    required_fields = []

    for output_conf in outputs:
        # Generate the schema properties for the main value
        if output_conf.outputType == OutputType.TEXT:
            if output_conf.outputCardinality == OutputCardinality.SINGLE:
                combined_properties[output_conf.name] = {
                    "type": "string",
                    "description": f"Text output for {output_conf.name}"
                }
            else: # MULTIPLE
                combined_properties[output_conf.name] = {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"List of {output_conf.name}. {output_conf.prompt}"
                }
        elif output_conf.outputType == OutputType.CATEGORY:
            if not output_conf.outputCategories:
                raise ValueError(
                    f"Output '{output_conf.name}' is type 'category' but has no outputCategories defined."
                )
            if output_conf.outputCardinality == OutputCardinality.SINGLE:
                combined_properties[output_conf.name] = {
                    "type": "string",
                    "description": f"Categorical output for {output_conf.name}",
                    "enum": [cat.name for cat in output_conf.outputCategories]
                }
            else: # MULTIPLE
                combined_properties[output_conf.name] = {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": f"Selected categories for {output_conf.name}",
                        "enum": [cat.name for cat in output_conf.outputCategories]
                    },
                    "description": f"List of selected categories for {output_conf.name}. {output_conf.prompt}"
                }
        elif output_conf.outputType == OutputType.NUMBER:
            combined_properties[output_conf.name] = {
                "type": "number",
                "description": f"Numerical value for {output_conf.name}. {output_conf.prompt}"
            }
        elif output_conf.outputType == OutputType.DATE:
            combined_properties[output_conf.name] = {
                "type": "string",
                "format": "date",
                "description": f"Date value (YYYY-MM-DD) for {output_conf.name}. {output_conf.prompt}"
            }
        elif output_conf.outputType == OutputType.URL:
            combined_properties[output_conf.name] = {
                "type": "string",
                "format": "uri",
                "description": f"URL value for {output_conf.name}. {output_conf.prompt}"
            }
        else:
            raise ValueError(f"Unsupported output type: {output_conf.outputType}")

        # Determine required fields for this output
        # The main output field is always required
        required_fields.append(output_conf.name)

        # Add reasoning property and requirement if requested for this output
        if output_conf.includeReasoning:
            combined_properties[f"{output_conf.name}_reasoning"] = {
                "type": "string",
                "description": f"Reasoning for {output_conf.name}."
            }
            required_fields.append(f"{output_conf.name}_reasoning") # Make reasoning required too

    return {
        "type": "object",
        "properties": combined_properties,
        "required": required_fields,
        "additionalProperties": False
    }
