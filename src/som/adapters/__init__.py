"""Adapters: one class per provider surface, each a :class:`som.systems.Decider` that returns envelopes.

Provider SDKs are optional extras and are imported only when an adapter is built without a client.
"""

from som.adapters.anthropic import Anthropic
from som.adapters.gemini import Gemini
from som.adapters.openai import OpenAIChat, OpenAIDecisions, OpenAIResponses
from som.adapters.typesafe import TypeSafe

__all__ = ["Anthropic", "Gemini", "OpenAIChat", "OpenAIDecisions", "OpenAIResponses", "TypeSafe"]
