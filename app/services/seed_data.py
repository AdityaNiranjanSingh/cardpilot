from __future__ import annotations

from datetime import date
from sqlalchemy.orm import Session

from ..models import Merchant
from ..utils import canonical_category, normalize_text

# Professional seed merchants for the local CardPilot database. These mappings are
# meant to make dropdowns, merchant matching, and early user testing feel realistic.
# Verify MCCs and bank-specific categorisation before using these mappings for a
# production eligibility decision.
MERCHANT_GROUPS: dict[str, list[str]] = {
    "online shopping": [
        "Amazon", "Flipkart", "Myntra", "Ajio", "Nykaa", "Tata Cliq", "Meesho", "Snapdeal", "ShopClues", "FirstCry",
        "Pepperfry", "Urban Ladder", "IKEA India", "Croma Online", "Reliance Digital Online", "Samsung Shop", "Apple Store India", "Mi Store", "OnePlus Store", "Vijay Sales Online",
        "JioMart", "BigBasket", "Blinkit", "Zepto", "Nature's Basket", "Lenskart", "Titan Eyeplus", "CaratLane", "Bluestone", "Pharmeasy",
        "Netmeds", "Apollo Pharmacy Online", "HealthKart", "Decathlon Online", "Sportsjam", "Hamleys India", "Toys R Us India", "Ferns N Petals", "IGP Gifts", "Archies Online",
        "Purplle", "Sugar Cosmetics", "Mamaearth", "Boat Lifestyle", "Noise Store", "Fire-Boltt", "Wakefit", "SleepyCat", "The Souled Store", "Bewakoof",
    ],
    "food delivery": [
        "Swiggy", "Zomato", "EatSure", "Domino's Online", "Pizza Hut Online", "KFC Online", "McDonald's App", "Burger King App", "Subway Online", "Haldiram's Online",
        "Biryani By Kilo", "Behrouz Biryani", "Faasos", "Oven Story", "LunchBox", "Box8", "FreshMenu", "Good Flippin Burgers", "Chaayos App", "Starbucks App",
        "Third Wave Coffee", "Blue Tokai", "Cafe Coffee Day App", "Theobroma", "NIC Ice Creams", "Naturals Ice Cream", "Baskin Robbins", "EatClub", "Rebel Foods", "Barbeque Nation Delivery",
    ],
    "dining": [
        "EazyDiner", "Dineout", "Zomato Dining", "Swiggy Dineout", "Barbeque Nation", "Mainland China", "Social", "Hard Rock Cafe", "Cafe Delhi Heights", "Smoke House Deli",
        "PizzaExpress", "Chili's", "Taco Bell", "Starbucks", "Third Wave Coffee Roasters", "Blue Tokai Coffee", "Chaayos", "Bikanervala", "Haldiram's", "Keventers",
        "Burger Singh", "Wow Momo", "Absolute Barbecues", "Punjab Grill", "Biryani Blues", "The Beer Cafe", "Farzi Cafe", "Nando's", "McDonald's", "KFC",
    ],
    "grocery": [
        "DMart", "DMart Ready", "Reliance Smart", "Reliance Fresh", "More Retail", "Spencer's", "Big Bazaar", "Star Bazaar", "Nature's Basket", "Foodhall",
        "BigBasket", "Blinkit", "Zepto", "JioMart Grocery", "Grofers", "Easyday", "Metro Cash and Carry", "Spar Hypermarket", "Ratnadeep", "Nilgiris",
        "Modern Bazaar", "24Seven", "Needs Supermarket", "FreshToHome", "Licious", "TenderCuts", "Country Delight", "Milkbasket", "Supr Daily", "Amazon Fresh",
    ],
    "travel": [
        "MakeMyTrip", "Goibibo", "Cleartrip", "Yatra", "EaseMyTrip", "Ixigo", "Booking.com", "Agoda", "Expedia", "Skyscanner",
        "Air India", "IndiGo", "Vistara", "Akasa Air", "SpiceJet", "AirAsia India", "Alliance Air", "Emirates", "Qatar Airways", "Singapore Airlines",
        "IRCTC", "RedBus", "AbhiBus", "KSRTC", "MSRTC", "Uber Intercity", "Ola Outstation", "Zoomcar", "Revv", "Savaari",
        "Taj Hotels", "IHCL", "Marriott", "Hyatt", "Hilton", "ITC Hotels", "Lemon Tree Hotels", "OYO", "Treebo", "FabHotels",
    ],
    "fuel": [
        "Indian Oil", "IOCL", "Bharat Petroleum", "BPCL", "Hindustan Petroleum", "HPCL", "Shell", "Reliance Petroleum", "Nayara Energy", "Essar Oil",
        "Jio-bp", "IndianOil XTRAREWARDS", "HP Pay", "BPCL SmartDrive", "Shell SmartPay", "Petrol Pump", "Fuel Station", "Diesel Station", "CNG Station", "EV Charging Station",
    ],
    "mobility": [
        "Uber", "Ola", "Rapido", "Namma Yatri", "BluSmart", "Quick Ride", "Zoomcar", "Revv", "Drivezy", "Bounce",
        "Yulu", "Vogo", "Meru Cabs", "Savaari", "InDrive", "RedBus", "AbhiBus", "IRCTC", "Metro Recharge", "FASTag Recharge",
    ],
    "utilities": [
        "Electricity Bill", "Tata Power", "BSES Rajdhani", "BSES Yamuna", "Adani Electricity", "MSEB", "BESCOM", "TANGEDCO", "Torrent Power", "CESC",
        "Gas Bill", "Mahanagar Gas", "Indraprastha Gas", "Gujarat Gas", "Adani Gas", "Water Bill", "Municipal Bill", "Property Tax", "Broadband Bill", "DTH Recharge",
        "Airtel Bill Pay", "Jio Bill Pay", "Vi Bill Pay", "ACT Fibernet", "Hathway", "Tata Play Recharge", "Dish TV Recharge", "Sun Direct Recharge", "NoBroker Pay", "Housing Society Bill",
    ],
    "telecom": [
        "Airtel", "Jio", "Vi", "BSNL", "MTNL", "Airtel Thanks", "MyJio", "Vodafone Idea", "JioFiber", "Airtel Xstream",
        "ACT Fibernet", "Hathway Broadband", "Tata Play Fiber", "Excitel", "You Broadband", "Spectra", "Tikona", "RailWire", "Den Broadband", "GTPL Broadband",
    ],
    "entertainment": [
        "BookMyShow", "PVR Cinemas", "INOX", "Cinepolis", "Miraj Cinemas", "Paytm Movies", "Netflix", "Amazon Prime Video", "Disney Hotstar", "SonyLIV",
        "Zee5", "JioCinema", "Spotify", "YouTube Premium", "Apple Music", "Gaana", "Wynk Music", "Audible", "Kindle", "Steam",
        "PlayStation Store", "Xbox Store", "Google Play", "Apple App Store", "Lollapalooza India", "Insider.in", "District by Zomato", "SkillBox", "Fever Up", "MUBI",
    ],
    "fashion": [
        "Lifestyle", "Shoppers Stop", "Westside", "Pantaloons", "Max Fashion", "Zudio", "H&M", "Zara", "Uniqlo", "Marks and Spencer",
        "Levi's", "Nike", "Adidas", "Puma", "Reebok", "Skechers", "Metro Shoes", "Bata", "Woodland", "Allen Solly",
        "Van Heusen", "Peter England", "Louis Philippe", "Raymond", "Manyavar", "Fabindia", "Biba", "W", "Global Desi", "Mochi",
    ],
    "electronics": [
        "Croma", "Reliance Digital", "Vijay Sales", "Poorvika", "Sangeetha Mobiles", "Lot Mobile", "Bajaj Electronics", "Apple Store", "iPlanet", "Samsung SmartCafe",
        "Mi Home", "OnePlus Experience Store", "Dell Store", "HP World", "Lenovo Exclusive Store", "Asus Store", "Sony Center", "LG Best Shop", "Bosch Brand Store", "Havells Galaxy",
    ],
    "healthcare": [
        "Apollo Pharmacy", "MedPlus", "Wellness Forever", "PharmEasy", "Netmeds", "Tata 1mg", "Practo", "Apollo 24/7", "Healthians", "Thyrocare",
        "Dr Lal PathLabs", "Metropolis Healthcare", "SRL Diagnostics", "Max Healthcare", "Fortis Healthcare", "Apollo Hospitals", "Manipal Hospitals", "Narayana Health", "Aster Hospitals", "Cloudnine Hospitals",
    ],
    "education": [
        "Byju's", "Unacademy", "Vedantu", "Physics Wallah", "UpGrad", "Simplilearn", "Coursera", "Udemy", "edX", "Great Learning",
        "WhiteHat Jr", "Cuemath", "Toppr", "Khan Academy Donation", "School Fees", "College Fees", "University Fees", "Exam Fees", "Coaching Institute", "Book Store",
    ],
    "insurance": [
        "LIC", "HDFC Life", "ICICI Prudential Life", "SBI Life", "Max Life", "Tata AIA", "Bajaj Allianz", "Star Health", "Care Health Insurance", "Niva Bupa",
        "HDFC ERGO", "ICICI Lombard", "Tata AIG", "Reliance General", "Policybazaar", "Acko", "Digit Insurance", "RenewBuy", "Coverfox", "Aditya Birla Health",
    ],
    "financial services": [
        "CRED", "Paytm", "PhonePe", "Google Pay", "Amazon Pay", "Mobikwik", "Freecharge", "BharatPe", "Razorpay", "PayU",
        "BillDesk", "Cashfree", "Pine Labs", "Instamojo", "Niyo", "Fi Money", "Jupiter Money", "Groww", "Zerodha", "Upstox",
        "Angel One", "INDmoney", "Kuvera", "ET Money", "Smallcase", "CoinDCX", "WazirX", "KreditBee", "MoneyTap", "CASHe",
    ],
    "rent": [
        "NoBroker Rent Pay", "RedGirraffe", "Housing.com Rent", "Magicbricks Rent", "CRED RentPay", "Paytm Rent", "PhonePe Rent", "Freecharge Rent", "Rentomojo", "Furlenco",
    ],
    "jewellery": [
        "Tanishq", "Malabar Gold", "Kalyan Jewellers", "Joyalukkas", "PC Jeweller", "CaratLane", "Bluestone", "Senco Gold", "PNG Jewellers", "TBZ",
    ],
    "department stores": [
        "Reliance Retail", "Trends", "Central", "Brand Factory", "Vishal Mega Mart", "D Mart", "Spencer's Retail", "Shoppers Stop", "Lifestyle Stores", "More Megastore",
    ],
    "home improvement": [
        "Asian Paints", "Berger Paints", "Home Centre", "HomeTown", "Pepperfry Studio", "Urban Ladder Store", "IKEA", "Livspace", "HomeLane", "Wakefit Store",
        "Durian", "Godrej Interio", "Nilkamal", "Cera", "Kajaria", "Somany", "Jaquar", "Hindware", "Urban Company", "Housejoy",
    ],
    "beauty wellness": [
        "Lakme Salon", "Naturals Salon", "Looks Salon", "Enrich Salon", "VLCC", "Urban Company Salon", "Nykaa Luxe", "Sephora", "Health and Glow", "The Body Shop",
        "Cult Fit", "Gold's Gym", "Anytime Fitness", "Fitternity", "Curefit", "Decathlon", "Apollo Clinic", "Kaya Skin Clinic", "Tattva Spa", "O2 Spa",
    ],
    "government taxes": [
        "Income Tax", "GST Payment", "Passport Seva", "RTO Payment", "Municipal Tax", "Property Tax", "Traffic Challan", "EPFO", "NPS Contribution", "BharatKosh",
    ],
}

