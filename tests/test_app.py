import os, tempfile
from app import create_app

def app_client():
    fd,path=tempfile.mkstemp(); os.close(fd)
    app=create_app({'TESTING':True,'SECRET_KEY':'test','DATABASE':path})
    yield app.test_client()
    os.unlink(path)

def test_register_login_and_transaction():
    client=next(app_client())
    assert client.post('/register',data={'username':'student','password':'password123'},follow_redirects=True).status_code==200
    assert client.post('/login',data={'username':'student','password':'password123'},follow_redirects=True).status_code==200
    with client.session_transaction() as s: assert s['user_id']
    assert client.get('/api/summary').status_code==200

def test_protected_route_redirects():
    client=next(app_client())
    assert client.get('/').status_code==302
