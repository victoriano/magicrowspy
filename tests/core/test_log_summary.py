"""Tests for the log_summary feature in Enricher."""

import sys
import unittest
import asyncio
import io
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
import pytest

from magicrowspy.core.enricher import Enricher
from magicrowspy.core.enrichment_stats import CallStats
from magicrowspy.config import AIEnrichmentBlockConfig, OpenAIProviderConfig

class TestLogSummary(unittest.TestCase):
    """Test suite for the log_summary feature in Enricher."""
    
    def setUp(self):
        """Set up common test fixtures."""
        # Create a provider config
        self.provider = OpenAIProviderConfig(
            integrationName="openai",
            apiKey="fake-api-key"
        )
        
        # Create an enricher instance
        self.enricher = Enricher(providers=[self.provider])
        
        # Create a sample DataFrame
        self.df = pd.DataFrame({
            'task_description': ['Task 1', 'Task 2'],
            'industry': ['Technology', 'Healthcare']
        })
        
        # Mock config
        self.mock_config = MagicMock(spec=AIEnrichmentBlockConfig)
        self.mock_config.integrationName = "openai"
        self.mock_config.model = "gpt-4o"
        self.mock_config.contextColumns = ['task_description', 'industry']
        self.mock_config.outputs = []
        
        # Prepare mock call stats
        self.call_stats = CallStats(
            prompt_tokens=100,
            completion_tokens=150,
            api_time=0.5,
            success=True,
            model="gpt-4o",
            provider="openai"
        )
        
        # Mock provider result
        self.provider_result = {"test_output": {"value": "test", "reasoning": "test reasoning"}}
    
    @pytest.mark.asyncio
    async def test_log_summary_output(self):
        """Test that log_summary=True produces output to stdout."""
        # Patch stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Patch _call_provider to return predetermined values
        with patch.object(
            self.enricher, 
            '_call_provider', 
            new_callable=AsyncMock,
            return_value=(self.provider_result, self.call_stats)
        ):
            # Mock load_preset to return our mock config
            with patch('magicrowspy.config.load_preset', return_value=self.mock_config):
                # Call enrich with log_summary=True
                await self.enricher.enrich(
                    self.df,
                    "fake_config.ts",
                    reasoning=True,
                    log_summary=True
                )
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Check that output contains expected text
        output = captured_output.getvalue()
        self.assertIn("========== Enrichment Summary ==========", output)
        self.assertIn("Total Rows Processed: 2", output)
        self.assertIn("Input Tokens:", output)
        self.assertIn("Estimated Total Cost:", output)
    
    @pytest.mark.asyncio
    async def test_no_log_summary_output(self):
        """Test that log_summary=False doesn't produce output to stdout."""
        # Patch stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Patch _call_provider to return predetermined values
        with patch.object(
            self.enricher, 
            '_call_provider', 
            new_callable=AsyncMock,
            return_value=(self.provider_result, self.call_stats)
        ):
            # Mock load_preset to return our mock config
            with patch('magicrowspy.config.load_preset', return_value=self.mock_config):
                # Call enrich with log_summary=False
                await self.enricher.enrich(
                    self.df,
                    "fake_config.ts",
                    reasoning=True,
                    log_summary=False
                )
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Check that output doesn't contain summary text
        output = captured_output.getvalue()
        self.assertNotIn("========== Enrichment Summary ==========", output)
    
    @pytest.mark.asyncio
    async def test_statistics_accuracy(self):
        """Test that statistics are accurately accumulated."""
        # Create multiple call stats with known values
        call_stats1 = CallStats(
            prompt_tokens=100,
            completion_tokens=150,
            api_time=0.5,
            success=True,
            model="gpt-4o",
            provider="openai"
        )
        
        call_stats2 = CallStats(
            prompt_tokens=200,
            completion_tokens=300,
            api_time=0.7,
            success=True,
            model="gpt-4o",
            provider="openai"
        )
        
        # Patch _call_provider to return different stats for each call
        call_counter = [0]  # Use list for mutable closure
        
        async def mock_call_provider(*args, **kwargs):
            call_counter[0] += 1
            if call_counter[0] == 1:
                return (self.provider_result, call_stats1)
            else:
                return (self.provider_result, call_stats2)
        
        # Patch stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        with patch.object(
            self.enricher, 
            '_call_provider', 
            new_callable=AsyncMock,
            side_effect=mock_call_provider
        ):
            # Mock load_preset to return our mock config
            with patch('magicrowspy.config.load_preset', return_value=self.mock_config):
                # Call enrich with log_summary=True
                await self.enricher.enrich(
                    self.df,
                    "fake_config.ts",
                    reasoning=True,
                    log_summary=True
                )
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Check that statistics sum correctly
        output = captured_output.getvalue()
        self.assertIn("Total Rows Processed: 2", output)
        self.assertIn("Successful API Calls: 2", output)
        self.assertIn("Input Tokens:         300", output)  # 100 + 200
        self.assertIn("Output Tokens:        450", output)  # 150 + 300
        self.assertIn("Total Tokens:         750", output)  # 300 + 450
    
    @pytest.mark.asyncio
    async def test_cost_calculation(self):
        """Test that cost calculations are accurate."""
        # Use known token counts for easy verification
        call_stats = CallStats(
            prompt_tokens=1000000,  # 1M tokens for easy math
            completion_tokens=1000000,  # 1M tokens for easy math
            api_time=1.0,
            success=True,
            model="gpt-4o",
            provider="openai"
        )
        
        # Patch stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Patch _call_provider to return our known stats
        with patch.object(
            self.enricher, 
            '_call_provider', 
            new_callable=AsyncMock,
            return_value=(self.provider_result, call_stats)
        ):
            # Mock load_preset to return our mock config
            with patch('magicrowspy.config.load_preset', return_value=self.mock_config):
                # Patch get_token_prices to return known prices
                with patch('magicrowspy.utils.cost_utils.get_token_prices', return_value=(5.0, 15.0)):
                    # Call enrich with log_summary=True
                    await self.enricher.enrich(
                        self.df,
                        "fake_config.ts",
                        reasoning=True,
                        log_summary=True
                    )
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Check cost calculations
        output = captured_output.getvalue()
        self.assertIn("Estimated Input Cost: $5.000000", output)  # 1M * $5/M
        self.assertIn("Estimated Output Cost:$15.000000", output)  # 1M * $15/M
        self.assertIn("Estimated Total Cost: $20.000000", output)  # $5 + $15

if __name__ == '__main__':
    unittest.main()
