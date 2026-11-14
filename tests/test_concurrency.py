"""The money test: many patients race for one slot — exactly one wins.

On PostgreSQL this is guaranteed by ``SELECT ... FOR UPDATE`` row locking;
the UNIQUE constraint on ``appointments.slot_id`` is the final safety net
(and the only guard needed on the SQLite quick-start backend).
"""
import threading

from tests.conftest import register


def test_five_patients_race_for_one_slot(app, doctor_with_slots):
    _client, _user, slot_ids = doctor_with_slots
    slot_id = slot_ids[0]
    n_racers = 5

    results = {}
    barrier = threading.Barrier(n_racers)

    def attempt(i):
        # Fresh client + fresh session per racer, created inside the thread.
        racer = app.test_client()
        register(racer, email=f"racer{i}@test.local")
        barrier.wait()  # everyone fires at the same moment
        resp = racer.post("/api/appointments",
                          json={"slot_id": slot_id, "symptoms": f"race {i}"})
        results[i] = resp.status_code

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(n_racers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(results) == n_racers, "every racer got a response"
    winners = [code for code in results.values() if code == 201]
    losers = [code for code in results.values() if code == 409]
    assert len(winners) == 1, f"expected exactly one booking, got {results}"
    assert len(losers) == n_racers - 1

    # And the database agrees: one appointment, slot marked booked.
    from app.extensions import db
    from app.models import Appointment, Slot

    with app.app_context():
        assert db.session.query(Appointment).count() == 1
        assert db.session.get(Slot, slot_id).status == Slot.STATUS_BOOKED
