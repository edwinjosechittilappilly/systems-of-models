"""Writer sees only sampled observations, and question types retain mined values."""

from types import SimpleNamespace

import pytest

from som.compile.mining import Candidate, Example
from som.compile.writer import OpenAIQuestionWriter, write_question
from som.questions import Choice, Predicate


def test_writer_only_receives_samples_and_reproduces_selection():
    candidate = Candidate(
        kind="retrieval_choice",
        name="policy",
        tool="search",
        argument=None,
        examples=[Example(str(i), f"ticket {i}", str(i % 2), f"title {i % 2}") for i in range(10)],
        values=["0", "1"],
        support=10,
    )
    seen = []

    def writer(samples):
        seen.append(samples)
        return {"name": "policy", "instructions": "Choose the governing policy"}

    question, provenance = write_question(candidate, writer, n_samples=3, seed=7)
    _, repeat = write_question(candidate, writer, n_samples=3, seed=7)
    assert isinstance(question, Choice)
    assert question.values == ["0", "1"]
    assert provenance == repeat
    assert seen[0] == seen[1] and len(seen[0]) == 3
    assert all(set(sample) == {"input", "value", "title"} for sample in seen[0])


def test_writer_branch_becomes_predicate():
    candidate = Candidate(
        kind="branch",
        name="verify",
        tool="verify",
        argument=None,
        examples=[Example("1", "ticket", True, None), Example("2", "other", False, None)],
        values=[True, False],
        support=2,
    )
    question, _ = write_question(candidate, lambda _: {"name": "verify", "instructions": "Verify?"}, seed=1)
    assert isinstance(question, Predicate)
    with pytest.raises(ValueError, match="n_samples"):
        write_question(candidate, lambda _: {}, n_samples=0, seed=1)


def test_openai_writer_uses_structured_response():
    class Responses:
        def create(self, **kwargs):
            assert kwargs["text"]["format"]["strict"] is True
            assert '"input": "ticket"' in kwargs["input"]
            return SimpleNamespace(output_text='{"name":"n","instructions":"i","true_means":"yes","false_means":"no"}')

    writer = OpenAIQuestionWriter(client=SimpleNamespace(responses=Responses()))
    assert writer([{"input": "ticket", "value": True}])["name"] == "n"
