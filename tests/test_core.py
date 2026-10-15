import httpx
import pytest
from app.core import DIMENSIONS, EvaluationError, extract_scores, jev_evaluate, questions, weighted_score

def test_weights():
    assert weighted_score({key: 100 for key in DIMENSIONS}) == 100
    assert weighted_score({key: 0 for key in DIMENSIONS}) == 0
    with pytest.raises(ValueError):
        weighted_score({'accuracy': 50})
    with pytest.raises(ValueError):
        weighted_score({key: 101 for key in DIMENSIONS})

def test_question_schema():
    assert set(questions()) == set(DIMENSIONS)
    assert all(q['type'] == 'score' and len(q['criteria']) == 6 for q in questions().values())

def test_parse_jev():
    payload = {'answers': {key: {'type': 'score', 'score': 4, 'confidence': .88} for key in DIMENSIONS}}
    scores, confidence = extract_scores(payload)
    assert all(v == 80 for v in scores.values())
    assert confidence == .88
    payload['answers']['accuracy']['score'] = 7
    with pytest.raises(EvaluationError):
        extract_scores(payload)

@pytest.mark.asyncio
async def test_live_jev_mock(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'mock-secret')
    def handler(req):
        assert req.headers['Authorization'] == 'Bearer mock-secret'
        assert 'questions' in __import__('json').loads(req.content)
        return httpx.Response(200, json={'answers': {key: {'type': 'score', 'score': 3.5, 'confidence': .93} for key in DIMENSIONS}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await jev_evaluate('Question', 'Answer', 'Reference', client=client)
    assert result['overall'] == 70
    assert result['status'] == 'evaluated'
    assert result['engine'] == 'jev'

@pytest.mark.asyncio
async def test_low_confidence_and_missing_reference(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'fake')
    def handler(req):
        return httpx.Response(200, json={'answers': {key: {'type': 'score', 'score': 3, 'confidence': .5} for key in DIMENSIONS}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await jev_evaluate('Question', 'Answer', None, client=client)
    assert result['status'] == 'review'

@pytest.mark.asyncio
async def test_jev_error_is_not_silent(monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'fake')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(429))) as client:
        with pytest.raises(EvaluationError):
            await jev_evaluate('q', 'a', 'r', client=client)
