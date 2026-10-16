import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pymysql

try:
    pymysql.install_as_MySQLdb()
except Exception:
    pass

# Load environment
env_path_app = Path(__file__).resolve().parent.parent / "app" / ".env"
env_path_parent = Path(__file__).resolve().parent.parent / ".env"
if env_path_app.exists():
    load_dotenv(env_path_app)
else:
    load_dotenv(env_path_parent)

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/ecomproff")

# Parse connection parameters
def parse_db_url(url: str):
    # e.g. mysql+pymysql://root:root@localhost:3306/ecomproff
    clean = url.replace("mysql+pymysql://", "").replace("mysql://", "")
    auth, rest = clean.split("@")
    if ":" in auth:
        user, password = auth.split(":", 1)
    else:
        user, password = auth, ""
    
    host_port, dbname = rest.split("/", 1)
    dbname = dbname.split("?")[0]
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        port = int(port)
    else:
        host, port = host_port, 3306
    return host, port, user, password, dbname

def run_seed():
    host, port, user, password, dbname = parse_db_url(DATABASE_URL)
    print(f"Connecting to MySQL: {host}:{port} as {user} for database {dbname}...")
    
    # Connect without db first to ensure db exists
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.close()
    except Exception as e:
        print(f"Notice during db check: {e}")

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=dbname, autocommit=True)
    cur = conn.cursor()

    schema_file = Path(__file__).parent / "schema.sql"
    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Execute table definitions
    for statement in sql_content.split(";"):
        stmt = statement.strip()
        if stmt and not stmt.lower().startswith("create database") and not stmt.lower().startswith("use "):
            try:
                cur.execute(stmt)
            except Exception as e:
                print(f"Schema statement warning: {e}")

    # Ensure login1 has role and phone columns if table already existed
    try:
        cur.execute("SHOW COLUMNS FROM login1 LIKE 'role'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE login1 ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'customer'")
            print("Added 'role' column to login1.")
    except Exception as e:
        pass

    try:
        cur.execute("SHOW COLUMNS FROM login1 LIKE 'phone'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE login1 ADD COLUMN phone VARCHAR(20) DEFAULT NULL")
            print("Added 'phone' column to login1.")
    except Exception as e:
        pass

    # Ensure admin user exists
    # Use passlib/bcrypt if available
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin_pass_hash = pwd_context.hash("Admin@123")
    except Exception:
        admin_pass_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW" # Pre-hashed Admin@123

    cur.execute("SELECT id FROM login1 WHERE email = %s", ("admin@ecomproff.com",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO login1 (name, email, password, role, phone) VALUES (%s, %s, %s, %s, %s)",
            ("Administrator", "admin@ecomproff.com", admin_pass_hash, "admin", "9876543210")
        )
        print("Created default admin user: admin@ecomproff.com (Password: Admin@123)")

    # Seed Categories
    categories = [
        ("Mobiles", "mobiles", "Smartphone", "Latest smartphones, 5G devices & accessories"),
        ("Electronics & Laptops", "electronics", "Laptop", "High-performance laptops, PCs and hardware"),
        ("Fashion & Apparel", "fashion", "Shirt", "Trendy clothing, apparel and fashion wear"),
        ("TV & Appliances", "tv-appliances", "Tv", "Smart TVs, washing machines and home appliances"),
        ("Furniture & Decor", "furniture", "Armchair", "Modern furniture, decor and comfortable living"),
        ("Grocery & Essentials", "grocery", "ShoppingBag", "Daily groceries, staples and home needs"),
        ("Watches", "watches", "Watch", "Luxury, smart and classic wristwatches"),
        ("Bags & Sunglasses", "bags-sunglasses", "Glasses", "Designer handbags, backpacks and premium sunglasses"),
        ("Audio & Cameras", "audio-cameras", "Headphones", "Studio headphones, earbuds and digital cameras")
    ]

    for name, slug, icon, desc in categories:
        cur.execute("SELECT id FROM categories WHERE slug = %s", (slug,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO categories (name, slug, icon, description) VALUES (%s, %s, %s, %s)",
                (name, slug, icon, desc)
            )

    print("Categories seeded successfully.")

    # Seed Products
    products = [
        # Mobiles
        ("iPhone 17 Pro Max", "Apple", "mobiles", "Flagship Apple smartphone with Titanium finish, A19 Pro chip and Super Retina XDR display.", 189999.00, 199999.00, 5, "https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcR-8fdGiULyggyQPBXr1xPyjM2yKU5orHwZrd0Ks1YRrOqLZeQffU85a-41QF5QVREQdM1_fdbsbU0yYBUg7UBW2ICx0h0l0ArX9R_z_8WD-dawEViQZ6z-SYo", 25, 4.8, True),
        ("iPhone 17 Pro", "Apple", "mobiles", "Pro camera system, ProMotion 120Hz display, and all-day battery life.", 159999.00, 169999.00, 6, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRl1PZuZtK1-RaE7mt1eSvQTZEAg7oZWINlSiARGLDcWg&s", 30, 4.7, True),
        ("iPhone 17", "Apple", "mobiles", "Dual 48MP camera, Dynamic Island, fast USB-C charging, vivid colors.", 82999.00, 89999.00, 8, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRlxLfS1P1w93B80Oa597--J3qOqkxQlgPjPoN4MXEqFQ&s", 40, 4.6, False),
        ("iPhone 16 Pro Max", "Apple", "mobiles", "Grade 5 Titanium, A18 Pro silicon, Action Button and 5x telephoto optical zoom.", 164999.00, 174999.00, 6, "https://rukminim2.flixcart.com/image/480/640/xif0q/mobile/b/f/5/-original-imahggexm5yafhez.jpeg?q=90", 20, 4.9, True),
        ("Samsung Galaxy S24 Ultra", "Samsung", "mobiles", "Galaxy AI, 200MP camera, built-in S-Pen and Snapdragon 8 Gen 3 for Galaxy.", 129999.00, 139999.00, 7, "https://rukminim3.flixcart.com/image/480/480/xif0q/mobile/y/s/g/-resized-original-imahgfmy2zgqvjmy.jpeg?q=90", 35, 4.8, True),
        ("OnePlus 12 5G", "OnePlus", "mobiles", "Hasselblad 4th Gen Camera, 5400mAh battery with 100W SUPERVOOC charging.", 64999.00, 69999.00, 7, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRL0bUhWNjmmZgQcZQRtCUinRYtUbzpCTkQXSmDYI43Lg&s", 45, 4.7, False),

        # Electronics & Laptops
        ("Apple MacBook Pro M5", "Apple", "electronics", "Liquid Retina XDR, incredible power efficiency, 36GB unified memory, 1TB SSD.", 222999.00, 232999.00, 4, "https://media-ik.croma.com/Croma%20Assets/Computers%20Peripherals/Laptop/Images/324219_0_IVTu1Rrpw.png?updatedAt=1782721453142", 15, 4.9, True),
        ("Dell XPS 16 OLED", "Dell", "electronics", "Intel Core Ultra 9, 4K OLED touch display, NVIDIA RTX 4070 graphic prowess.", 195999.00, 215999.00, 9, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR9TtevOGUhUOYb9UojN_RIeGZdH6yoWQnWBn8UUiGaPw&s=10", 18, 4.7, True),
        ("ASUS ROG Zephyrus G16", "ASUS", "electronics", "Ultra-slim gaming laptop, 240Hz OLED ROG Nebula display, AMD Ryzen 9 AI.", 179999.00, 199999.00, 10, "https://m.media-amazon.com/images/I/81X2quaC9eL.jpg", 12, 4.8, False),
        ("Lenovo ThinkPad X1 Carbon", "Lenovo", "electronics", "Ultralight carbon-fiber chassis, enterprise security, 14-inch 2.8K OLED.", 164999.00, 179999.00, 8, "https://rukminim3.flixcart.com/image/480/480/computer/u/t/k/lenovo-thinkpad-ultrabook-original-imadpwkhfpapptsg.jpeg?q=90", 22, 4.6, False),

        # Audio & Cameras
        ("Apple AirPods Max Wireless", "Apple", "audio-cameras", "High-fidelity audio, Active Noise Cancellation with Transparency mode.", 52499.00, 59499.00, 12, "https://rukminim3.flixcart.com/image/480/640/xif0q/headphone/v/g/z/mgyj3hn-a-apple-enriched-transparent-original-imafy8whg2wxcygt.png?q=20", 30, 4.6, True),
        ("Sony WH-1000XM5 ANC Headphones", "Sony", "audio-cameras", "Industry-leading noise canceling with two processors and 8 microphones.", 29990.00, 34990.00, 14, "https://m.media-amazon.com/images/I/61+btxzpfDL._AC_UF1000,1000_QL80_.jpg", 40, 4.8, True),
        ("Sony Alpha 7 IV Full-Frame Camera", "Sony", "audio-cameras", "33MP Exmor R CMOS sensor, 4K 60p recording, realtime eye autofocus.", 90890.00, 99890.00, 9, "https://m.media-amazon.com/images/I/61RrspGZ99L._AC_UF350,350_QL50_.jpg", 10, 4.7, True),
        ("Bose QuietComfort Ultra", "Bose", "audio-cameras", "World-class spatial audio with Bose Immersive Sound and custom acoustic modes.", 35900.00, 39900.00, 10, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSrdmz239S7S3sl6UR9C_tDUnowU5PHNeYDpFuORlLc1Q&s=10", 25, 4.7, False),

        # Fashion & Apparel
        ("Solid Linen Blend Shirt - White", "WROGN", "fashion", "Breathable premium 100% pure linen shirt designed for casual and smart occasions.", 1819.00, 2599.00, 30, "https://wrogn.com/cdn/shop/files/Catlopgue-Image.webp?v=1745414571&width=533", 60, 4.6, True),
        ("U.S. Polo Assn. Casual Shirt", "U.S. Polo Assn.", "fashion", "Signature pony embroidery, tailored slim fit, crafted from combed cotton.", 1439.00, 3599.00, 60, "https://encrypted-tbn1.gstatic.com/shopping?q=tbn:ANd9GcTEmihWX26EZ7HBOTr1vnwDDyt6ofgcvm2fV3OD5bKyiPMhtFMPh8nLXOmYHoOCvB9uVzTbMLoJ310goW9G-uLTw41aA0q2ES7MMa7oruVEJkHSXaGnqxbPxvborqeMrARO88nU4yabOA&usqp=CAc", 80, 4.6, True),
        ("Cotton Oversized Graphic T-Shirt", "Roadster", "fashion", "Heavyweight pure bio-washed cotton, dropped shoulder comfortable cut.", 799.00, 1499.00, 47, "https://rukminim3.flixcart.com/image/480/640/xif0q/t-shirt/j/k/o/l-repl5001-coffee-yonge-original-imahm9yayn4zaxyt.jpeg?q=90", 100, 4.3, False),
        ("Slim Fit Stretch Chino Trousers", "Peter England", "fashion", "Smart casual stretch twill chinos engineered for maximum flex and durability.", 1299.00, 2299.00, 43, "https://pantproject.com/cdn/shop/files/DSC3195_-_Copy.jpg?v=1755540740&width=1200", 75, 4.4, False),

        # Watches
        ("Apple Watch Ultra 2 GPS + Cellular", "Apple", "watches", "49mm corrosion-resistant titanium case, precision dual-frequency GPS, 3000 nits display.", 89900.00, 94900.00, 5, "https://rukmini1.flixcart.com/image/1500/1500/xif0q/smartwatch/e/a/y/-original-imahftggye6eyhzw.jpeg?q=70", 25, 4.9, True),
        ("Samsung Galaxy Watch 6 Classic", "Samsung", "watches", "Rotating physical bezel, sapphire crystal screen, ECG and health tracking.", 33999.00, 43999.00, 23, "https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcQpKgKdKF9sYRNQxUxPb6IB-AJ4bETTyYt0p3EyCDrrXDZZUqiJ1rKPJqx9iN5ISFflbkNeFTcrto6nK3C4zrfCBYS_1BcKuyNHH93EKzWr8MwODJKXKO2zP3ocpQqOs6mpEFH283A&usqp=CAc", 30, 4.5, True),
        ("Fossil Grant Chronograph Leather Watch", "Fossil", "watches", "Classic Roman numerals, dark blue dial and genuine brown leather strap.", 10495.00, 13995.00, 25, "https://fossil.scene7.com/is/image/FossilPartners/FS4835_main?$sfcc_fossil_hi-res$", 40, 4.6, False),

        # Bags & Sunglasses
        ("Carissa Blue Sling Bag for Women", "Carissa", "bags-sunglasses", "Faux leather premium textured finish with dual compartments and golden chain strap.", 2499.00, 3499.00, 28, "https://rukminim3.flixcart.com/image/480/640/xif0q/sling-bag/7/d/a/ling-bag-for-women-and-girls-ladies-purse-woman-handbag-1-20-resized-original-imahbfh4wky23v3p.jpeg?q=90", 50, 4.6, True),
        ("Polarized Black Aviator Sunglasses", "Ray-Ban Style", "bags-sunglasses", "100% UV400 protection, lightweight alloy frame, glare reduction coating.", 599.00, 1299.00, 54, "https://rukminim3.flixcart.com/image/316/420/xif0q/sunglass/f/r/l/medium-full-black-kamm-lushora-resized-original-imahbz4yzxtw7jwt.jpeg?q=80&crop=false", 90, 4.2, False),
        ("American Tourister 32L Backpack", "American Tourister", "bags-sunglasses", "Ergonomic shoulder straps, water-resistant fabric, 3 compartments with laptop sleeve.", 1699.00, 3200.00, 47, "https://rukmini1.flixcart.com/image/1500/1500/xif0q/backpack/i/z/l/-original-imahfskb9n9zupfk.jpeg?q=70", 60, 4.5, True),

        # TV & Appliances
        ("Sony BRAVIA XR 55-inch 4K OLED TV", "Sony", "tv-appliances", "Cognitive Processor XR, Acoustic Surface Audio+, Dolby Vision Atmos.", 124990.00, 149900.00, 17, "https://m.media-amazon.com/images/I/81p-QMgwnLL._AC_UF1000,1000_QL80_.jpg", 15, 4.9, True),
        ("LG 8kg Front Load Smart Washing Machine", "LG", "tv-appliances", "AI Direct Drive motor, steam allergy care, TurboWash 360 in 39 mins.", 38990.00, 48990.00, 20, "https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcQ8PpfVcPqOS4UOLM7rRBruqfcEWIitxr9QCJpUXNLif5uEZ2Bx2g-0EhhKMepYfdNQrZQfPOodvnWtIe5SAkLN_Glo9ixreWAah-E13HWGcqnSBeARn7jE89QG6XQ25lcw4DrThn3d&usqp=CAc", 20, 4.7, True),
        ("Samsung 653L Side-by-Side Refrigerator", "Samsung", "tv-appliances", "Convertible 5-in-1, Twin Cooling Plus, Digital Inverter with 20-year warranty.", 82990.00, 99990.00, 17, "https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcT2dHFAZf83jWCOm6Ip0uBw5Mb91mpP9Yjj7R4Qnol-2hXb4DyGtM8dnxBe_hrlde6Gy9uSw-amG78zbBbuOA3Vt2nOE5dI4EwBj6quzSRZ0yBFYaT8O9DjD0Nsr9jyXhv42Wn1iXg&usqp=CAc", 12, 4.8, False),

        # Furniture & Decor
        ("Modern Velvet 3-Seater Sofa", "Wakefit", "furniture", "High-density foam, solid Sheesham wood frame, water-repellent velvet finish.", 24999.00, 36999.00, 32, "https://cdn.swadeshonline.com/v2/patient-paper-41f385/swad-p/wrkr/products/pictures/item/free/original/-nQMsU2e30-Vaniza_3Seater_Pink_0.jpg", 15, 4.6, True),
        ("Ergonomic Mesh Office Chair", "Green Soul", "furniture", "Breathable mesh back, multi-lock synchro tilt, 2D adjustable armrests.", 8499.00, 14990.00, 43, "https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcRVbhnvt8dwU2NpqyTyYcI7wP8dU2cpAVf63JdNhKS1_lSYH8_0lMioqmh1rx23IMMfxaObk_dxxjy1Gafc1nPA4-k9Q9sWyAE0CHHjtyhcluT8vBId0vborxln6vC6VMjvfHcGmWg&usqp=CAc", 40, 4.7, False),

        # Grocery & Essentials
        ("Fortune Sunlite Refined Sunflower Oil 5L", "Fortune", "grocery", "Enriched with vitamins A & D, heart-friendly cooking oil.", 675.00, 750.00, 10, "https://rukmini1.flixcart.com/image/1500/1500/xif0q/edible-oil/y/8/6/-enriched-transparent-original-imahbwhr46uerghr.png?q=70", 150, 4.5, False),
        ("Daawat Rozana Gold Basmati Rice 5kg", "Daawat", "grocery", "Aged long grain aromatic rice suitable for daily meal preparation.", 425.00, 520.00, 18, "https://aapkabazar.co/_next/image?url=https%3A%2F%2Fimage.aapkabazar.co%2Fproduct%2F7305%2F1671620500550.png%3Ftype%3Dwebp%26width%3D600&w=3840&q=75", 200, 4.6, False),
    ]

    for p in products:
        name, brand, cat_slug, desc, price, orig_price, disc, img, stock, rating, feat = p
        cur.execute("SELECT id FROM products WHERE name = %s", (name,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO products 
                (name, brand, category_slug, description, price, original_price, discount_percent, image_url, stock, rating, is_featured, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (name, brand, cat_slug, desc, price, orig_price, disc, img, stock, rating, feat))

    print(f"Products seeded successfully! Total products: {len(products)}.")
    cur.close()
    conn.close()
    print("Database initialization and migration completed successfully.")

if __name__ == "__main__":
    run_seed()
