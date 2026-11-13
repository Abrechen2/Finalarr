from finalarr.core.codec import dump_memory, load_memory
from finalarr.core.model import SeasonMemory


def test_round_trip():
    memory = SeasonMemory("aired", True, frozenset({3, 1}), frozenset({3}), 12, 12, 4, True, 2)
    assert load_memory(dump_memory(memory)) == memory


def test_empty_is_initial():
    assert load_memory(None) == SeasonMemory.initial()
