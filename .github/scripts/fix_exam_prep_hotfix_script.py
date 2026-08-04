from pathlib import Path

path = Path('.github/scripts/apply_exam_prep_stuck_hotfix.py')
text = path.read_text(encoding='utf-8')
old = """progress_arg_count = service.count('options?.onProgress')
if progress_arg_count != 2:
    raise SystemExit(
        f'expected two upload progress arguments, found {progress_arg_count}'
    )
service = service.replace('options?.onProgress', 'options')
service_path.write_text(service, encoding='utf-8')
"""
new = """service_call_start = service.index('export async function transcribeClassCreationStep1(')
service_prefix = service[:service_call_start]
service_calls = service[service_call_start:]
progress_arg_count = service_calls.count('options?.onProgress')
if progress_arg_count != 2:
    raise SystemExit(
        f'expected two upload progress call arguments, found {progress_arg_count}'
    )
service = service_prefix + service_calls.replace('options?.onProgress', 'options')
service_path.write_text(service, encoding='utf-8')
"""
if text.count(old) != 1:
    raise SystemExit(f'expected one progress replacement block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
Path(__file__).unlink()
