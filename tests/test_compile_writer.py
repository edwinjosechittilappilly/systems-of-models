"""Writer sees only sampled observations, and question types retain mined values."""

from types import SimpleNamespace

import pytest

from som.compile import question_name
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

    def writer(context):
        seen.append(context)
        return {"name": "policy", "instructions": "Choose the governing policy"}

    question, provenance = write_question(candidate, writer, n_samples=3, seed=7)
    _, repeat = write_question(candidate, writer, n_samples=3, seed=7)
    assert isinstance(question, Choice)
    assert question.values == ["0", "1"]
    assert [option.description for option in question.options] == ["title 0", "title 1"]
    assert provenance == repeat
    assert provenance["writer"].endswith(".writer")
    assert seen[0] == seen[1] and len(seen[0]["samples"]) == 3
    assert all(set(sample) == {"input", "value", "title"} for sample in seen[0]["samples"])
    assert seen[0]["choices"] == [{"value": "0", "title": "title 0"}, {"value": "1", "title": "title 1"}]
    assert set(seen[0]) == {"samples", "choices"}


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
    seen = []

    def writer(context):
        seen.append(context)
        return {"name": "verify", "instructions": "Verify?"}

    question, _ = write_question(candidate, writer, seed=1)
    assert seen[0]["tool"] == "verify" and seen[0]["argument"] is None
    assert isinstance(question, Predicate)
    with pytest.raises(ValueError, match="n_samples"):
        write_question(candidate, lambda _: {}, n_samples=0, seed=1)


def test_writer_titles_become_contract_valid_names():
    # E4 found 52,135 E3a envelopes invalid because the writer named a question "Customer Support Intent".
    candidate = Candidate(
        kind="branch",
        name="verify",
        tool="verify",
        argument=None,
        examples=[Example("1", "ticket", True, None), Example("2", "other", False, None)],
        values=[True, False],
        support=2,
    )
    for title, expected in [("Customer Support Intent", "Customer_Support_Intent"), ("3 days?", "q_3_days")]:
        question, _ = write_question(candidate, lambda _, t=title: {"name": t, "instructions": "Verify?"}, seed=1)
        assert question.name == expected


def test_candidate_names_become_contract_identifiers():
    assert question_name("search_policy.retrieval_choice") == "search_policy__retrieval_choice"
    assert question_name("3 days?") == "q_3_days"
    assert len(question_name("a" * 100)) == 64
    Choice(question_name("search_policy.retrieval_choice"), "Choose", ["a", "b"])


@pytest.mark.parametrize("make", [lambda n: Predicate(n, "?"), lambda n: Choice(n, "?", ["a", "b"])])
def test_questions_reject_names_the_contract_cannot_carry(make):
    with pytest.raises(ValueError, match="question name"):
        make("Customer Support Intent")


def test_openai_writer_uses_structured_response():
    class Responses:
        def create(self, **kwargs):
            assert kwargs["text"]["format"]["strict"] is True
            assert '"input": "ticket"' in kwargs["input"]
            return SimpleNamespace(output_text='{"name":"n","instructions":"i","true_means":"yes","false_means":"no"}')

    writer = OpenAIQuestionWriter(client=SimpleNamespace(responses=Responses()))
    assert writer({"samples": [{"input": "ticket", "value": True}]})["name"] == "n"
