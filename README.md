# vangrapf-proxy-vk-tunnel

Vangrapf VK Tunnel Proxy для локального запуска на Lubuntu через VK Tunnel.

## Быстрый запуск на Lubuntu

```bash
./run_lubuntu_vk_tunnel.sh
```

Скрипт автоматически:

1. установит системные пакеты через `apt` (`python3-venv`, `python3-tk`, `nodejs`, `npm`, `curl`);
2. создаст `.venv` и установит/обновит Python-зависимости из `requirements.txt`;
3. локально установит/обновит `@vkontakte/vk-tunnel` в `node_modules`;
4. запустит Flask proxy на `http://127.0.0.1:5000`;
5. запустит VK Tunnel к локальному proxy;
6. выведет публичную ссылку VK Tunnel в GUI и скопирует её в буфер обмена, когда ссылка появится.

> Логин в VK Tunnel скрипт не автоматизирует: авторизацию нужно пройти вручную в окне/терминале, который откроет VK Tunnel.

## GUI

По умолчанию запускается GUI:

```bash
./run_lubuntu_vk_tunnel.sh
```

В GUI доступны:

- **Старт / обновить и запустить** — обновляет зависимости и запускает proxy + tunnel;
- **Добавить в автозапуск** — создаёт user-service systemd и включает запуск при входе пользователя;
- **Выход** — останавливает дочерние процессы.

## Запуск без GUI

```bash
./run_lubuntu_vk_tunnel.sh --no-gui
```

## Только установка/обновление зависимостей

```bash
./run_lubuntu_vk_tunnel.sh --install-only
```

## Включить автозапуск из терминала

```bash
./run_lubuntu_vk_tunnel.sh --enable-autostart
```

Автозапуск создаётся как user-service:

```bash
systemctl --user status vangrapf-proxy-vk-tunnel.service
```

При каждом старте service скрипт снова обновляет Python-пакеты в `.venv` и локальный `@vkontakte/vk-tunnel`, затем запускает proxy и tunnel.

## API Endpoints

Check health:

```bash
curl http://127.0.0.1:5000/health
```

Doc:

```bash
curl http://127.0.0.1:5000/ | jq
```

Download video:

```bash
curl -X POST http://127.0.0.1:5000/download -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}' --output video.mp4
```

Search:

```bash
curl -X POST http://127.0.0.1:5000/search -H "Content-Type: application/json" -d '{"query":"музыка"}' | jq
```

Watch:

```bash
mpv 'http://127.0.0.1:5000/stream?url=https://www.youtube.com/watch?v=9jF2Hvv8j7s&quality=best'
```

For public access, use the VK Tunnel URL printed by the launcher instead of `http://127.0.0.1:5000`.

If YouTube requires cookies, set `YOUTUBE_COOKIES` before launch.
