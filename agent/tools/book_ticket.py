from datetime import date

from agent.db import get_connection
from agent.policy import next_booking_ref


def book_ticket(customer_id: int, route_id: int, payment_method: str) -> dict:
    conn = get_connection()
    try:
        route = conn.execute(
            "SELECT * FROM routes WHERE route_id = ?", (route_id,)
        ).fetchone()

        if route is None:
            return {"success": False, "error": f"No route with route_id {route_id}"}

        if route["available_seats"] <= 0:
            return {"success": False, "error": "No seats available on this route"}

        today = date.today().isoformat()
        existing_today = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE booking_date = ?", (today,)
        ).fetchone()[0]
        booking_ref = next_booking_ref(existing_today, today)

        seat_number = f"{chr(65 + (existing_today % 4))}{(existing_today % 30) + 1:02d}"

        cur = conn.execute(
            """INSERT INTO bookings
               (customer_id, route_id, booking_ref, status, seat_number,
                booking_date, payment_amount, payment_method)
               VALUES (?, ?, ?, 'confirmed', ?, ?, ?, ?)""",
            (customer_id, route_id, booking_ref, seat_number,
             today, route["price"], payment_method),
        )
        conn.execute(
            "UPDATE routes SET available_seats = available_seats - 1 WHERE route_id = ?",
            (route_id,),
        )
        conn.commit()

        return {
            "success": True,
            "booking_id": cur.lastrowid,
            "booking_ref": booking_ref,
            "seat_number": seat_number,
            "payment_amount": route["price"],
        }
    finally:
        conn.close()