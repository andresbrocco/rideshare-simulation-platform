"""Custom Faker providers for Brazilian rideshare data."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from faker import Faker
from faker.providers import BaseProvider

if TYPE_CHECKING:
    from faker.proxy import Faker as FakerType


class VehicleDict(TypedDict):
    """Type for vehicle data dictionary."""

    make: str
    model: str
    year: int


class PaymentMethodDict(TypedDict):
    """Type for payment method dictionary."""

    type: str
    masked: str


class BrazilianLicensePlateProvider(BaseProvider):
    """Custom provider for Brazilian license plates."""

    def license_plate_br(self) -> str:
        """Generate Brazilian license plate (old ABC-1234 or Mercosul ABC1D23 format)."""
        if self.random_element([True, False]):
            # Old format: ABC-1234
            letters = "".join(
                self.random_elements(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", length=3, unique=False
                )
            )
            numbers = "".join(
                self.random_elements("0123456789", length=4, unique=False)
            )
            return f"{letters}-{numbers}"
        else:
            # Mercosul format: ABC1D23
            letters1 = "".join(
                self.random_elements(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", length=3, unique=False
                )
            )
            digit1 = self.random_element("0123456789")
            letter2 = self.random_element("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            digits2 = "".join(
                self.random_elements("0123456789", length=2, unique=False)
            )
            return f"{letters1}{digit1}{letter2}{digits2}"


class BrazilianPhoneProvider(BaseProvider):
    """Custom provider for Brazilian mobile phones (Sao Paulo)."""

    def phone_br_mobile_sp(self) -> str:
        """Generate Sao Paulo mobile number: 119XXXXXXXX (11 digits)."""
        digits = "".join(self.random_elements("0123456789", length=8, unique=False))
        return f"119{digits}"


class BrazilianVehicleProvider(BaseProvider):
    """Custom provider for Brazilian rideshare vehicles."""

    VEHICLE_DATA: dict[str, list[str]] = {
        "Volkswagen": ["Gol", "Polo", "Voyage", "Fox"],
        "Fiat": ["Uno", "Palio", "Argo", "Mobi"],
        "Chevrolet": ["Onix", "Prisma", "Cruze"],
        "Toyota": ["Corolla", "Etios"],
        "Honda": ["Civic", "Fit"],
        "Hyundai": ["HB20", "Creta"],
    }

    def vehicle_make_br(self) -> str:
        """Generate a Brazilian car make common in rideshare."""
        return self.random_element(list(self.VEHICLE_DATA.keys()))

    def vehicle_model_br(self, make: str | None = None) -> str:
        """Generate a Brazilian car model for the given make.

        Args:
            make: Car make. If None, picks a random make first.
        """
        if make is None:
            make = self.vehicle_make_br()
        models = self.VEHICLE_DATA.get(make, ["Gol"])  # Fallback to Gol
        return self.random_element(models)

    def vehicle_year_br(self, min_year: int = 2015, max_year: int = 2025) -> int:
        """Generate a vehicle year within the allowed range."""
        return self.random_int(min=min_year, max=max_year)

    def vehicle_br(self) -> VehicleDict:
        """Generate complete vehicle info (make, model, year)."""
        make = self.vehicle_make_br()
        model = self.vehicle_model_br(make)
        year = self.vehicle_year_br()
        return {"make": make, "model": model, "year": year}


class BrazilianPaymentProvider(BaseProvider):
    """Custom provider for Brazilian payment methods."""

    DIGITAL_WALLETS: list[str] = ["Pix", "PicPay", "Mercado Pago", "Nubank", "PayPal"]

    def digital_wallet_br(self) -> str:
        """Generate a Brazilian digital wallet name."""
        return self.random_element(self.DIGITAL_WALLETS)

    def credit_card_masked(self) -> str:
        """Generate a masked credit card number (****XXXX)."""
        last_four = "".join(self.random_elements("0123456789", length=4, unique=False))
        return f"****{last_four}"

    def payment_method_br(
        self, credit_card_probability: float = 0.7
    ) -> PaymentMethodDict:
        """Generate a payment method (credit card or digital wallet).

        Args:
            credit_card_probability: Probability of credit card vs digital wallet.
        """
        if self.generator.random.random() < credit_card_probability:
            return {"type": "credit_card", "masked": self.credit_card_masked()}
        else:
            return {"type": "digital_wallet", "masked": self.digital_wallet_br()}


def create_faker_instance(seed: int | None = None) -> FakerType:
    """Create a configured Faker instance with Brazilian locale and custom providers.

    Args:
        seed: Optional seed for reproducible random data.

    Returns:
        Configured Faker instance with pt_BR locale and all custom providers.
    """
    fake: FakerType = Faker("pt_BR")

    if seed is not None:
        Faker.seed(seed)
        fake.seed_instance(seed)

    fake.add_provider(BrazilianLicensePlateProvider)
    fake.add_provider(BrazilianPhoneProvider)
    fake.add_provider(BrazilianVehicleProvider)
    fake.add_provider(BrazilianPaymentProvider)

    return fake
