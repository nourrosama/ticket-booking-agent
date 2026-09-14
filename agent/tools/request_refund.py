"""
request_refund: looks up the booking + route + customer, runs the
shared calculate_refund() from policy.py, then writes a refund
record and updates the booking/route accordingly.

Design choice: since the refund percentage is a deterministic rule
(not a judgment call), a refund with percentage > 0 is auto-approved
here rather than left 'pending' for manual review. This keeps the
agent able to fully resolve a refund request in one turn.
"""
from datetime import date

from agent.db import get_connection
from agent.policy import calculate_refund


def request_refund(booking_id: int, reason: str = "Customer requested") -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT b.booking_id, b.status, b.route_id, b.payment_amount,
                      c.loyalty_tier, r.departure_time
               FROM bookings b
               JOIN customers c ON b.customer_id = c.customer_id
               JOIN routes r ON b.route_id = r.route_id
               WHERE b.booking_id = ?""",
            (booking_id,),
        ).fetchone()

        if row is None:
            return {"success": False, "error": f"No booking with booking_id {booking_id}"}

        if row["status"] in ("cancelled", "refunded"):
            return {"success": False, "error": f"Booking is already {row['status']}"}

        refund = calculate_refund(
            departure_time=row["departure_time"],
            loyalty_tier=row["loyalty_tier"],
            payment_amount=row["payment_amount"],
        )

        refund_status = "approved" if refund["percentage"] > 0 else "rejected"
        today = date.today().isoformat()

        cur = conn.execute(
            """INSERT INTO refunds
               (booking_id, refund_amount, refund_reason, refund_status,
                requested_date, processed_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (booking_id, refund["amount"], reason, refund_status, today,
             today if refund_status == "approved" else None),
        )

        # requesting a refund cancels the booking either way, and frees
        # the seat back up on the route regardless of refund amount
        new_status = "refunded" if refund_status == "approved" else "cancelled"
        conn.execute(
            "UPDATE bookings SET status = ? WHERE booking_id = ?",
            (new_status, booking_id),
        )
        conn.execute(
            "UPDATE routes SET available_seats = available_seats + 1 WHERE route_id = ?",
            (row["route_id"],),
        )
        conn.commit()

        return {
            "success": True,
            "refund_id": cur.lastrowid,
            "refund_status": refund_status,
            "percentage": refund["percentage"],
            "refund_amount": refund["amount"],
            "policy_applied": refund["policy_applied"],
            "reason": refund["reason"],
        }
    finally:
        conn.close()