MCC_BY_CATEGORY = {
    "online shopping": "5399",
    "food delivery": "5814",
    "dining": "5812",
    "grocery": "5411",
    "travel": "4722",
    "fuel": "5541",
    "mobility": "4121",
    "utilities": "4900",
    "telecom": "4814",
    "entertainment": "7832",
    "fashion": "5651",
    "electronics": "5732",
    "healthcare": "5912",
    "education": "8299",
    "insurance": "6300",
    "financial services": "6012",
    "rent": "6513",
    "jewellery": "5944",
    "department stores": "5311",
    "home improvement": "5200",
    "beauty wellness": "7298",
    "government taxes": "9399",
}


def extra_merchant_rows() -> list[dict]:
    rows: list[dict] = []
    idx = 1
    for category, names in MERCHANT_GROUPS.items():
        for name in names:
            rows.append(
                {
                    "merchant_id": f"MX{idx:04d}",
                    "raw_merchant_pattern": name,
                    "normalized_merchant": name,
                    "mcc": MCC_BY_CATEGORY.get(category),
                    "category": category,
                    "subcategory": canonical_category(category),
                    "mapping_confidence": "Medium",
                    "last_verified": date.today(),
                    "source_url": None,
                    "source_notes": "Professional seed mapping for CardPilot MVP. Verify MCC and issuer treatment before production decisions.",
                    "mvp_next_action": "Verify issuer MCC/category treatment after real statement testing.",
                }
            )
            idx += 1
    return rows


def ensure_professional_seed_data(db: Session) -> dict:
    existing_ids = {row[0] for row in db.query(Merchant.merchant_id).all()}
    existing_norms = {normalize_text(row[0]) for row in db.query(Merchant.normalized_merchant).all() if row[0]}
    inserted = 0
    skipped = 0

    for row in extra_merchant_rows():
        norm = normalize_text(row["normalized_merchant"])
        if row["merchant_id"] in existing_ids or norm in existing_norms:
            skipped += 1
            continue
        db.add(Merchant(**row))
        existing_ids.add(row["merchant_id"])
        existing_norms.add(norm)
        inserted += 1

    if inserted:
        db.commit()
    return {"inserted_merchants": inserted, "skipped_merchants": skipped}
