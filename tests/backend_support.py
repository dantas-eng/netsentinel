from werkzeug.security import generate_password_hash
from netsentinel.api.settings import Settings

MAC = '02:00:00:00:00:20'
HASH = generate_password_hash('test-only-password', method='pbkdf2:sha256:1000')


def settings(url, mode='lab'):
    return Settings(mode, url, 'test-only-secret-key-with-at-least-32-characters', 'operator', HASH)


def snapshot(end=8, count=80, run_id='capture-1', **updates):
    value = dict(timestamp=1700000000 + end, source='live', capture_run_id=run_id,
                 window_seconds=8, observed_seconds=8, window_start_monotonic=end-8,
                 window_end_monotonic=end, warming_up=False, incomplete=False,
                 devices={MAC: dict(bytes=count, packets=1, arp_requests=0, arp_replies=0)},
                 arp_claims=[], links=[])
    value.update(updates)
    return value


def login(client):
    csrf = client.get('/api/auth/csrf').json['csrf_token']
    response = client.post('/api/auth/login', json=dict(username='operator', password='test-only-password'),
                           headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    return response, response.json['csrf_token']
