from axyn.database import ConsentResponse
from axyn.ui.consent import ConsentMenu, ConsentSelect
from collections import Counter


async def test_select_presents_all_options():
    select = ConsentSelect()

    values = Counter(option.value for option in select.options)
    responses = Counter(response.name for response in ConsentResponse)
    assert values == responses, "each ConsentResponse should appear exactly once"


async def test_select_has_different_labels():
    select = ConsentSelect()

    labels = Counter(option.label for option in select.options)
    for label, count in labels.items():
        assert count == 1, f'"{label}" should only appear once'


async def test_select_has_different_descriptions():
    select = ConsentSelect()

    descriptions = Counter(option.description for option in select.options)
    for description, count in descriptions.items():
        assert count == 1, f'"{description}" should only appear once'


async def test_menu_contains_select():
    menu = ConsentMenu()

    assert any(isinstance(child, ConsentSelect) for child in menu.children)

