import math

import pytest

from tropicast.classification.imd import AgencyMismatchError, category_probabilities, classify


@pytest.mark.parametrize("wind,code", [
    (10, "LOW"), (17, "D"), (27, "D"), (28, "DD"), (33, "DD"), (34, "CS"), (47, "CS"), (48, "SCS"),
    (63, "SCS"), (64, "VSCS"), (89, "VSCS"), (90, "ESCS"), (119, "ESCS"), (120, "SuCS"), (165, "SuCS"),
])
def test_thresholds(wind, code):
    assert classify(wind).code == code


def test_fractional_wind_between_classes():
    assert classify(33.5).code == "DD"


def test_agency_mismatch_refused():
    with pytest.raises(AgencyMismatchError):
        classify(70, agency="usa")


def test_unknown_wind():
    assert classify(float("nan")).code == "UNK"


def test_probabilities_sum_to_one_and_peak_at_median():
    p = category_probabilities({0.05: 40.0, 0.5: 70.0, 0.95: 95.0})
    assert math.isclose(sum(p.values()), 1.0, rel_tol=1e-9)
    assert max(p, key=p.get) == "VSCS"
