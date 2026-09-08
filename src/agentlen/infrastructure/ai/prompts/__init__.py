"""Versioned prompt templates."""

from agentlen.infrastructure.ai.prompts.analysis import (
    DATA_BLOCK_CLOSE,
    DATA_BLOCK_OPEN,
    INSTRUCTION_BLOCK_CLOSE,
    INSTRUCTION_BLOCK_OPEN,
    PROMPT_VERSION,
    build_analysis_prompt,
    wrap_as_data,
    wrap_as_instruction,
)

__all__ = [
    "DATA_BLOCK_CLOSE",
    "DATA_BLOCK_OPEN",
    "INSTRUCTION_BLOCK_CLOSE",
    "INSTRUCTION_BLOCK_OPEN",
    "PROMPT_VERSION",
    "build_analysis_prompt",
    "wrap_as_data",
    "wrap_as_instruction",
]
