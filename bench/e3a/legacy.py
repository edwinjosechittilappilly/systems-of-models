"""Compatibility for the frozen E3a and E3b experiments, not new experiments.

Archived requests and questions used non-identifier question names (writer titles), which E4 reports as invalid.
Replay and recording of the archived runs must retain them to preserve cache keys and archived results.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import som.compile.writer as writer
import som.questions as questions


@contextmanager
def archived_question_names() -> Iterator[None]:
    """Temporarily restore E3a's original unchecked, unslugged question names."""
    check_name, question_name = questions._check_name, writer.question_name
    questions._check_name = lambda name: None
    writer.question_name = lambda name: name
    try:
        yield
    finally:
        questions._check_name = check_name
        writer.question_name = question_name
