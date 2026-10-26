from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
import app
import public_quota as quota
import store


@pytest.fixture(autouse=True)
def isolated_quota(tmp_path, monkeypatch):
    quota._reset_for_tests()
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.setattr(store, 'DB', tmp_path/'tasks.sqlite3')
    monkeypatch.setattr(quota, 'PUBLIC', False)
    yield
    quota._reset_for_tests()


def request(headers=()):
    return Request({'type':'http','headers':headers,'client':('192.0.2.1',1234)})


def test_private_gate_is_inert_and_creates_no_database(tmp_path):
    for _ in range(20):quota.require_quota('editorial')(request())
    assert not (tmp_path/'public_quota.db').exists()


def test_device_rejection_does_not_consume_ip_and_day_rolls_over():
    for _ in range(3):quota.gate('editorial','device0001','ip1','2026-10-26')
    with pytest.raises(HTTPException) as caught:quota.gate('editorial','device0001','ip1','2026-10-26')
    assert caught.value.status_code == 429
    assert quota.gate('editorial','device0002','ip1','2026-10-26')['ip_remaining'] == 6
    assert quota.gate('editorial','device0001','ip1','2026-10-27')['device_remaining'] == 2


def test_rotating_devices_still_exhausts_ip_pool():
    for i in range(10):quota.gate('editorial',f'device{i:04}','same-ip')
    with pytest.raises(HTTPException) as caught:quota.gate('editorial','another-device','same-ip')
    assert caught.value.status_code == 429
    assert quota.gate('editorial','another-device','other-ip')['device_remaining'] == 2


def test_missing_or_invalid_device_uses_ip_fallback(monkeypatch):
    monkeypatch.setattr(quota,'PUBLIC',True)
    dependency=quota.require_quota('editorial')
    for header in ['', 'short', 'bad-device\n']:
        dependency(request([(b'x-device-id',header.encode())]))
    with pytest.raises(HTTPException):dependency(request())
    assert quota.client_ip(request([(b'x-forwarded-for',b'203.0.113.8, 10.0.0.1')])) == '203.0.113.8'
    assert quota.client_ip(request()) == '192.0.2.1'


def test_concurrent_checks_cannot_exceed_device_limit():
    def attempt(_):
        try:quota.gate('classify','same-device','same-ip');return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(attempt,range(20)))
    assert results.count(200) == 3
    assert results.count(429) == 17


def test_counts_survive_connection_reopen():
    for _ in range(3):quota.gate('editorial','persist-device','same-ip')
    quota._reset_for_tests()
    with pytest.raises(HTTPException) as caught:quota.gate('editorial','persist-device','same-ip')
    assert caught.value.status_code == 429


def test_configured_public_hosts_and_private_allowlist(monkeypatch):
    from app_shared import install_shared
    for public in [True,False]:
        monkeypatch.setenv('SHIWEN_PUBLIC','1' if public else '')
        monkeypatch.setenv('SHIWEN_ALLOWED_HOSTS',' public.example.test , testserver ')
        instance=FastAPI();install_shared(instance)
        @instance.get('/probe')
        def probe():return {'ok':True}
        client=TestClient(instance)
        assert client.get('/probe',headers={'Host':'public.example.test'}).status_code == (200 if public else 400)
        assert client.get('/probe',headers={'Host':'unlisted.example.test'}).status_code == 400
        assert client.get('/probe').status_code == 200


@pytest.mark.parametrize('path,body,limit',[
    ('/api/library/items/missing/question',{'question':'测试问题'},10),
    ('/api/library/image-items/missing/editorial',None,3),
    ('/api/library/image-items/missing/classify',None,3),
    ('/api/studio/research/documents/missing',{},5),
])
def test_all_four_routes_gate_before_missing_material(monkeypatch,path,body,limit):
    monkeypatch.setattr(quota,'PUBLIC',True)
    store.init()
    client=TestClient(app.app)
    responses=[client.post(path,json=body,headers={'X-Device-Id':'testdevice123'}) for _ in range(limit+1)]
    assert all(r.status_code in {400,404} for r in responses[:-1])
    assert responses[-1].status_code == 429
    assert responses[-1].json()['detail'] == quota.OVER_LIMIT_MESSAGE


def test_manual_note_is_not_gated(monkeypatch,tmp_path):
    monkeypatch.setattr(quota,'PUBLIC',True)
    client=TestClient(app.app)
    store.init()
    for _ in range(12):
        assert client.post('/api/studio/research/documents/missing/manual-note',
                           json={'topic_title':'笔记','personal':'自己的理解'}).status_code == 404
    assert not (tmp_path/'public_quota.db').exists()
