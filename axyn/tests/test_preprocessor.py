from axyn.preprocessor import preprocess_index, preprocess_reply


def test_index_removes_whitespace():
    content = preprocess_index("   Hello, world!   \n")
    assert content == "Hello, world!"


def test_reply_removes_whitespace():
    content = preprocess_reply(
        "   Hello, world!   \n",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=4,
    )
    assert content == "Hello, world!"


def test_reply_replaces_prompt_author():
    content = preprocess_reply(
        "Hello <@1>! I'm Bob.",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=4,
    )
    assert content == "Hello <@3>! I'm Bob."


def test_reply_replaces_response_author():
    content = preprocess_reply(
        "Hello Bob! I'm <@2>.",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=4,
    )
    assert content == "Hello Bob! I'm <@4>."


def test_reply_swaps_authors():
    content = preprocess_reply(
        "Hello <@1>! I'm <@2>.",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=2,
        axyn_id=1,
    )
    assert content == "Hello <@2>! I'm <@1>."


def test_reply_replaces_axyn_out_of_context():
    content = preprocess_reply(
        "<@4> Who is Bob?",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=4,
    )
    assert content == "@everyone Who is Bob?"


def test_reply_replaces_axyn_in_context():
    # When Axyn is one of the other parameters too, that replacement
    # should take priority over @everyone.

    content = preprocess_reply(
        "<@1> Who is Bob?",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=1,
    )
    assert content == "<@3> Who is Bob?"


def test_reply_preserves_other_mentions():
    content = preprocess_reply(
        "Hi, I'm <@12345>!",
        original_prompt_author_id=1,
        original_response_author_id=2,
        current_prompt_author_id=3,
        axyn_id=4,
    )
    assert content == "Hi, I'm <@12345>!"

