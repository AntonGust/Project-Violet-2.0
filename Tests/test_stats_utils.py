"""
Tests for stats_utils.py functions.

Comprehensive tests for all statistical utility functions.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.stats_utils import (
    calculate_basic_stats,
    calculate_quartiles,
    calculate_percentiles,
    detect_outliers_iqr,
    detect_outliers_std,
    detect_outliers_zscore,
    summarize_distribution,
    compare_distributions,
    normalize_data
)


class TestCalculateBasicStats:
    """Tests for calculate_basic_stats function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_basic_stats_simple_data(self, sample_data_simple):
        """Test basic statistics with simple sequential data."""
        stats = calculate_basic_stats(sample_data_simple)

        assert 'mean' in stats
        assert 'var' in stats
        assert 'std' in stats
        assert 'min' in stats
        assert 'max' in stats
        assert 'range' in stats

        assert stats['mean'] == 5.5
        assert stats['min'] == 1.0
        assert stats['max'] == 10.0
        assert stats['range'] == 9.0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_basic_stats_identical_values(self, identical_data):
        """Test with identical values (zero variance)."""
        stats = calculate_basic_stats(identical_data)

        assert stats['mean'] == 5.0
        assert stats['var'] == 0.0
        assert stats['std'] == 0.0
        assert stats['range'] == 0.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_basic_stats_returns_floats(self, sample_data_simple):
        """Test that all values are returned as float type."""
        stats = calculate_basic_stats(sample_data_simple)

        for key, value in stats.items():
            assert isinstance(value, float)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_basic_stats_negative_values(self):
        """Test with negative values."""
        data = np.array([-5, -3, 0, 3, 5])
        stats = calculate_basic_stats(data)

        assert stats['mean'] == 0.0
        assert stats['min'] == -5.0
        assert stats['max'] == 5.0
        assert stats['range'] == 10.0


class TestCalculateQuartiles:
    """Tests for calculate_quartiles function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_quartiles_simple_data(self, sample_data_simple):
        """Test quartile calculation with simple data."""
        quartiles = calculate_quartiles(sample_data_simple)

        assert 'q1' in quartiles
        assert 'median' in quartiles
        assert 'q3' in quartiles
        assert 'iqr' in quartiles

        assert quartiles['median'] == 5.5
        assert quartiles['q1'] < quartiles['median'] < quartiles['q3']
        assert quartiles['iqr'] == quartiles['q3'] - quartiles['q1']

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_quartiles_identical_values(self, identical_data):
        """Test with identical values."""
        quartiles = calculate_quartiles(identical_data)

        assert quartiles['q1'] == 5.0
        assert quartiles['median'] == 5.0
        assert quartiles['q3'] == 5.0
        assert quartiles['iqr'] == 0.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_quartiles_returns_floats(self, sample_data_simple):
        """Test that all values are floats."""
        quartiles = calculate_quartiles(sample_data_simple)

        for key, value in quartiles.items():
            assert isinstance(value, float)


class TestCalculatePercentiles:
    """Tests for calculate_percentiles function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_percentiles_standard(self, sample_data_simple):
        """Test standard percentile calculations."""
        percentiles = calculate_percentiles(sample_data_simple, [25, 50, 75])

        assert 'p25' in percentiles
        assert 'p50' in percentiles
        assert 'p75' in percentiles

        assert percentiles['p25'] < percentiles['p50'] < percentiles['p75']

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_percentiles_extreme_values(self, sample_data_simple):
        """Test extreme percentiles (0 and 100)."""
        percentiles = calculate_percentiles(sample_data_simple, [0, 100])

        assert percentiles['p0'] == sample_data_simple.min()
        assert percentiles['p100'] == sample_data_simple.max()

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_percentiles_custom_list(self, sample_data_simple):
        """Test with custom percentile list."""
        percentiles = calculate_percentiles(sample_data_simple, [10, 30, 70, 90])

        assert len(percentiles) == 4
        assert 'p10' in percentiles
        assert 'p90' in percentiles


