import pytest
from src.llm.conversation import ConversationManager, DEFAULT_SYSTEM_PROMPT


def test_initialization_with_default_prompt():
    """Test: ConversationManager initializes with default system prompt"""
    cm = ConversationManager()
    assert cm.system_prompt == DEFAULT_SYSTEM_PROMPT
    assert cm.history == []
    assert cm.max_history_messages == 20


def test_initialization_with_custom_prompt():
    """Test: ConversationManager accepts custom system prompt"""
    cm = ConversationManager(system_prompt="You are a test bot.")
    assert cm.system_prompt == "You are a test bot."


def test_add_user_message():
    """Test: add_user_message() adds to history"""
    cm = ConversationManager()
    cm.add_user_message("Hello there")
    assert len(cm.history) == 1
    assert cm.history[0] == {"role": "user", "content": "Hello there"}


def test_add_assistant_message():
    """Test: add_assistant_message() adds to history"""
    cm = ConversationManager()
    cm.add_assistant_message("Hi! How can I help?")
    assert len(cm.history) == 1
    assert cm.history[0] == {"role": "assistant", "content": "Hi! How can I help?"}


def test_empty_messages_ignored():
    """Test: Empty or whitespace-only messages are not added"""
    cm = ConversationManager()
    cm.add_user_message("")
    cm.add_user_message("   ")
    cm.add_assistant_message("")
    assert len(cm.history) == 0


def test_get_messages_includes_system_prompt():
    """Test: get_messages() prepends system prompt"""
    cm = ConversationManager()
    cm.add_user_message("Hello")
    messages = cm.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_conversation_flow():
    """Test: Multi-turn conversation tracks correctly"""
    cm = ConversationManager()
    cm.add_user_message("Hello")
    cm.add_assistant_message("Hi there!")
    cm.add_user_message("How are you?")
    cm.add_assistant_message("I'm doing great!")
    cm.add_user_message("Good to hear")

    messages = cm.get_messages()
    assert len(messages) == 6  # system + 5 messages
    assert cm.get_turn_count() == 3


def test_history_trimming():
    """Test: History trims oldest messages when exceeding max"""
    cm = ConversationManager(max_history_messages=4)
    cm.add_user_message("msg1")
    cm.add_assistant_message("resp1")
    cm.add_user_message("msg2")
    cm.add_assistant_message("resp2")
    cm.add_user_message("msg3")  # This should trim msg1

    assert len(cm.history) == 4
    assert cm.history[0]["content"] == "resp1"  # msg1 was trimmed


def test_reset_clears_history():
    """Test: reset() clears history but keeps system prompt"""
    cm = ConversationManager()
    cm.add_user_message("Hello")
    cm.add_assistant_message("Hi!")
    cm.reset()

    assert len(cm.history) == 0
    assert cm.system_prompt is not None
    messages = cm.get_messages()
    assert len(messages) == 1  # Just system prompt
