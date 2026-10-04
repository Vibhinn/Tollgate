from src.cache.keys import CacheKeyBuilder, EXACT_CACHE_KEY_PREFIX
from src.utils.types import Message


def conversation(*turns: tuple[str, str]) -> list[Message]:
    return [Message(role=role, content=content) for role, content in turns]


def keys(messages, user_id="user-1", model="cheap", temperature=None):
    return CacheKeyBuilder().build_cache_keys(user_id=user_id, model=model, temperature=temperature, messages=messages)


def test_same_request_gives_the_same_keys():
    messages = conversation(("system", "be brief"), ("user", "capital of France?"))

    assert keys(messages) == keys(list(messages))


def test_prompt_is_the_last_user_message_even_when_an_assistant_turn_follows_it():
    messages = conversation(("user", "first"), ("assistant", "ok"), ("user", "second"), ("assistant", "prefill"))

    assert keys(messages).prompt == "second"


def test_same_last_message_in_different_conversations_does_not_share_a_cache_entry():
    """The original bug: two chats that both end in "yes" got each other's answer."""
    about_deleting = conversation(("user", "should I delete prod?"), ("assistant", "are you sure?"), ("user", "yes"))
    about_pizza = conversation(("user", "want pizza?"), ("assistant", "are you sure?"), ("user", "yes"))

    assert keys(about_deleting).exact_key != keys(about_pizza).exact_key
    assert keys(about_deleting).context_hash != keys(about_pizza).context_hash


def test_paraphrased_prompt_with_the_same_context_shares_the_context_hash():
    original = conversation(("system", "you are a geography bot"), ("user", "capital of France?"))
    paraphrased = conversation(("system", "you are a geography bot"), ("user", "France's capital city?"))

    assert keys(original).context_hash == keys(paraphrased).context_hash
    assert keys(original).exact_key != keys(paraphrased).exact_key


def test_changing_the_system_prompt_changes_both_keys():
    french = conversation(("system", "reply in French"), ("user", "hi"))
    german = conversation(("system", "reply in German"), ("user", "hi"))

    assert keys(french).exact_key != keys(german).exact_key
    assert keys(french).context_hash != keys(german).context_hash


def test_keys_are_scoped_per_user_model_and_temperature():
    messages = conversation(("user", "hi"))
    baseline = keys(messages)

    for other in (keys(messages, user_id="user-2"), keys(messages, model="fast"), keys(messages, temperature=0.2)):
        assert other.exact_key != baseline.exact_key
        assert other.context_hash != baseline.context_hash


def test_exact_key_is_namespaced_so_a_message_cannot_overwrite_other_redis_keys():
    """Regression test: the raw message used to be the Redis key, so caching
    the message "token:hacker" wrote a key auth accepted as a valid token."""
    for message in ("token:hacker", "in_flight", "successful"):
        exact_key = keys(conversation(("user", message))).exact_key

        assert exact_key.startswith(EXACT_CACHE_KEY_PREFIX)
        assert message not in exact_key
