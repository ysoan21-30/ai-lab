"""Sanity checks on config.py's tier definitions."""
from config import DEFAULT_TIER, ROUTER_MODEL, TIERS


class TestTiers:
    def test_all_expected_tiers_present(self):
        assert set(TIERS.keys()) == {"fast", "balanced", "deep"}

    def test_default_tier_is_valid(self):
        assert DEFAULT_TIER in TIERS

    def test_router_model_matches_fast_tier(self):
        assert ROUTER_MODEL == TIERS["fast"].model

    def test_tier_names_match_dict_keys(self):
        for key, tier in TIERS.items():
            assert tier.name == key

    def test_tiers_have_distinct_models(self):
        models = [t.model for t in TIERS.values()]
        assert len(models) == len(set(models))
