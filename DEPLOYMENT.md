# EC2 Deployment

Este proyecto debe desplegarse desde la carpeta Git principal:

```bash
cd ~/energy-iot-saas
```

## Actualizar desde GitHub

```bash
git pull
```

## Desplegar backend y frontend

```bash
bash scripts/deploy_ec2.sh
```

El script hace:

- Reconstruye el backend con Docker Compose.
- Ejecuta migraciones Alembic.
- Instala dependencias frontend si hace falta.
- Compila React/Vite.
- Publica `frontend/dist` en `/var/www/thinc`.
- Valida y recarga Nginx.
- Prueba `https://thinc.site/api/v1/health`.

## Variables que no van a Git

Estos archivos deben existir en la EC2, pero no se suben a GitHub:

```text
backend/.env
frontend/.env
```

## Flujo diario recomendado

```bash
cd ~/energy-iot-saas
git status
git pull
bash scripts/deploy_ec2.sh
```

## Si haces cambios directamente en la EC2

```bash
cd ~/energy-iot-saas
git status
git add .
git commit -m "Describe el cambio"
git push
```
