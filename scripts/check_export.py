"""Verify the asynchronous ZIP and clip subtitle download against running services."""
import io
import json
import time
import zipfile
from pathlib import Path

import httpx

fixture = json.loads(Path('.local/analysis-test.json').read_text())
with httpx.Client(base_url='http://localhost:8000/api/v1', headers={'Origin': 'http://localhost:3000'}, timeout=60) as client:
    client.post('/auth/login', json={'email': fixture['email'], 'password': fixture['password']}).raise_for_status()
    base = f"/projects/{fixture['project_id']}"
    response = client.post(f'{base}/export')
    response.raise_for_status()
    identifier = response.json()['job_id']
    for _ in range(120):
        job = next(j for j in client.get(f'{base}/jobs').json() if j['id'] == identifier)
        if job['status'] == 'SUCCEEDED':
            break
        assert job['status'] not in {'FAILED', 'CANCELED'}, job
        time.sleep(1)
    else:
        raise TimeoutError('Archive exceeded two minutes')
    response = client.get(f'{base}/export/{identifier}')
    response.raise_for_status()
    archive = httpx.get(response.json()['url'], timeout=60)
    archive.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(archive.content)) as files:
        assert files.namelist() and all(name.endswith('.mp4') for name in files.namelist())
        assert files.testzip() is None
    response = client.get(f"{base}/clips/{fixture['clip_id']}/subtitles")
    response.raise_for_status()
    assert '-->' in response.text
    print('Real ZIP archive and clip subtitle download passed.')
