import pytest
from bench.common.labels import BANKING77
from bench.tasks.environment import PolicyKB, SupportEnvironment, augment_ticket
from bench.tasks.policy import generate_policy, load_policy


@pytest.mark.parametrize("granularity", [4, 12])
def test_frozen_policy_is_reproducible_and_covers_banking77(granularity):
    policy = load_policy(granularity)
    assert policy == generate_policy(granularity)
    assert [entry["id"] for entry in policy] == list(BANKING77)
    assert len({entry["department"] for entry in policy}) == granularity
    assert {entry["priority"] for entry in policy} == {"high", "normal"}
    assert {entry["identity_check"] for entry in policy} == {True, False}


def test_granularity_rejected():
    with pytest.raises(ValueError, match="granularity"):
        load_policy(5)
    with pytest.raises(ValueError, match="granularity"):
        generate_policy(5)


def test_policy_search_exact_id_and_top_five_are_deterministic():
    kb = PolicyKB()
    first = kb.search_policy("card payment")
    assert len(first) == 5
    assert first == kb.search_policy("card payment")
    assert all(set(entry) == {"id", "title"} for entry in first)
    assert kb.search_policy("reverted_card_payment?")[0]["id"] == "reverted_card_payment?"
    first[0]["title"] = "mutated"
    assert kb.search_policy("card payment")[0]["title"] != "mutated"


def test_custom_entries_support_new_and_split_governing_entries():
    entries = [
        {
            "id": "split-new",
            "title": "Split card issue",
            "department": "new",
            "priority": "high",
            "identity_check": False,
        },
    ]
    kb = PolicyKB(entries=entries)
    assert kb.search_policy("split-new") == [{"id": "split-new", "title": "Split card issue"}]
    entries[0]["priority"] = "normal"
    assert kb.get_entry("split-new")["priority"] == "high"
    with pytest.raises(KeyError):
        kb.get_entry("missing")
    with pytest.raises(ValueError, match="duplicate"):
        PolicyKB(entries=entries * 2)


def test_ticket_augmentation_is_deterministic_and_distinguishes_tickets():
    ticket = augment_ticket("Help me", ticket_id="ticket-1")
    assert ticket == augment_ticket("Help me", ticket_id="ticket-1")
    assert ticket["text"].startswith("Help me\n")
    assert ticket["account_id"] in ticket["text"]
    assert ticket["account_id"] != augment_ticket("Help me", ticket_id="ticket-2")["account_id"]
    assert ticket["amount"] is None
    assert ticket["merchant"] is None


def test_transaction_distractors_are_copyable_from_ticket_text():
    ticket = augment_ticket("My card payment was declined", ticket_id="ticket-1")
    assert isinstance(ticket["amount"], float)
    assert f"{ticket['amount']:.2f}" in ticket["text"]
    assert ticket["merchant"] in ticket["text"]


def test_transfer_omits_merchant():
    ticket = augment_ticket("My transfer failed", ticket_id="ticket-1")
    assert ticket["amount"] is not None
    assert ticket["merchant"] is None


@pytest.mark.parametrize("verify", [False, True])
def test_substitution_follows_explicit_d2_not_policy_gold(verify):
    entry = {
        "id": "decision",
        "title": "Decision",
        "department": "cards",
        "priority": "high",
        "identity_check": not verify,
    }
    env = SupportEnvironment(PolicyKB(entries=[entry]))
    route = env.substitute("decision", "account", verify, note="help", amount=12.5, merchant="shop")
    assert route == {
        "department": "cards",
        "priority": "high",
        "queue": "cards_queue",
        "note": "help",
        "account_id": "account",
        "amount": 12.5,
        "merchant": "shop",
    }
    assert env.routes == [route]
    assert ("account" in env.verified_accounts) is verify
    assert [event["tool"] for event in env.events] == (
        ["search_policy", "get_policy", "verify_identity", "route_ticket"]
        if verify
        else ["search_policy", "get_policy", "route_ticket"]
    )
    assert env.agent_calls == 0
    assert env.agent_cost == 0.0


def test_missing_entry_does_not_route_or_verify():
    env = SupportEnvironment(PolicyKB())
    with pytest.raises(KeyError):
        env.substitute("not-a-policy", "account", True)
    assert env.routes == []
    assert env.verified_accounts == set()


def test_account_lookup_and_verification_are_observable():
    env = SupportEnvironment(PolicyKB(), accounts={"a": {"status": "open"}})
    account = env.get_account("a")
    assert account["account_id"] == "a"
    assert account["status"] == "open"
    assert account == env.get_account("a")
    assert isinstance(account["balance"], float)
    assert env.verify_identity("a") == {"account_id": "a", "verified": True}
    assert [event["tool"] for event in env.events] == ["get_account", "get_account", "verify_identity"]
