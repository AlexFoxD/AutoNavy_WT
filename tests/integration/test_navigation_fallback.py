"""Regression: navigation falls back across capture zones after no-route results."""
from autonavy.navigation.planner import PlanResult
from test_navigation_runtime import navigation_rig


def _fail(planner, error='No reachable route'):
    planner.result = PlanResult(planner.requests[-1].key, None, error)


def test_unreachable_destination_tries_each_other_zone_once_then_stops():
    app, backend, clock, telemetry, vision, step, planner = navigation_rig()
    try:
        telemetry.zones = ((.7, .5), (.2, .5), (.5, .2))
        navigation = app.policy.navigation

        step(.1)
        assert len(planner.requests) == 1
        seen = {navigation.destination}

        # First failed destination -> a different live zone is selected.
        _fail(planner)
        step(.1)
        assert navigation.last_error is None
        assert navigation.destination not in seen
        seen.add(navigation.destination)
        step(.1)
        assert len(planner.requests) == 2

        # Second failed destination -> the final untried zone is selected.
        _fail(planner)
        step(.1)
        assert navigation.last_error is None
        assert navigation.destination not in seen
        seen.add(navigation.destination)
        step(.1)
        assert len(planner.requests) == 3
        assert seen == set(telemetry.zones)

        # Once all current zones have failed, do not spin/re-submit forever.
        _fail(planner)
        step(.1)
        assert navigation.last_error == 'No reachable route'
        request_count = len(planner.requests)
        for _ in range(5):
            step(.1)
        assert len(planner.requests) == request_count
    finally:
        app.close()
