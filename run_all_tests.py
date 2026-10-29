"""Run the included local regression checks; no live job APIs required."""
import subprocess
import sys

TESTS = [
    "test_smoke.py", "test_regression.py", "test_v6.py",
    "test_search_matrix_v8.py", "test_free_providers_v9.py",
    "test_provider_diagnostics.py",
]
failed=[]
for script in TESTS:
    print(f"\n{'='*12} {script} {'='*12}",flush=True)
    result=subprocess.run([sys.executable,script],check=False)
    print(f"RESULT: {'PASS' if result.returncode==0 else 'FAIL'} - {script}",flush=True)
    if result.returncode:failed.append(script)
print(f"\nSUMMARY: {len(TESTS)-len(failed)}/{len(TESTS)} test scripts passed")
if failed:print('FAILED: '+', '.join(failed))
raise SystemExit(bool(failed))
