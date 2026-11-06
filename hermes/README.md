# Hermes — publicador de estado

`publish_status.py` escribe `/opt/data/virtoffice/status.json` cada 15 s con el
estado de Hermes (tarea actual, kanban y cron). El feeder del panel lo lee para
mostrar al agente en la oficina.

## Arranque

```bash
python3 hermes/publish_status.py &
```

O como servicio systemd: ver `hermes-office.service` en la raíz del repo.

## Archivos que lee

- `~/.hermes/virtoffice/current_task.txt` — tarea actual (una línea).
- `~/.hermes/virtoffice/status.json` — salida (escrita por este script).
- `/opt/data/cron/jobs.json` — cron de Hermes.
