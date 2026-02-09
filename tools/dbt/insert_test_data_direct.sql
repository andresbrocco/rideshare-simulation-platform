-- Insert test data directly into Bronze tables

-- bronze_drivers (must be first - referenced by other tables)
INSERT INTO bronze_drivers VALUES
    ('driver-profile-001', 'D001', CAST('2026-01-15 08:00:00' AS TIMESTAMP), 'driver.profile_created',
     'John Driver', 'john.driver@example.com', '+5511987654321',
     'Toyota', 'Corolla', 2020, 'ABC1234', 'White',
     CAST('2026-01-15 08:00:01' AS TIMESTAMP));

-- bronze_riders (must be early - referenced by other tables)
INSERT INTO bronze_riders VALUES
    ('rider-profile-001', 'R001', CAST('2026-01-15 07:00:00' AS TIMESTAMP), 'rider.profile_created',
     'Jane Rider', 'jane.rider@example.com', '+5511912345678',
     CAST('2026-01-15 07:00:01' AS TIMESTAMP));

-- bronze_trips
INSERT INTO bronze_trips VALUES
    ('trip-001', 'trip.requested', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), NULL,
     CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
    ('trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:05:01' AS TIMESTAMP)),
    ('trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
     'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
     CAST('2026-01-15 10:15:01' AS TIMESTAMP));

-- bronze_gps_pings
INSERT INTO bronze_gps_pings VALUES
    ('gps-001', 'driver', 'D001', CAST('2026-01-15 10:01:00' AS TIMESTAMP),
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     CAST(10.0 AS DECIMAL(2,1)), CAST(45.0 AS DECIMAL(3,1)), CAST(5.0 AS DECIMAL(3,1)),
     'T001', 'matched', CAST('2026-01-15 10:01:01' AS TIMESTAMP)),
    ('gps-002', 'rider', 'R001', CAST('2026-01-15 10:01:00' AS TIMESTAMP),
     ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
     CAST(10.0 AS DECIMAL(2,1)), CAST(0.0 AS DECIMAL(3,1)), CAST(0.0 AS DECIMAL(3,1)),
     'T001', 'matched', CAST('2026-01-15 10:01:01' AS TIMESTAMP));

-- bronze_driver_status
INSERT INTO bronze_driver_status VALUES
    ('status-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'idle', NULL, 'manual',
     ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
     CAST('2026-01-15 09:00:01' AS TIMESTAMP)),
    ('status-002', 'D001', CAST('2026-01-15 17:00:00' AS TIMESTAMP), 'offline', 'idle', 'manual',
     ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
     CAST('2026-01-15 17:00:01' AS TIMESTAMP));

-- bronze_surge_updates
INSERT INTO bronze_surge_updates VALUES
    ('surge-001', 'PIN', CAST('2026-01-15 10:00:00' AS TIMESTAMP), CAST(1.0 AS DECIMAL(2,1)),
     CAST(1.2 AS DECIMAL(2,1)), 10, 15, 60, CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
    ('surge-002', 'PIN', CAST('2026-01-15 10:30:00' AS TIMESTAMP), CAST(1.2 AS DECIMAL(2,1)),
     CAST(1.5 AS DECIMAL(2,1)), 8, 20, 60, CAST('2026-01-15 10:30:01' AS TIMESTAMP)),
    ('surge-003', 'PIN', CAST('2026-01-15 10:45:00' AS TIMESTAMP), CAST(1.5 AS DECIMAL(2,1)),
     CAST(1.8 AS DECIMAL(2,1)), 6, 25, 60, CAST('2026-01-15 10:45:01' AS TIMESTAMP));

-- bronze_payments
INSERT INTO bronze_payments VALUES
    ('payment-001', 'PAY001', 'T001', CAST('2026-01-15 10:16:00' AS TIMESTAMP), 'R001', 'D001',
     'credit_card', '****1234', CAST(25.50 AS DECIMAL(4,2)), CAST(25.0 AS DECIMAL(3,1)),
     CAST(6.38 AS DECIMAL(3,2)), CAST(19.12 AS DECIMAL(4,2)), CAST('2026-01-15 10:16:01' AS TIMESTAMP));

-- bronze_ratings
INSERT INTO bronze_ratings VALUES
    ('rating-001', 'T001', CAST('2026-01-15 10:20:00' AS TIMESTAMP), 'rider', 'R001', 'driver', 'D001',
     CAST(5.0 AS DECIMAL(2,1)), CAST('2026-01-15 10:20:01' AS TIMESTAMP));
