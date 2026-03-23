# Purple_Revisited Test Suite

Comprehensive pytest test suite for all non-plotting functions in the Purple_Revisited project.

## Overview

This test suite provides comprehensive coverage for:
- **utils.py** - Core utility functions (confidence intervals, data extraction)
- **stats_utils.py** - Statistical utility functions (9 functions)
- **metrics/session_length.py** - Session length analysis
- **metrics/entropy.py** - Entropy calculations for MITRE data and session lengths
- **metrics/mitre_distribution.py** - MITRE ATT&CK distribution analysis
- **metrics/sequences.py** - Sequence extraction and indexing

## Test Structure

```
test_folder/
├── conftest.py                         # Common fixtures and test data
├── pytest.ini                          # Pytest configuration
├── test_utils.py                       # Tests for utils.py (15 tests)
├── test_stats_utils.py                 # Tests for stats_utils.py (50+ tests)
├── test_metrics_session_length.py      # Tests for session_length.py (20+ tests)
├── test_metrics_entropy.py             # Tests for entropy.py (25+ tests)
├── test_metrics_mitre_distribution.py  # Tests for mitre_distribution.py (25+ tests)
├── test_metrics_sequences.py           # Tests for sequences.py (30+ tests)
└── README.md                           # This file
```

## Requirements

Install pytest and dependencies:

```bash
pip install pytest numpy scipy
```

Optional (for better test output):
```bash
pip install pytest-cov pytest-xdist
```

## Running Tests

### Run All Tests

```bash
cd test_folder
pytest
```

### Run Specific Test File

```bash
pytest test_utils.py
pytest test_stats_utils.py
pytest test_metrics_session_length.py
```

### Run Tests by Marker

Tests are organized with markers for easy filtering:

```bash
# Run only unit tests
pytest -m unit

# Run only statistical tests
pytest -m statistical

# Run only edge case tests
pytest -m edge_case

# Run slow tests
pytest -m slow
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=../ --cov-report=html --cov-report=term
```

This will generate an HTML coverage report in `htmlcov/index.html`.

### Run Tests in Parallel

If you have pytest-xdist installed:

```bash
pytest -n auto
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
Individual function tests with controlled inputs and expected outputs.

### Statistical Tests (`@pytest.mark.statistical`)
Tests verifying statistical calculations, distributions, and mathematical properties.

### Edge Case Tests (`@pytest.mark.edge_case`)
Tests for boundary conditions, empty data, single values, and unusual inputs.

### Integration Tests (`@pytest.mark.integration`)
Tests verifying interactions between multiple functions.

## Test Coverage

### utils.py
- ✅ `compute_confidence_interval()` - 15 tests
  - Default margin of error mode
  - Bounds return mode
  - Different alpha values
  - Edge cases (identical values, small samples, outliers)
  - Statistical properties validation

### stats_utils.py
- ✅ `calculate_basic_stats()` - 4 tests
- ✅ `calculate_quartiles()` - 3 tests
- ✅ `calculate_percentiles()` - 3 tests
- ✅ `detect_outliers_iqr()` - 4 tests
- ✅ `detect_outliers_std()` - 6 tests
- ✅ `detect_outliers_zscore()` - 4 tests
- ✅ `summarize_distribution()` - 4 tests
- ✅ `compare_distributions()` - 3 tests
- ✅ `normalize_data()` - 9 tests

### metrics/session_length.py
- ✅ `measure_session_length()` - 21 tests
  - Basic statistics calculation
  - Quartiles and median
  - Five most common lengths
  - Zero-length session handling
  - Edge cases (single session, identical lengths, missing fields)

### metrics/entropy.py
- ✅ `compute_entropy()` - 6 tests
- ✅ `measure_entropy_mitre()` - 5 tests
- ✅ `measure_entropy_tactics()` - 1 test
- ✅ `measure_entropy_techniques()` - 1 test
- ✅ `measure_entropy_session_length()` - 7 tests
- Additional integration tests for entropy calculations

### metrics/mitre_distribution.py
- ✅ `create_heatmap()` - 5 tests
- ✅ `measure_mitre_distribution()` - 20 tests
  - Tactic and technique counting
  - Fraction calculations
  - Session-level tracking
  - Cumulative counts
  - Heatmap generation
  - Edge cases (empty sessions, missing fields)

### metrics/sequences.py
- ✅ `measure_sequences()` - 11 tests
- ✅ `measure_tactic_sequences()` - 2 tests
- ✅ `measure_technique_sequences()` - 2 tests
- ✅ `measure_command_sequences()` - 3 tests
- ✅ Integration tests - 6 tests

## Common Fixtures

### Sample Data Fixtures
- `sample_data_simple` - Simple 1-10 array
- `sample_data_with_outliers` - Data with clear outliers
- `sample_data_normal` - Normally distributed (n=100)
- `sample_data_uniform` - Uniformly distributed (n=50)
- `identical_data` - All identical values
- `two_groups_data` - Two distinct groups for comparison

### Session Fixtures
- `sample_sessions_basic` - 3 sessions with varied lengths
- `sample_sessions_with_zeros` - Sessions including zero-length
- `sample_sessions_varied_tactics` - Sessions with diverse MITRE tactics
- `empty_sessions` - Empty session list
- `single_session` - Single session for edge cases

### Statistical Fixtures
- `sample_confidence_data` - Data with known statistical properties
- `two_groups_data` - Two groups for comparison tests

## Writing New Tests

### Test Template

```python
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from your_module import your_function


class TestYourFunction:
    """Tests for your_function."""

    @pytest.mark.unit
    def test_basic_functionality(self, fixture_name):
        """Test basic function behavior."""
        result = your_function(fixture_name)

        assert result is not None
        assert isinstance(result, expected_type)
        # Add more assertions
```

### Best Practices

1. **Use descriptive test names** - Name should explain what is being tested
2. **One assertion per concept** - Test one thing at a time when possible
3. **Use fixtures** - Reuse common test data via fixtures
4. **Mark tests appropriately** - Use `@pytest.mark.unit`, `@pytest.mark.edge_case`, etc.
5. **Test edge cases** - Empty data, single values, None, etc.
6. **Document expected behavior** - Use docstrings to explain what's being tested

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install pytest numpy scipy
      - run: cd test_folder && pytest
```

## Troubleshooting

### Import Errors

If you get import errors, make sure:
1. You're running pytest from the `test_folder` directory
2. The parent directory is accessible
3. All dependencies are installed

### Failed Tests

1. Check if the source code has changed
2. Verify test data fixtures match expected format
3. Look for numerical precision issues (use `abs(x - y) < epsilon`)

## Test Statistics

- **Total Test Files**: 6
- **Total Tests**: 165+
- **Test Markers**: unit, statistical, edge_case, integration, slow
- **Fixtures**: 13 common fixtures

## Future Enhancements

- [ ] Add performance/benchmark tests
- [ ] Add property-based testing with Hypothesis
- [ ] Add mutation testing with mutmut
- [ ] Increase coverage to 100%
- [ ] Add integration tests with real data files
- [ ] Add tests for extract_experiment() with mock file system

## Contributing

When adding new functions to Purple_Revisited:
1. Add corresponding tests in the appropriate test file
2. Use existing fixtures when possible
3. Add new fixtures to `conftest.py` if needed
4. Update this README with test counts
5. Ensure all tests pass before committing

## License

Same license as the Purple_Revisited project.

## Contact

For questions or issues with the test suite, see the main project documentation.

---

**Last Updated**: 2025-11-10
**Test Suite Version**: 1.0
**Pytest Version**: 6.0+
