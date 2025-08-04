"""DNA generators for creating synthetic driver and rider profiles."""

import math
import random

from agents.dna import DriverDNA, RiderDNA, ShiftPreference, haversine_distance

FIRST_NAMES = [
    "João",
    "Maria",
    "José",
    "Ana",
    "Carlos",
    "Patricia",
    "Pedro",
    "Mariana",
    "Lucas",
    "Juliana",
    "Paulo",
    "Fernanda",
    "Rafael",
    "Camila",
    "Marcos",
    "Amanda",
    "Bruno",
    "Gabriela",
    "Felipe",
    "Isabella",
    "Rodrigo",
    "Larissa",
    "Diego",
    "Beatriz",
    "Thiago",
    "Leticia",
    "Gustavo",
    "Raquel",
    "Leonardo",
    "Carla",
    "André",
    "Vanessa",
    "Daniel",
    "Priscila",
    "Fernando",
    "Renata",
    "Henrique",
    "Natália",
    "Vinicius",
    "Mônica",
    "Eduardo",
    "Cristina",
    "Ricardo",
    "Claudia",
    "Marcelo",
    "Sandra",
    "Alexandre",
    "Tatiana",
    "Roberto",
    "Adriana",
]

LAST_NAMES = [
    "Silva",
    "Santos",
    "Oliveira",
    "Souza",
    "Pereira",
    "Costa",
    "Rodrigues",
    "Almeida",
    "Nascimento",
    "Lima",
    "Araújo",
    "Fernandes",
    "Carvalho",
    "Gomes",
    "Martins",
    "Rocha",
    "Ribeiro",
    "Alves",
    "Monteiro",
    "Mendes",
    "Barros",
    "Freitas",
    "Barbosa",
    "Pinto",
    "Moreira",
    "Cavalcanti",
    "Dias",
    "Castro",
    "Campos",
    "Cardoso",
    "Silva",
    "Reis",
    "Teixeira",
    "Santos",
    "Duarte",
    "Machado",
    "Nunes",
    "Lopes",
    "Soares",
    "Vieira",
    "Melo",
    "Correia",
    "Garcia",
    "Ferreira",
    "Azevedo",
    "Ramos",
    "Moura",
    "Xavier",
    "Aguiar",
    "Borges",
]

VEHICLE_DATA = {
    "Volkswagen": ["Gol", "Polo", "Voyage", "Fox"],
    "Fiat": ["Uno", "Palio", "Argo", "Mobi"],
    "Chevrolet": ["Onix", "Prisma", "Cruze"],
    "Toyota": ["Corolla", "Etios"],
    "Honda": ["Civic", "Fit"],
    "Hyundai": ["HB20", "Creta"],
}

EMAIL_DOMAINS = ["gmail.com", "hotmail.com", "yahoo.com.br"]

SAO_PAULO_LAT_MIN = -24.0
SAO_PAULO_LAT_MAX = -23.0
SAO_PAULO_LON_MIN = -47.0
SAO_PAULO_LON_MAX = -46.0

DIGITAL_WALLETS = ["Pix", "PicPay", "Mercado Pago", "Nubank", "PayPal"]

TIME_AFFINITY_PATTERNS = [
    [7, 8, 9],  # Morning commute
    [17, 18, 19],  # Evening return
    [10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23],  # Leisure
]


def _clean_name_for_email(name: str) -> str:
    """Remove accents from name for email address."""
    return (
        name.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ã", "a")
        .replace("õ", "o")
        .replace("ç", "c")
        .replace("â", "a")
        .replace("ê", "e")
        .replace("ô", "o")
    )


def generate_license_plate() -> str:
    """Generate Brazilian license plate (old or new Mercosul format)."""
    if random.choice([True, False]):
        # Old format: ABC-1234
        letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
        numbers = "".join(random.choices("0123456789", k=4))
        return f"{letters}-{numbers}"
    else:
        # New Mercosul: ABC1D23
        letters1 = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
        digit1 = random.choice("0123456789")
        letter2 = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        digits2 = "".join(random.choices("0123456789", k=2))
        return f"{letters1}{digit1}{letter2}{digits2}"


