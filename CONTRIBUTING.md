# Contributing / перед пушем

## Коммиты

1. **Код и шаблоны**: скрипты, `templates/`, `data/*.example`, `.gitignore`, `README`, без `data/server.env` и `data/users.json`.
2. **Локальная установка** (опционально): только на сервере или приватный remote; не пушить секреты.

## Если `server.env` / `users.json` уже в индексе

```bash
git rm --cached data/server.env data/users.json
git commit -m "chore: stop tracking local secrets"
```

## Проверки перед push

- `python3 -m py_compile bot.py scripts/vpn_manager.py`
- `bash -n vpn.sh install.sh scripts/*.sh`
- `bash vpn.sh --help` и `python3 scripts/vpn_manager.py --help`

## Smoke (на машине с systemd)

`vpn install` → `vpn status` → `vpn user add` → `vpn user info` → `vpn user export --zip` → `vpn uninstall --yes`
