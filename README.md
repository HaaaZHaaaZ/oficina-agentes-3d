# Oficina de agentes 3D

Fork de [OneByJorah/offivo](https://github.com/OneByJorah/offivo) (licencia MIT) adaptado para ver en una oficina 3D a **Hermes** y **Claude**, los agentes del servidor, con su estado real.

## Qué cambia respecto al original

- **Agentes reales:** el servicio `feeder` escribe en el panel el estado de Hermes (`~/.hermes/virtoffice/status.json`, su kanban y su cron) y de Claude (procesos `claude -p` en el contenedor `claude-discord`). Ya no salen los agentes de demostración ni frases o estados inventados.
- **Movimiento:** los personajes calculan rutas (A*) que esquivan los muebles; cuando trabajan van a su puesto y se sientan frente al monitor; libres, pasean.
- **Botones con función:** 📋 Tareas, 📊 Servidor (carga, memoria, swap, disco, contenedores), ⚙️ Ajustes, 🔒 Bloquear, Equipo y Actividad.
- **Enfocar a un agente:** clic en su icono de arriba; la cámara le sigue. «Vista general», Esc o un segundo clic vuelven a la oficina completa.

## Despliegue

Stack de Portainer (método *Repository*) con `docker-compose.yml`:

- `office`: el panel, en `http://<servidor>:9502` (variable `LAN_PORT`) y, por Cloudflare Tunnel, en `http://virtoffice:9502`. Sin login propio: ponle Cloudflare Access delante si lo publicas.
- `feeder`: necesita el socket de Docker y `HERMES_HOME` (por defecto `/home/haz/.hermes`) en solo lectura.
- **Tarea actual de Hermes:** el feeder lee `~/.hermes/virtoffice/current_task.txt` directamente (una línea; vacío = libre). `status.json` de `hermes/publish_status.py` es opcional: solo se usa si se ha escrito hace menos de 90 s; si no, el feeder lee el kanban y el cron de Hermes por su cuenta.

### Migrar desde la prueba (contenedores sueltos)

1. `docker rm -f virtoffice-lan virtoffice-feeder` (los de la etiqueta `temporal=virtoffice-test`; ocupan el puerto 9502 y el nombre del feeder).
2. En Portainer, borrar el stack standalone y crearlo como *Repository*: este repo, rama `main`, `docker-compose.yml`.
3. Comprobar `http://<servidor>:9502` y `docker logs virtoffice-feeder`.

---

<div align="center">

![Offivo banner](docs/assets/banner.svg)

# Offivo

*Formerly VirtOffice (hermes-3d-office).*

Virtual office platform — shared workspaces, video rooms, team chat, and collaborative document editing with Docker deployment.

[![GitHub release](https://img.shields.io/github/v/release/OneByJorah/offivo?color=a78bfa&label=release&logo=github)](https://github.com/OneByJorah/offivo/releases)
[![npm version](https://img.shields.io/npm/v/offivo?color=a78bfa&label=npm&logo=npm)](https://www.npmjs.com/package/offivo)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?color=FFB300&logo=open-source-initiative&logoColor=FFB300)](https://opensource.org/licenses/MIT)

</div>

![Offivo landing page](docs/screenshots/landing.png)
![Offivo office view](docs/screenshots/office.png)

## What This Is

Virtual office platform — shared workspaces, video rooms, team chat, and collaborative document editing with Docker deployment.

## Quick Start

### npm

```bash
npm install offivo
```

### Docker

```bash
git clone https://github.com/OneByJorah/offivo.git
cd offivo
docker compose up -d
```

### From Source

```bash
git clone https://github.com/OneByJorah/offivo.git
cd offivo
npm install
npm run dev
```

## Features

- **Self-hosted** — run on your own hardware
- **Docker Compose** — full stack with one command
- **npm package** — install via npm
- **Dark theme** — operational UI

- **Shared workspaces** — virtual office spaces for teams
- **Video rooms** — WebRTC-based video conferencing
- **Team chat** — real-time messaging and channels
- **Document collaboration** — shared editing and comments
- **Docker Compose deployment** — multi-service stack
- **Dark theme** — modern, collaborative UI

## Package Badges

[![GitHub release](https://img.shields.io/github/v/release/OneByJorah/offivo?color=a78bfa&label=release&logo=github)](https://github.com/OneByJorah/offivo/releases)
[![npm version](https://img.shields.io/npm/v/offivo?color=a78bfa&label=npm&logo=npm)](https://www.npmjs.com/package/offivo)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?color=FFB300&logo=open-source-initiative&logoColor=FFB300)](https://opensource.org/licenses/MIT)

## Contributing

[Open an issue](https://github.com/OneByJorah/offivo/issues) to report a bug or request a feature.

## License

MIT — see [LICENSE](LICENSE).
