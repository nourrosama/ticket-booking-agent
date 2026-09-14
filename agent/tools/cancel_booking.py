from agent.db import get_connection


def cancel_booking(booking_id: int) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT status, route_id FROM bookings WHERE booking_id = ?",
            (booking_id,),
        ).fetchone()

        if row is None:
            return {"success": False, "error": f"No booking with booking_id {booking_id}"}

        if row["status"] in ("cancelled", "refunded"):
            return {"success": False, "error": f"Booking is already {row['status']}"}

        conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?",
            (booking_id,),
        )
        conn.execute(
            "UPDATE routes SET available_seats = available_seats + 1 WHERE route_id = ?",
            (row["route_id"],),
        )
        conn.commit()

        return {"success": True, "booking_id": booking_id, "status": "cancelled"}
    finally:
        conn.close()