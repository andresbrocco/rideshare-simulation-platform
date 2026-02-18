"""Tests for profile_mutations module-level Faker instance caching."""

import random
from unittest.mock import patch

import pytest

import agents.profile_mutations as pm_module
from agents.profile_mutations import mutate_driver_profile, mutate_rider_profile
from tests.factories import DNAFactory


@pytest.mark.unit
class TestModuleLevelFakerInstance:
    """Verify the module-level _fake instance is reused across mutation calls."""

    def test_module_level_fake_exists(self):
        """Module exports a single _fake instance at import time."""
        assert pm_module._fake is not None

    def test_faker_instance_is_same_object_across_calls(self, dna_factory: DNAFactory):
        """Both mutation functions share the same module-level Faker object."""
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        instance_before = id(pm_module._fake)

        # Call mutations several times and confirm the object identity never changes
        for _ in range(5):
            random.seed(10)
            mutate_driver_profile(driver_dna)
            random.seed(60)
            mutate_rider_profile(rider_dna)

        assert id(pm_module._fake) == instance_before

    def test_create_faker_instance_not_called_during_mutations(self, dna_factory: DNAFactory):
        """create_faker_instance() is NOT called on every mutate_* invocation."""
        driver_dna = dna_factory.driver_dna()
        rider_dna = dna_factory.rider_dna()

        with patch("agents.profile_mutations.create_faker_instance") as mock_create:
            random.seed(10)
            mutate_driver_profile(driver_dna)
            random.seed(60)
            mutate_rider_profile(rider_dna)

        # create_faker_instance should not be called at call time —
        # only once at module import. The patch replaces the name after import
        # so no new calls should occur.
        mock_create.assert_not_called()

    def test_driver_mutations_still_work_with_cached_faker(self, dna_factory: DNAFactory):
        """mutate_driver_profile returns valid changes using cached Faker."""
        driver_dna = dna_factory.driver_dna()
        random.seed(42)
        changes = mutate_driver_profile(driver_dna)
        assert isinstance(changes, dict)
        assert len(changes) > 0

    def test_rider_mutations_still_work_with_cached_faker(self, dna_factory: DNAFactory):
        """mutate_rider_profile returns valid changes using cached Faker."""
        rider_dna = dna_factory.rider_dna()
        random.seed(42)
        changes = mutate_rider_profile(rider_dna)
        assert isinstance(changes, dict)
        assert len(changes) > 0
