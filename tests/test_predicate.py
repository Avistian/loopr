import pytest

from loopr.predicate import PredicateError, evaluate_predicate
from loopr.result import Result


def r(status="ok", summary="", next=None, artifacts=None):
    return Result(status=status, summary=summary, next=next, artifacts=artifacts or [])


def test_eq_true_false():
    assert evaluate_predicate('result.status == "issues"', r(status="issues"))
    assert not evaluate_predicate('result.status == "issues"', r(status="ok"))


def test_neq():
    assert evaluate_predicate('result.status != "ok"', r(status="issues"))


def test_in_list():
    assert evaluate_predicate('result.status in ["a", "b"]', r(status="b"))
    assert not evaluate_predicate('result.status in ["a", "b"]', r(status="c"))


def test_boolean_logic():
    res = r(status="issues", summary="urgent")
    assert evaluate_predicate(
        'result.status == "issues" and result.summary == "urgent"', res
    )
    assert not evaluate_predicate(
        'result.status == "ok" or result.summary == "calm"', res
    )


def test_not_operator():
    assert evaluate_predicate('not result.status == "ok"', r(status="issues"))


def test_unknown_name_rejected():
    with pytest.raises(PredicateError, match="only 'result'"):
        evaluate_predicate('foo == "x"', r())


def test_unknown_field_rejected():
    with pytest.raises(PredicateError, match="unknown result field"):
        evaluate_predicate('result.bogus == "x"', r())


def test_calls_rejected():
    with pytest.raises(PredicateError):
        evaluate_predicate('result.status.upper() == "OK"', r())


def test_syntax_error_rejected():
    with pytest.raises(PredicateError, match="invalid predicate"):
        evaluate_predicate("result.status ==", r())
