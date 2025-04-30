"""Utilities for cost estimation and pricing."""

import json
import logging
import os
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger('magicrowspy')

def load_pricing_config() -> Dict[str, Any]:
    """Load pricing configuration from JSON file.
    
    Returns:
        Dict containing pricing information for different models and providers.
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        pricing_path = os.path.join(current_dir, 'pricing.json')
        
        with open(pricing_path, 'r') as f:
            pricing = json.load(f)
        return pricing
    except Exception as e:
        logger.warning(f"Could not load pricing configuration: {e}")
        # Return default pricing if unable to load
        return {
            "defaults": {
                "input_tokens": 5.0,
                "output_tokens": 15.0
            }
        }

def get_token_prices(provider: str, model: str) -> Tuple[float, float]:
    """Get the price per million tokens for input and output.
    
    Args:
        provider: The provider name (e.g., 'openai', 'anthropic')
        model: The model name (e.g., 'gpt-4o', 'claude-3-haiku')
        
    Returns:
        Tuple of (input_price_per_million, output_price_per_million)
    """
    pricing = load_pricing_config()
    
    # Default prices
    default_input = pricing.get("defaults", {}).get("input_tokens", 5.0)
    default_output = pricing.get("defaults", {}).get("output_tokens", 15.0)
    
    # Check if provider exists
    provider_pricing = pricing.get(provider.lower(), {})
    
    # Check if model exists under the provider
    model_pricing = provider_pricing.get(model, {})
    
    input_price = model_pricing.get("input_tokens", default_input)
    output_price = model_pricing.get("output_tokens", default_output)
    
    return input_price, output_price

def calculate_cost(
    input_tokens: int, 
    output_tokens: int, 
    provider: str = "openai", 
    model: str = "gpt-4o"
) -> Dict[str, float]:
    """Calculate the cost for a given token usage.
    
    Args:
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        provider: Provider name (default: 'openai')
        model: Model name (default: 'gpt-4o')
        
    Returns:
        Dictionary with input_cost, output_cost, and total_cost in USD
    """
    input_price, output_price = get_token_prices(provider, model)
    
    # Calculate costs (price per million)
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "input_price_per_million": input_price,
        "output_price_per_million": output_price
    }