class TestDetectOutliersIQR:
    """Tests for detect_outliers_iqr function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_iqr_outliers_clear_case(self, sample_data_with_outliers):
        """Test IQR outlier detection with clear outliers."""
        outliers, thresholds = detect_outliers_iqr(sample_data_with_outliers)

        assert len(outliers) > 0
        assert 100 in outliers or 105 in outliers or 110 in outliers

        assert 'lower' in thresholds
        assert 'upper' in thresholds
        assert 'q1' in thresholds
        assert 'q3' in thresholds
        assert 'iqr' in thresholds

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_iqr_no_outliers(self, sample_data_simple):
        """Test with data that has no outliers."""
        outliers, thresholds = detect_outliers_iqr(sample_data_simple)

        # Simple sequential data shouldn't have outliers
        assert len(outliers) == 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_iqr_different_multipliers(self, sample_data_with_outliers):
        """Test that larger multiplier detects fewer outliers."""
        outliers_15, _ = detect_outliers_iqr(sample_data_with_outliers, multiplier=1.5)
        outliers_30, _ = detect_outliers_iqr(sample_data_with_outliers, multiplier=3.0)

        # More conservative multiplier should detect fewer outliers
        assert len(outliers_30) <= len(outliers_15)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_iqr_identical_values(self, identical_data):
        """Test with identical values (IQR=0)."""
        outliers, thresholds = detect_outliers_iqr(identical_data)

        assert len(outliers) == 0
        assert thresholds['iqr'] == 0.0


class TestDetectOutliersStd:
    """Tests for detect_outliers_std function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_std_outliers_clear_case(self, sample_data_with_outliers):
        """Test standard deviation outlier detection."""
        outliers, thresholds = detect_outliers_std(sample_data_with_outliers, std_multiplier=2.0)

        assert len(outliers) > 0
        assert 'mean' in thresholds
        assert 'std' in thresholds
        assert 'lower' in thresholds
        assert 'upper' in thresholds

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_std_method_both(self, sample_data_with_outliers):
        """Test 'both' method detects outliers on both sides."""
        outliers, _ = detect_outliers_std(sample_data_with_outliers, std_multiplier=1.5, method='both')

        assert isinstance(outliers, list)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_std_method_above_only(self):
        """Test 'above' method only detects high outliers."""
        data = np.array([1, 2, 3, 4, 5, 100])
        outliers, _ = detect_outliers_std(data, std_multiplier=2.0, method='above')

        assert 100 in outliers
        assert 1 not in outliers  # Low value should not be detected

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_std_method_below_only(self):
        """Test 'below' method only detects low outliers."""
        data = np.array([-100, 45, 50, 52, 55, 48])
        outliers, _ = detect_outliers_std(data, std_multiplier=2.0, method='below')

        assert -100 in outliers

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_std_invalid_method(self, sample_data_simple):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError):
            detect_outliers_std(sample_data_simple, method='invalid')

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_std_identical_values(self, identical_data):
        """Test with identical values (std=0)."""
        outliers, thresholds = detect_outliers_std(identical_data, std_multiplier=2.0)

        assert len(outliers) == 0


class TestDetectOutliersZscore:
    """Tests for detect_outliers_zscore function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_zscore_outliers_clear_case(self, sample_data_with_outliers):
        """Test z-score outlier detection."""
        outliers, stats = detect_outliers_zscore(sample_data_with_outliers, threshold=2.0)

        assert len(outliers) > 0
        # Each outlier is tuple of (index, value, z_score)
        for idx, val, z in outliers:
            assert isinstance(idx, int)
            assert isinstance(val, float)
            assert isinstance(z, float)
            assert abs(z) > 2.0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_zscore_no_outliers(self, sample_data_simple):
        """Test with data that has no extreme z-scores."""
        outliers, stats = detect_outliers_zscore(sample_data_simple, threshold=3.0)

        assert len(outliers) == 0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_zscore_identical_values(self, identical_data):
        """Test with identical values (std=0, undefined z-scores)."""
        outliers, stats = detect_outliers_zscore(identical_data, threshold=3.0)

        assert len(outliers) == 0
        assert stats['std'] == 0.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_zscore_returns_correct_structure(self, sample_data_with_outliers):
        """Test return structure is correct."""
        outliers, stats = detect_outliers_zscore(sample_data_with_outliers, threshold=2.0)

        assert 'mean' in stats
        assert 'std' in stats
        assert 'threshold' in stats

        if len(outliers) > 0:
            assert len(outliers[0]) == 3  # (index, value, z_score)


class TestSummarizeDistribution:
    """Tests for summarize_distribution function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_summarize_complete_structure(self, sample_data_normal):
        """Test that summary contains all expected sections."""
        summary = summarize_distribution(sample_data_normal)

        assert 'basic' in summary
        assert 'quartiles' in summary
        assert 'n' in summary
        assert 'n_unique' in summary

        # Check nested structures
        assert 'mean' in summary['basic']
        assert 'median' in summary['quartiles']

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_summarize_sample_size(self, sample_data_normal):
        """Test sample size is correct."""
        summary = summarize_distribution(sample_data_normal)

        assert summary['n'] == len(sample_data_normal)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_summarize_all_unique(self, sample_data_simple):
        """Test with all unique values."""
        summary = summarize_distribution(sample_data_simple)

        assert summary['n_unique'] == 10

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_summarize_identical_values(self, identical_data):
        """Test with identical values (n_unique=1)."""
        summary = summarize_distribution(identical_data)

        assert summary['n_unique'] == 1


