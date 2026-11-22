"""Adapters: one class per provider surface, each a :class:`som.systems.Decider` that returns envelopes.

Provider SDKs are optional extras and are imported only when an adapter is built without a client.
"""

from som.adapters.openai import OpenAIChat, OpenAIDecisions, OpenAIResponses
from som.adapters.typesafe import TypeSafe

__all__ = ["OpenAIChat", "OpenAIDecisions", "OpenAIResponses", "TypeSafe"]