def generate_phone() -> str:
    """Generate Brazilian mobile phone number (11 digits, starting with 11 and 9)."""
    return "11" + "9" + "".join(random.choices("0123456789", k=8))


def generate_driver_dna() -> DriverDNA:
    """Generate random driver DNA with realistic Brazilian driver profile."""

    # Behavioral parameters (immutable)
    acceptance_rate = random.uniform(0.7, 0.95)
    cancellation_tendency = random.uniform(0.01, 0.1)

    # Service quality skewed toward higher values
    service_quality = max(0.6, min(1.0, random.gauss(0.85, 0.1)))

    # Response time with normal distribution
    response_time = max(3.0, min(12.0, random.gauss(6.0, 2.0)))

    min_rider_rating = random.uniform(3.0, 4.5)

    # Home location
    home_lat = random.uniform(SAO_PAULO_LAT_MIN, SAO_PAULO_LAT_MAX)
    home_lon = random.uniform(SAO_PAULO_LON_MIN, SAO_PAULO_LON_MAX)
    home_location = (home_lat, home_lon)

    # Preferred zones (placeholder for now)
    num_zones = random.randint(1, 3)
    preferred_zones = [f"zone_{i}" for i in range(num_zones)]

    # Shift preference with weighted distribution
    shift_weights = {
        ShiftPreference.MORNING: 0.15,
        ShiftPreference.AFTERNOON: 0.25,
        ShiftPreference.EVENING: 0.25,
        ShiftPreference.NIGHT: 0.15,
        ShiftPreference.FLEXIBLE: 0.20,
    }
    shift_preference = random.choices(
        list(shift_weights.keys()), weights=list(shift_weights.values()), k=1
    )[0]

    avg_hours_per_day = random.randint(4, 12)
    avg_days_per_week = random.randint(3, 7)

    # Vehicle info
    vehicle_make = random.choice(list(VEHICLE_DATA.keys()))
    vehicle_model = random.choice(VEHICLE_DATA[vehicle_make])
    vehicle_year = random.randint(2015, 2025)
    license_plate = generate_license_plate()

    # Personal info
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)

    # Email
    first_clean = _clean_name_for_email(first_name)
    last_clean = _clean_name_for_email(last_name)
    domain = random.choice(EMAIL_DOMAINS)
    random_suffix = random.randint(1, 9999)
    email = f"{first_clean}.{last_clean}{random_suffix}@{domain}"

    phone = generate_phone()

    return DriverDNA(
        acceptance_rate=acceptance_rate,
        cancellation_tendency=cancellation_tendency,
        service_quality=service_quality,
        response_time=response_time,
        min_rider_rating=min_rider_rating,
        home_location=home_location,
        preferred_zones=preferred_zones,
        shift_preference=shift_preference,
        avg_hours_per_day=avg_hours_per_day,
        avg_days_per_week=avg_days_per_week,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        license_plate=license_plate,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )


def _generate_destination_near(
    home_lat: float, home_lon: float, min_km: float = 0.8, max_km: float = 20.0
) -> tuple[float, float] | None:
    """Generate random coordinates within min_km-max_km of home, within Sao Paulo bounds."""
    # Generate random bearing and distance
    bearing = random.uniform(0, 2 * math.pi)
    distance = random.uniform(min_km, max_km)

    # Convert to lat/lon offset
    # 1 degree lat ≈ 111 km, 1 degree lon ≈ 111 * cos(lat) km
    delta_lat = (distance * math.cos(bearing)) / 111.0
    delta_lon = (distance * math.sin(bearing)) / (111.0 * math.cos(math.radians(home_lat)))

    new_lat = home_lat + delta_lat
    new_lon = home_lon + delta_lon

    # Check bounds
    if not (SAO_PAULO_LAT_MIN <= new_lat <= SAO_PAULO_LAT_MAX):
        return None
    if not (SAO_PAULO_LON_MIN <= new_lon <= SAO_PAULO_LON_MAX):
        return None

    # Verify actual distance is within limits
    actual_distance = haversine_distance(home_lat, home_lon, new_lat, new_lon)
    if actual_distance < min_km or actual_distance > max_km:
        return None

    return (new_lat, new_lon)


