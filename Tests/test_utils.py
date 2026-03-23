"""
Tests for utils.py functions.

Tests the compute_confidence_interval function with various scenarios.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.utils import compute_confidence_interval


class TestComputeConfidenceInterval:
    """Tests for compute_confidence_interval function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_return_margin_of_error_default(self, sample_confidence_data):
        """Test default behavior returns margin of error."""
        result = compute_confidence_interval(sample_confidence_data, alpha=0.05)

        assert isinstance(result, float)
        assert result > 0
        # For this data, MOE should be reasonable (not too large)
        assert result < 10

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_return_bounds_mode(self, sample_confidence_data):
        """Test return_bounds=True returns tuple of (lower, upper)."""
        lower, upper = compute_confidence_interval(
            sample_confidence_data,
            alpha=0.05,
            return_bounds=True
        )

        assert isinstance(lower, float)
        assert isinstance(upper, float)
        assert lower < upper

        # Check that bounds are symmetric around mean
        mean = sample_confidence_data.mean()
        assert abs((upper - mean) - (mean - lower)) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_different_alpha_values(self, sample_data_simple):
        """Test that smaller alpha gives wider confidence intervals."""
        moe_95 = compute_confidence_interval(sample_data_simple, alpha=0.05)
        moe_99 = compute_confidence_interval(sample_data_simple, alpha=0.01)

        # 99% CI should be wider than 95% CI
        assert moe_99 > moe_95

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_bounds_consistency(self, sample_data_simple):
        """Test that bounds mode is consistent with MOE mode."""
        moe = compute_confidence_interval(sample_data_simple, alpha=0.05)
        lower, upper = compute_confidence_interval(
            sample_data_simple,
            alpha=0.05,
            return_bounds=True
        )

        mean = sample_data_simple.mean()

        # Check that bounds match mean ± moe
        assert abs(lower - (mean - moe)) < 0.01
        assert abs(upper - (mean + moe)) < 0.01

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_identical_values(self, identical_data):
        """Test with data that has zero variance."""
        moe = compute_confidence_interval(identical_data, alpha=0.05)

        # With zero variance, MOE should be 0
        assert moe == 0.0 or abs(moe) < 1e-10

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_small_sample_size(self):
        """Test with very small sample size (n=3)."""
        small_data = np.array([1.0, 2.0, 3.0])
        moe = compute_confidence_interval(small_data, alpha=0.05)

        # Should still return a valid value
        assert isinstance(moe, float)
        assert moe > 0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_two_element_array(self):
        """Test minimum valid sample size (n=2)."""
        data = np.array([10.0, 20.0])
        moe = compute_confidence_interval(data, alpha=0.05)

        assert isinstance(moe, float)
        assert moe > 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_large_sample_reduces_moe(self):
        """Test that larger samples give smaller MOE (holding other factors constant)."""
        np.random.seed(42)
        small_sample = np.random.normal(50, 10, 30)
        large_sample = np.random.normal(50, 10, 300)

        moe_small = compute_confidence_interval(small_sample, alpha=0.05)
        moe_large = compute_confidence_interval(large_sample, alpha=0.05)

        # Larger sample should have smaller MOE
        assert moe_large < moe_small

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_with_negative_values(self):
        """Test that function works with negative values."""
        data = np.array([-10, -5, 0, 5, 10])
        moe = compute_confidence_interval(data, alpha=0.05)

        assert isinstance(moe, float)
        assert moe > 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_bounds_contain_mean(self, sample_data_normal):
        """Test that confidence interval bounds contain the mean."""
        lower, upper = compute_confidence_interval(
            sample_data_normal,
            alpha=0.05,
            return_bounds=True
        )
        mean = sample_data_normal.mean()

        assert lower <= mean <= upper

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_alpha_0_10_gives_90_percent_ci(self, sample_data_simple):
        """Test 90% confidence interval (alpha=0.10)."""
        moe_90 = compute_confidence_interval(sample_data_simple, alpha=0.10)
        moe_95 = compute_confidence_interval(sample_data_simple, alpha=0.05)

        # 90% CI should be narrower than 95% CI
        assert moe_90 < moe_95

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_return_type_consistency(self, sample_data_simple):
        """Test return types are always float."""
        moe = compute_confidence_interval(sample_data_simple, alpha=0.05)
        lower, upper = compute_confidence_interval(
            sample_data_simple,
            alpha=0.05,
            return_bounds=True
        )

        assert type(moe) == float
        assert type(lower) == float
        assert type(upper) == float

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_high_variance_gives_wider_ci(self):
        """Test that higher variance gives wider confidence intervals."""
        np.random.seed(42)
        low_var_data = np.random.normal(50, 2, 100)
        high_var_data = np.random.normal(50, 20, 100)

        moe_low_var = compute_confidence_interval(low_var_data, alpha=0.05)
        moe_high_var = compute_confidence_interval(high_var_data, alpha=0.05)

        assert moe_high_var > moe_low_var

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_with_outliers(self, sample_data_with_outliers):
        """Test function behavior with outliers present."""
        moe = compute_confidence_interval(sample_data_with_outliers, alpha=0.05)

        # Should still compute a valid CI even with outliers
        assert isinstance(moe, float)
        assert moe > 0

        # With outliers, CI should be wider
        data_no_outliers = sample_data_with_outliers[:7]
        moe_no_outliers = compute_confidence_interval(data_no_outliers, alpha=0.05)
        assert moe > moe_no_outliers


# Note: extract_experiment() is not tested here as it requires file system operations
# and would be better suited for integration tests with mock data files.
