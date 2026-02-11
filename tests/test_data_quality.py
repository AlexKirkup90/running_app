from core.services.readiness import readiness_band, readiness_score


def test_readiness_score_range():
    score = readiness_score(1, 1, 1, 5)
    assert 1 <= score <= 5
    assert readiness_band(score) == "red"
