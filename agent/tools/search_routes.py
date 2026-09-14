"""
search_routes: read-only lookup against the routes table.
Used for the 'book' intent (find a route to book) and 'inquiry'
intent (check schedules/availability/pricing).
"""
from agent.db import get_connection


def search_routes(origin: str = None, destination: str = None,
                   transport_type: str = None, route_code: str = None) -> dict:
    """
    Returns matching routes. All filters are optional and combined
    with AND — pass only the ones you have.
    """
    query = "SELECT * FROM routes WHERE 1=1"
    params = []

    if origin:
        query += " AND origin LIKE ?"
        params.append(f"%{origin}%")
    if destination:
        query += " AND destination LIKE ?"
        params.append(f"%{destination}%")
    if transport_type:
        query += " AND transport_type = ?"
        params.append(transport_type)
    if route_code:
        query += " AND route_code = ?"
        params.append(route_code)

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    routes = [dict(row) for row in rows]
    return {"success": True, "count": len(routes), "routes": routes}