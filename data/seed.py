"""
Seeds data/travel.sqlite with the schema + sample data for the
Customer Service Ticket Booking Agent assignment.

Design note: the assignment doc supplies exact SQL INSERT statements
for 20 linked records per table (customers/routes/bookings/refunds
reference each other by ID, e.g. booking 5 -> route 5 -> customer 5).
Re-typing that as Python dicts/tuples would risk breaking those FK
links through transcription errors, so this script keeps the DDL and
the seed INSERTs as raw SQL and runs them with executescript(). That
guarantees the linked IDs match exactly what the eval file expects.

Run with: python data/seed.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "travel.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    loyalty_tier TEXT DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    transport_type TEXT NOT NULL,
    carrier TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    price REAL NOT NULL,
    available_seats INTEGER NOT NULL,
    route_code TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    route_id INTEGER NOT NULL,
    booking_ref TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'confirmed',
    seat_number TEXT,
    booking_date TEXT NOT NULL,
    payment_amount REAL NOT NULL,
    payment_method TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    refund_amount REAL NOT NULL,
    refund_reason TEXT,
    refund_status TEXT DEFAULT 'pending',
    requested_date TEXT NOT NULL,
    processed_date TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id)
);
"""

SEED_DATA = """
INSERT INTO customers (full_name, email, phone, loyalty_tier) VALUES
('Ahmed Hassan', 'ahmed.hassan@gmail.com', '+201001234567', 'gold'),
('Fatma El-Sayed', 'fatma.elsayed@yahoo.com', '+201112345678', 'platinum'),
('Mohamed Ali', 'mohamed.ali@outlook.com', '+201223456789', 'standard'),
('Nour Ibrahim', 'nour.ibrahim@gmail.com', '+201034567890', 'silver'),
('Yasmin Khaled', 'yasmin.khaled@hotmail.com', '+201145678901', 'standard'),
('Omar Mostafa', 'omar.mostafa@gmail.com', '+201256789012', 'gold'),
('Hana Adel', 'hana.adel@yahoo.com', '+201067890123', 'standard'),
('Karim Samir', 'karim.samir@gmail.com', '+201178901234', 'silver'),
('Salma Tarek', 'salma.tarek@outlook.com', '+201289012345', 'platinum'),
('Youssef Magdy', 'youssef.magdy@gmail.com', '+201090123456', 'standard'),
('Mariam Fouad', 'mariam.fouad@yahoo.com', '+201101234560', 'gold'),
('Tamer Reda', 'tamer.reda@gmail.com', '+201212345601', 'standard'),
('Dina Sherif', 'dina.sherif@hotmail.com', '+201023456012', 'silver'),
('Amr Gamal', 'amr.gamal@outlook.com', '+201134560123', 'standard'),
('Rania Nabil', 'rania.nabil@gmail.com', '+201245601234', 'platinum'),
('Khaled Mahmoud', 'khaled.mahmoud@yahoo.com', '+201056012345', 'gold'),
('Sara Wael', 'sara.wael@gmail.com', '+201167012345', 'standard'),
('Hazem Ashraf', 'hazem.ashraf@outlook.com', '+201278012345', 'silver'),
('Laila Hossam', 'laila.hossam@gmail.com', '+201089012345', 'standard'),
('Mostafa Emad', 'mostafa.emad@yahoo.com', '+201190123456', 'gold');

INSERT INTO routes (origin, destination, transport_type, carrier, departure_time, arrival_time, price, available_seats, route_code) VALUES
('Cairo', 'Alexandria', 'train', 'Egyptian Railways', '2025-09-15T08:00:00', '2025-09-15T10:30:00', 150.00, 120, 'TR-101'),
('Cairo', 'Luxor', 'flight', 'EgyptAir', '2025-09-15T06:00:00', '2025-09-15T07:15:00', 1800.00, 45, 'EG-201'),
('Cairo', 'Aswan', 'flight', 'Nile Air', '2025-09-16T09:00:00', '2025-09-16T10:30:00', 2200.00, 38, 'NA-301'),
('Cairo', 'Hurghada', 'bus', 'Go Bus', '2025-09-15T22:00:00', '2025-09-16T04:00:00', 350.00, 49, 'GB-401'),
('Alexandria', 'Cairo', 'train', 'Egyptian Railways', '2025-09-16T14:00:00', '2025-09-16T16:30:00', 150.00, 95, 'TR-102'),
('Luxor', 'Aswan', 'train', 'Egyptian Railways', '2025-09-17T07:00:00', '2025-09-17T10:00:00', 120.00, 80, 'TR-103'),
('Hurghada', 'Cairo', 'flight', 'EgyptAir', '2025-09-18T12:00:00', '2025-09-18T13:00:00', 1600.00, 50, 'EG-202'),
('Cairo', 'Sharm El Sheikh', 'flight', 'Nile Air', '2025-09-15T10:00:00', '2025-09-15T11:00:00', 2000.00, 42, 'NA-302'),
('Sharm El Sheikh', 'Cairo', 'flight', 'EgyptAir', '2025-09-19T16:00:00', '2025-09-19T17:00:00', 1900.00, 55, 'EG-203'),
('Cairo', 'Marsa Alam', 'bus', 'Blue Bus', '2025-09-16T20:00:00', '2025-09-17T04:30:00', 400.00, 44, 'BB-501'),
('Alexandria', 'Luxor', 'train', 'Egyptian Railways', '2025-09-17T22:00:00', '2025-09-18T08:00:00', 280.00, 60, 'TR-104'),
('Aswan', 'Cairo', 'flight', 'EgyptAir', '2025-09-20T11:00:00', '2025-09-20T12:30:00', 2100.00, 40, 'EG-204'),
('Cairo', 'Dahab', 'bus', 'Go Bus', '2025-09-15T18:00:00', '2025-09-16T02:00:00', 380.00, 46, 'GB-402'),
('Luxor', 'Hurghada', 'bus', 'Blue Bus', '2025-09-18T06:00:00', '2025-09-18T10:00:00', 200.00, 48, 'BB-502'),
('Cairo', 'Siwa Oasis', 'bus', 'West Delta', '2025-09-19T07:00:00', '2025-09-19T15:00:00', 300.00, 35, 'WD-601'),
('Hurghada', 'Luxor', 'bus', 'Go Bus', '2025-09-20T08:00:00', '2025-09-20T12:00:00', 220.00, 47, 'GB-403'),
('Cairo', 'Ain Sokhna', 'bus', 'Go Bus', '2025-09-15T07:00:00', '2025-09-15T09:00:00', 100.00, 50, 'GB-404'),
('Sharm El Sheikh', 'Hurghada', 'flight', 'Nile Air', '2025-09-21T09:00:00', '2025-09-21T10:00:00', 1500.00, 36, 'NA-303'),
('Alexandria', 'Marsa Matrouh', 'bus', 'West Delta', '2025-09-16T06:00:00', '2025-09-16T10:00:00', 180.00, 42, 'WD-602'),
('Cairo', 'Fayoum', 'bus', 'Blue Bus', '2025-09-17T09:00:00', '2025-09-17T11:00:00', 80.00, 44, 'BB-503');

INSERT INTO bookings (customer_id, route_id, booking_ref, status, seat_number, booking_date, payment_amount, payment_method) VALUES
(1,  1,  'BK-20250901-001', 'confirmed',  'A12', '2025-09-01', 150.00,  'credit_card'),
(2,  2,  'BK-20250901-002', 'confirmed',  'B03', '2025-09-01', 1800.00, 'credit_card'),
(3,  3,  'BK-20250902-003', 'confirmed',  'C07', '2025-09-02', 2200.00, 'wallet'),
(4,  4,  'BK-20250902-004', 'confirmed',  'D15', '2025-09-02', 350.00,  'cash'),
(5,  5,  'BK-20250903-005', 'cancelled',  'A08', '2025-09-03', 150.00,  'credit_card'),
(6,  6,  'BK-20250903-006', 'confirmed',  'B22', '2025-09-03', 120.00,  'wallet'),
(7,  7,  'BK-20250904-007', 'confirmed',  'C01', '2025-09-04', 1600.00, 'credit_card'),
(8,  8,  'BK-20250904-008', 'pending',    'D10', '2025-09-04', 2000.00, 'wallet'),
(9,  9,  'BK-20250905-009', 'confirmed',  'A05', '2025-09-05', 1900.00, 'credit_card'),
(10, 10, 'BK-20250905-010', 'confirmed',  'B18', '2025-09-05', 400.00,  'cash'),
(11, 11, 'BK-20250906-011', 'confirmed',  'C14', '2025-09-06', 280.00,  'credit_card'),
(12, 12, 'BK-20250906-012', 'cancelled',  'D02', '2025-09-06', 2100.00, 'wallet'),
(1,  13, 'BK-20250907-013', 'confirmed',  'A20', '2025-09-07', 380.00,  'cash'),
(2,  14, 'BK-20250907-014', 'confirmed',  'B09', '2025-09-07', 200.00,  'credit_card'),
(13, 15, 'BK-20250908-015', 'pending',    'C11', '2025-09-08', 300.00,  'wallet'),
(14, 16, 'BK-20250908-016', 'confirmed',  'D06', '2025-09-08', 220.00,  'cash'),
(15, 17, 'BK-20250909-017', 'confirmed',  'A03', '2025-09-09', 100.00,  'credit_card'),
(16, 18, 'BK-20250909-018', 'refunded',   'B25', '2025-09-09', 1500.00, 'credit_card'),
(17, 19, 'BK-20250910-019', 'confirmed',  'C19', '2025-09-10', 180.00,  'wallet'),
(18, 20, 'BK-20250910-020', 'confirmed',  'D08', '2025-09-10', 80.00,   'cash');

INSERT INTO refunds (booking_id, refund_amount, refund_reason, refund_status, requested_date, processed_date) VALUES
(5,  150.00,  'Schedule change',              'approved',  '2025-09-03', '2025-09-05'),
(12, 2100.00, 'Flight cancelled by airline',  'approved',  '2025-09-06', '2025-09-08'),
(18, 1500.00, 'Personal emergency',           'approved',  '2025-09-09', '2025-09-11'),
(8,  2000.00, 'Changed travel plans',         'pending',   '2025-09-05', NULL),
(1,  150.00,  'Found cheaper option',         'rejected',  '2025-09-04', '2025-09-06'),
(2,  1800.00, 'Medical reason',               'approved',  '2025-09-05', '2025-09-07'),
(3,  1650.00, 'Partial refund - 24hr policy', 'approved',  '2025-09-06', '2025-09-08'),
(4,  175.00,  'Partial refund - 12hr policy', 'approved',  '2025-09-07', '2025-09-09'),
(6,  120.00,  'Duplicate booking',            'approved',  '2025-09-08', '2025-09-10'),
(7,  0.00,    'Too close to departure',       'rejected',  '2025-09-09', '2025-09-09'),
(9,  1900.00, 'Trip postponed',               'pending',   '2025-09-10', NULL),
(10, 400.00,  'Wrong destination booked',     'approved',  '2025-09-10', '2025-09-12'),
(11, 280.00,  'Family emergency',             'approved',  '2025-09-11', '2025-09-13'),
(13, 380.00,  'Weather concerns',             'pending',   '2025-09-12', NULL),
(14, 200.00,  'Schedule conflict',            'approved',  '2025-09-12', '2025-09-14'),
(15, 300.00,  'Changed mind',                 'rejected',  '2025-09-13', '2025-09-13'),
(16, 220.00,  'Health issue',                 'pending',   '2025-09-13', NULL),
(17, 100.00,  'Road closure reported',        'approved',  '2025-09-14', '2025-09-15'),
(19, 180.00,  'Visa issue',                   'pending',   '2025-09-15', NULL),
(20, 80.00,   'Found alternative transport',  'rejected',  '2025-09-15', '2025-09-15');
"""


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()  # fresh DB every run, so seeding is idempotent

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executescript(SEED_DATA)
    conn.commit()

    counts = {}
    for table in ("customers", "routes", "bookings", "refunds"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()

    print(f"Seeded {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()