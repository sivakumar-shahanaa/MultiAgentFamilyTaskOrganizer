from app.capabilities import household_capability


def test_household_capability_is_custom_pydantic_ai_capability() -> None:
    capability = household_capability()

    assert capability.id == "household_capabilities"
    toolset = capability.get_toolset()
    assert toolset is not None