def _generate_frequent_destinations(
    home_lat: float, home_lon: float, count: int, min_km: float = 0.8, max_km: float = 20.0
) -> list[dict]:
    """Generate frequent destinations within min_km-max_km of home."""
    destinations: list[dict] = []

    for _ in range(count):
        coords = None
        for _ in range(10):  # Max 10 retries
            coords = _generate_destination_near(home_lat, home_lon, min_km, max_km)
            if coords:
                break

        if not coords:
            # Fallback: generate at minimum distance in random direction
            bearing = random.uniform(0, 2 * math.pi)
            delta_lat = (min_km * math.cos(bearing)) / 111.0
            delta_lon = (min_km * math.sin(bearing)) / (111.0 * math.cos(math.radians(home_lat)))
            coords = (home_lat + delta_lat, home_lon + delta_lon)

        # Random weight (will be normalized later)
        weight = random.uniform(0.1, 0.5)

        # Optional time affinity (50% chance)
        time_affinity = None
        if random.random() < 0.5:
            time_affinity = random.choice(TIME_AFFINITY_PATTERNS)

        destinations.append(
            {
                "coordinates": coords,
                "weight": weight,
                "time_affinity": time_affinity,
            }
        )

    # Normalize weights
    total_weight: float = sum(float(d["weight"]) for d in destinations)
    for d in destinations:
        d["weight"] = float(d["weight"]) / total_weight

    return destinations


def generate_rider_dna() -> RiderDNA:
    """Generate random rider DNA with realistic Brazilian rider profile."""

    # Home location
    home_lat = random.uniform(SAO_PAULO_LAT_MIN, SAO_PAULO_LAT_MAX)
    home_lon = random.uniform(SAO_PAULO_LON_MIN, SAO_PAULO_LON_MAX)
    home_location = (home_lat, home_lon)

    # Behavioral parameters (immutable)
    # Behavior factor skewed toward higher values (most riders are well-behaved)
    behavior_factor = max(0.5, min(1.0, random.gauss(0.85, 0.15)))

    patience_threshold = random.randint(120, 300)
    max_surge_multiplier = random.uniform(1.5, 3.0)
    avg_rides_per_week = random.randint(1, 15)

    # Generate 2-5 frequent destinations
    num_destinations = random.randint(2, 5)
    frequent_destinations = _generate_frequent_destinations(home_lat, home_lon, num_destinations)

    # Personal info
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)

    # Email
    first_clean = _clean_name_for_email(first_name)
    last_clean = _clean_name_for_email(last_name)
    domain = random.choice(EMAIL_DOMAINS)
    random_suffix = random.randint(1, 9999)
    email = f"{first_clean}.{last_clean}{random_suffix}@{domain}"

    phone = generate_phone()

    # Payment method (70% credit card, 30% digital wallet)
    if random.random() < 0.7:
        payment_method_type = "credit_card"
        payment_method_masked = "****" + "".join(random.choices("0123456789", k=4))
    else:
        payment_method_type = "digital_wallet"
        payment_method_masked = random.choice(DIGITAL_WALLETS)

    return RiderDNA(
        behavior_factor=behavior_factor,
        patience_threshold=patience_threshold,
        max_surge_multiplier=max_surge_multiplier,
        avg_rides_per_week=avg_rides_per_week,
        frequent_destinations=frequent_destinations,
        home_location=home_location,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        payment_method_type=payment_method_type,
        payment_method_masked=payment_method_masked,
    )
