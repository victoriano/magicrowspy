"""Statistics tracking for enrichment processes."""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class CallStats:
    """Statistics for a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_time: float = 0.0  # seconds
    success: bool = True
    model: str = ""
    provider: str = "openai"

@dataclass
class EnrichmentStats:
    """Aggregated statistics for an enrichment run."""
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float = 0.0
    total_rows: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_api_time: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    calls: List[CallStats] = field(default_factory=list)
    
    def add_call(self, stats: CallStats) -> None:
        """Add statistics from a single call."""
        self.calls.append(stats)
        if stats.success:
            self.successful_calls += 1
            self.total_prompt_tokens += stats.prompt_tokens
            self.total_completion_tokens += stats.completion_tokens
            self.total_api_time += stats.api_time
        else:
            self.failed_calls += 1
    
    def finish(self) -> None:
        """Mark the enrichment process as complete."""
        self.end_time = time.perf_counter()
    
    @property
    def elapsed_time(self) -> float:
        """Total elapsed wall clock time."""
        if self.end_time == 0:
            return time.perf_counter() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def processing_time(self) -> float:
        """Time spent in processing (non-API time)."""
        return self.elapsed_time - self.total_api_time
    
    @property
    def avg_api_time_per_call(self) -> float:
        """Average API time per successful call."""
        if self.successful_calls == 0:
            return 0
        return self.total_api_time / self.successful_calls
    
    @property
    def avg_time_per_row(self) -> float:
        """Average total time per row."""
        if self.total_rows == 0:
            return 0
        return self.elapsed_time / self.total_rows
    
    @property
    def total_tokens(self) -> int:
        """Total tokens (prompt + completion)."""
        return self.total_prompt_tokens + self.total_completion_tokens

def format_summary(
    stats: EnrichmentStats,
    input_price_per_million: float = 5.0,
    output_price_per_million: float = 15.0
) -> str:
    """Format enrichment statistics as a readable summary.
    
    Args:
        stats: EnrichmentStats object with collected metrics
        input_price_per_million: Price per million input tokens in USD
        output_price_per_million: Price per million output tokens in USD
        
    Returns:
        Formatted string with the summary
    """
    input_cost = (stats.total_prompt_tokens / 1_000_000) * input_price_per_million
    output_cost = (stats.total_completion_tokens / 1_000_000) * output_price_per_million
    total_cost = input_cost + output_cost
    
    return f"""
========== Enrichment Summary ==========
Total Rows Processed: {stats.total_rows}
Successful API Calls: {stats.successful_calls}
------------------------------------
Total Time Elapsed:   {stats.elapsed_time:.4f} s
Total API Time:       {stats.total_api_time:.4f} s
Total Processing Time:{stats.processing_time:.4f} s (Total - API)
Avg. API Time/Call:   {stats.avg_api_time_per_call:.4f} s
Avg. Total Time/Row:  {stats.avg_time_per_row:.4f} s
------------------------------------
Input Tokens:         {stats.total_prompt_tokens}
Output Tokens:        {stats.total_completion_tokens}
Total Tokens:         {stats.total_tokens}
------------------------------------
Estimated Input Cost: ${input_cost:.6f} (@ ${input_price_per_million}/M)
Estimated Output Cost:${output_cost:.6f} (@ ${output_price_per_million}/M)
Estimated Total Cost: ${total_cost:.6f}
======================================
"""
