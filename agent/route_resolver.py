"""
Shared route resolution -- used by both Policy Checker (to validate)
and Tool Executor (to act), so a customer request resolves to the
same route the same way in both places. Same "single source of
truth" reasoning as policy.py's calculate_refund().
"""
from agent.tools.search_routes import search_routes

SEARCH_FIELDS = ("origin", "destination", "transport_type")


def resolve_route(entities: dict) -> dict:
    """
    Returns one of:
      {"status": "resolved", "route": {...}, "matches": [route]}       -- exactly one match, safe to book
      {"status": "ambiguous", "route": None, "matches": [route, ...]}  -- more than one, present as options
      {"status": "not_found", "route": None, "matches": []}            -- zero matches
      {"status": "no_criteria", "route": None, "matches": []}          -- nothing to search on yet
    """
    if entities.get("route_code"):
        found = search_routes(route_code=entities["route_code"])
    else:
        filters = {k: entities[k] for k in SEARCH_FIELDS if k in entities}
        if not filters:
            return {"status": "no_criteria", "route": None, "matches": []}
        found = search_routes(**filters)

    routes = found["routes"]
    if len(routes) == 1:
        return {"status": "resolved", "route": routes[0], "matches": routes}
    if len(routes) == 0:
        return {"status": "not_found", "route": None, "matches": []}
    return {"status": "ambiguous", "route": None, "matches": routes}