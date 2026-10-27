"""Run ONLY against the disposable cluster initialized with tests/bootstrap.sql.
No production credentials or model calls. Uses the installed PostgreSQL psql CLI.
"""
import concurrent.futures
import os
import subprocess

PSQL = os.environ.get('SHIWEN_TEST_PSQL', r'C:\Program Files\PostgreSQL\16\bin\psql.exe')
ARGS = [PSQL, '-X', '-h', '127.0.0.1', '-p', '55437', '-U', 'shiwen_test', '-d', os.environ.get('SHIWEN_TEST_DB','postgres'), '-v', 'ON_ERROR_STOP=1', '-tA']
USER = '33333333-3333-4333-8333-333333333333'

def query(sql):
    return subprocess.run(ARGS + ['-c', sql], capture_output=True, text=True)

if query("select count(*) from auth.users where id='" + USER + "'").stdout.strip() != '1':
    raise SystemExit('Disposable test cluster not initialized')

def create(i):
    return query("select public.cloud_create_job('" + USER + "', '" + format(i, '064x') + "', 'concurrent fixture', 30, 'concurrency-fixture')")

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(create, range(8)))
assert sum(r.returncode == 0 for r in results) == 3
assert all(r.returncode == 0 or 'TRIAL_LIMIT' in r.stderr for r in results)
assert query("select count(*) from public.cloud_transcripts where user_id='" + USER + "'").stdout.strip() == '3'
assert query("select jobs from public.cloud_ip_usage where ip_hash='concurrency-fixture'").stdout.strip() == '3'
print('8 simultaneous trial admissions: exactly 3 accepted, 5 rejected; IP counter exactly 3: PASS')