class TestCompareDistributions:
    """Tests for compare_distributions function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_compare_two_groups(self, two_groups_data):
        """Test comparison of two distinct groups."""
        group1, group2 = two_groups_data
        comparison = compare_distributions(group1, group2, ('Group A', 'Group B'))

        assert 'Group A' in comparison
        assert 'Group B' in comparison
        assert 'difference' in comparison

        # Check difference metrics
        assert 'mean_diff' in comparison['difference']
        assert 'median_diff' in comparison['difference']
        assert 'std_diff' in comparison['difference']

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_compare_default_labels(self, two_groups_data):
        """Test with default labels."""
        group1, group2 = two_groups_data
        comparison = compare_distributions(group1, group2)

        assert 'Group 1' in comparison
        assert 'Group 2' in comparison

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_compare_identical_groups(self, sample_data_simple):
        """Test comparing identical groups."""
        comparison = compare_distributions(sample_data_simple, sample_data_simple)

        # Differences should be zero
        assert comparison['difference']['mean_diff'] == 0.0
        assert comparison['difference']['median_diff'] == 0.0
        assert comparison['difference']['std_diff'] == 0.0


class TestNormalizeData:
    """Tests for normalize_data function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_normalize_zscore(self, sample_data_simple):
        """Test z-score normalization."""
        normalized, params = normalize_data(sample_data_simple, method='zscore')

        assert len(normalized) == len(sample_data_simple)
        assert 'mean' in params
        assert 'std' in params
        assert params['method'] == 'zscore'

        # Z-score normalized data should have mean≈0 and std≈1
        assert abs(normalized.mean()) < 0.01
        assert abs(normalized.std(ddof=1) - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_normalize_minmax(self, sample_data_simple):
        """Test min-max normalization."""
        normalized, params = normalize_data(sample_data_simple, method='minmax')

        assert 'min' in params
        assert 'max' in params
        assert params['method'] == 'minmax'

        # Min-max normalized data should be in [0, 1]
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
        assert abs(normalized.min()) < 0.01
        assert abs(normalized.max() - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_normalize_robust(self, sample_data_with_outliers):
        """Test robust normalization."""
        normalized, params = normalize_data(sample_data_with_outliers, method='robust')

        assert 'median' in params
        assert 'iqr' in params
        assert params['method'] == 'robust'

        # Robust normalization should handle outliers better
        assert isinstance(normalized, np.ndarray)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_normalize_invalid_method(self, sample_data_simple):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError):
            normalize_data(sample_data_simple, method='invalid')

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_normalize_identical_values(self, identical_data):
        """Test normalization with zero variance."""
        normalized_z, params_z = normalize_data(identical_data, method='zscore')
        normalized_mm, params_mm = normalize_data(identical_data, method='minmax')

        # With zero variance/range, should handle gracefully
        assert params_z['std'] == 0.0
        assert params_mm['min'] == params_mm['max']

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_normalize_preserves_order(self, sample_data_simple):
        """Test that normalization preserves relative order."""
        normalized, _ = normalize_data(sample_data_simple, method='zscore')

        # Original order should be preserved
        for i in range(len(sample_data_simple) - 1):
            if sample_data_simple[i] < sample_data_simple[i + 1]:
                assert normalized[i] < normalized[i + 1]

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_normalize_negative_values(self):
        """Test normalization with negative values."""
        data = np.array([-10, -5, 0, 5, 10])

        normalized_z, _ = normalize_data(data, method='zscore')
        normalized_mm, _ = normalize_data(data, method='minmax')

        # Both should work with negative values
        assert len(normalized_z) == len(data)
        assert len(normalized_mm) == len(data)

        # Min-max should still be in [0, 1]
        assert normalized_mm.min() >= 0.0
        assert normalized_mm.max() <= 1.0
