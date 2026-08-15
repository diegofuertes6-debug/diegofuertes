from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit(f'PyYAML no está instalado: {exc}') from exc

path = Path('.github/workflows/android-apk.yml')
text = path.read_text(encoding='utf-8')
parsed = yaml.safe_load(text)
print('YAML parsed successfully')
print('Workflow name:', parsed.get('name'))
print('Jobs:', ', '.join(parsed.get('jobs', {}).keys()))
