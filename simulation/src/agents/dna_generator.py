"""Driver DNA generator for creating synthetic driver profiles."""

import random

from agents.dna import DriverDNA, ShiftPreference

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

    # Email (lowercase, remove accents for simplicity)
    first_clean = (
        first_name.lower()
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
    last_clean = (
        last_name.lower()
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
    domain = random.choice(EMAIL_DOMAINS)
    # Add random number to reduce collision probability
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
