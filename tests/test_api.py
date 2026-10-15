from app import main

PAYLOAD = {"question": "What is the capital of France?", "answer": "Paris is the capital of France.", "reference": "Paris.", "engine": "demo"}

def test_health(client):
    assert client.get('/health').json() == {'status': 'ok'}

def test_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'QUALITY LAB' in response.text

def test_demo_evaluation_saved_and_retrieved(client):
    response = client.post('/api/evaluate', json=PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'demo_only'
    assert data['engine'] == 'deterministic_demo'
    assert 0 <= data['overall'] <= 100
    assert len(data['scores']) == 5
    assert client.get('/api/runs/' + data['id']).json()['id'] == data['id']
    assert len(client.get('/api/runs').json()) == 1

def test_validation(client):
    assert client.post('/api/evaluate', json={**PAYLOAD, 'answer': ''}).status_code == 422
    assert client.post('/api/evaluate', json={**PAYLOAD, 'engine': 'unknown'}).status_code == 422
    assert client.get('/api/runs?limit=101').status_code == 422
    assert client.get('/api/runs/missing').status_code == 404

def test_live_requires_api_key(client, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    res = client.post('/api/evaluate', json={**PAYLOAD, 'engine': 'jev'})
    assert res.status_code == 503
    assert client.get('/api/runs').json() == []

def test_openai_model_allowlist(client, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')
    res = client.post('/api/evaluate', json={**PAYLOAD, 'generator': 'openai', 'answer': None, 'model': 'arbitrary-model'})
    assert res.status_code == 503
