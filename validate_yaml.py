from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit(f'PyYAML no está instalado: {exc}') from exc

path = Path('.github/workflows/build-apk.yml')
text = path.read_text(encoding='utf-8')
parsed = yaml.safe_load(text)
workflow_on = parsed.get('on', parsed.get(True, {}))
push = workflow_on.get('push', {})
push_branches = push.get('branches', [])
assert 'workflow_dispatch' in workflow_on, 'workflow_dispatch trigger is required'
assert 'main' in push_branches, 'push trigger must include the default branch'

steps = parsed.get('jobs', {}).get('build', {}).get('steps', [])
steps_by_name = {step.get('name'): step for step in steps if isinstance(step, dict) and step.get('name')}
assert 'Build debug APK' in steps_by_name, 'Build step is required'
assert 'Upload debug APK artifact' in steps_by_name, 'Artifact upload step is required'
assert 'Create GitHub Release' in steps_by_name, 'Release step is required'

upload_path = steps_by_name['Upload debug APK artifact'].get('with', {}).get('path')
release_files = steps_by_name['Create GitHub Release'].get('with', {}).get('files')
assert upload_path == '${{ steps.apk.outputs.apk_path }}', 'Artifact upload must use the resolved APK path'
assert release_files == upload_path, 'Release upload must use the same APK path as the artifact upload'
print('YAML parsed successfully')
print('Workflow name:', parsed.get('name'))
print('Jobs:', ', '.join(parsed.get('jobs', {}).keys()))
