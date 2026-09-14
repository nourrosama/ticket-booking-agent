from agent.db import get_connection


def get_booking_status(booking_ref: str = None, booking_id: int = None) -> dict:
    if not booking_ref and not booking_id:
        return {"success": False, "error": "booking_ref or booking_id is required"}

    query = """
        SELECT b.booking_id, b.booking_ref, b.status, b.seat_number,
               b.booking_date, b.payment_amount, b.payment_method,
               c.full_name AS customer_name, c.loyalty_tier,
               r.origin, r.destination, r.transport_type, r.carrier,
               r.departure_time, r.arrival_time
        FROM bookings b
        JOIN customers c ON b.customer_id = c.customer_id
        JOIN routes r ON b.route_id = r.route_id
        WHERE {} = ?
    """.format("b.booking_ref" if booking_ref else "b.booking_id")

    conn = get_connection()
    row = conn.execute(query, (booking_ref or booking_id,)).fetchone()
    conn.close()

    if row is None:
        return {"success": False, "error": "No booking found matching that reference"}

    return {"success": True, "booking": dict(row)}