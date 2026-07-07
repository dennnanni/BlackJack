"""The outbox must survive crashes (it is on disk) and only forget a round
once it is explicitly acknowledged.
"""
from game_server.outbox import Outbox
from shared.messages import Result


def test_enqueue_and_ack(tmp_path):
    outbox = Outbox(tmp_path / 'outbox.db')
    outbox.enqueue('round-1', [Result('alice', -100.0), Result('bob', 50.0)])

    pending = outbox.pending()
    assert len(pending) == 1
    round_id, results = pending[0]
    assert round_id == 'round-1'
    assert results == [Result('alice', -100.0), Result('bob', 50.0)]

    outbox.ack('round-1')
    assert outbox.pending() == []


def test_entries_survive_reopen(tmp_path):
    path = tmp_path / 'outbox.db'
    Outbox(path).enqueue('round-1', [Result('alice', 25.0)])

    # Simulate a game-server restart: a fresh instance over the same file
    reopened = Outbox(path)
    assert reopened.pending() == [('round-1', [Result('alice', 25.0)])]


def test_failed_send_keeps_entry_until_ack(tmp_path):
    outbox = Outbox(tmp_path / 'outbox.db')
    outbox.enqueue('round-1', [Result('alice', 25.0)])

    # A failed delivery attempt acks nothing: the entry must still be there
    assert len(outbox.pending()) == 1
    assert len(outbox.pending()) == 1  # reading is not consuming

    outbox.ack('round-1')
    assert outbox.pending() == []


def test_duplicate_enqueue_is_ignored(tmp_path):
    outbox = Outbox(tmp_path / 'outbox.db')
    outbox.enqueue('round-1', [Result('alice', 25.0)])
    outbox.enqueue('round-1', [Result('alice', 25.0)])
    assert len(outbox.pending()) == 1
