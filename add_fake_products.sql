-- Add 5 fake products to cheapa database for storefront testing
-- Run this on the core VM: ssh core-vm "docker exec cheapa_postgres_primary psql -U postgres -d cheapa -f /tmp/add_fake_products.sql"

-- First check if products table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'products') THEN
        RAISE EXCEPTION 'Products table does not exist. Run migrations first!';
    END IF;
END $$;

-- Clear existing products
TRUNCATE TABLE products RESTART IDENTITY CASCADE;

-- Insert 5 fake products
INSERT INTO products (
    name, 
    description, 
    initial_price, 
    final_price, 
    currency, 
    availability, 
    quantity_available, 
    brand, 
    category, 
    image_url,
    created_at,
    updated_at
) VALUES
(
    'Wireless Bluetooth Headphones',
    'High-quality over-ear headphones with active noise cancellation and 30-hour battery life. Perfect for music lovers and commuters.',
    79.99,
    59.99,
    'USD',
    'in_stock',
    150,
    'AudioPro',
    'Electronics',
    'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800',
    NOW(),
    NOW()
),
(
    'Smart Watch Series 5',
    'Advanced fitness tracker with heart rate monitor, GPS, and waterproof design. Track your workouts and stay connected.',
    299.99,
    249.99,
    'USD',
    'in_stock',
    85,
    'TechTime',
    'Wearables',
    'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800',
    NOW(),
    NOW()
),
(
    'Premium Coffee Maker',
    'Programmable 12-cup coffee maker with thermal carafe and auto-brew feature. Wake up to fresh coffee every morning.',
    129.99,
    99.99,
    'USD',
    'in_stock',
    45,
    'BrewMaster',
    'Home & Kitchen',
    'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=800',
    NOW(),
    NOW()
),
(
    'Ergonomic Office Chair',
    'Premium office chair with adjustable lumbar support, breathable mesh back, and 360-degree swivel. Work comfortably all day.',
    399.99,
    299.99,
    'USD',
    'in_stock',
    25,
    'ComfortSeating',
    'Furniture',
    'https://images.unsplash.com/photo-1580480055273-228ff5388ef8?w=800',
    NOW(),
    NOW()
),
(
    '4K Action Camera',
    'Waterproof 4K action camera with image stabilization and WiFi connectivity. Capture your adventures in stunning detail.',
    249.99,
    199.99,
    'USD',
    'in_stock',
    60,
    'ProCam',
    'Electronics',
    'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800',
    NOW(),
    NOW()
);

-- Show results
SELECT 
    id,
    name,
    final_price,
    category,
    availability
FROM products
ORDER BY id;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Successfully added 5 fake products!';
    RAISE NOTICE '🌐 Check storefront at: http://35.202.126.214:3000';
END $$;

