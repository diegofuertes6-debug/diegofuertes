# Política de secretos y credenciales

## Principios

- Usa `GOOGLE_MAPS_API_KEY` como variable de entorno para desarrollo local.
- Usa **GitHub Secrets** para CI/CD y expón la clave al job mediante variables de entorno.
- No subas al repositorio archivos con credenciales (`.env*`, `webServerApiSettings.json`, keystores, APKs, logs de build).
- Si una credencial se expuso, rótala antes de volver a usarla.

## Configuración recomendada

### Desarrollo local

```bash
export GOOGLE_MAPS_API_KEY="TU_API_KEY_AQUÍ"
```

### GitHub Actions

```yaml
env:
  GOOGLE_MAPS_API_KEY: ${{ secrets.GOOGLE_MAPS_API_KEY }}
```

## Compatibilidad heredada

- `webServerApiSettings.json` sigue existiendo solo como fallback temporal para instalaciones antiguas.
- Si necesitas usarlo puntualmente, mantenlo **fuera del control de versiones** y migra cuanto antes a variables de entorno.

## Prevención continua

### Checklist para pull requests

- [ ] No hay claves, tokens, contraseñas ni certificados en archivos versionados.
- [ ] `.gitignore` cubre archivos locales de secretos y artefactos de build.
- [ ] Los workflows usan `secrets.*` y variables de entorno, nunca valores hardcodeados.
- [ ] Los artefactos generados (APKs, logs, keystores) se publican como artifacts/releases, no se versionan.
- [ ] Las credenciales expuestas previamente se han rotado.

### Escaneo continuo en CI

- Activa **GitHub Secret Scanning** y **Push Protection** en el repositorio.
- Ejecuta el escaneo de secretos en cada pull request y en la rama principal.
- Bloquea la publicación de releases si el escaneo detecta secretos sin resolver.
- Revisa periódicamente los artifacts y logs de GitHub Actions para evitar exposiciones accidentales.
