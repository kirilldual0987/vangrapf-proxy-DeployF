# vangrapf-proxy-DeployF
Vangrapf proxy for Deploy-F

# API Endpoints

Check health: 

    curl https://<yourproxyadress>/health

Download video:

    curl -X POST https://<yourproxyadress>/download -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}' --output video.mp4

WARNING!!! You need add YOUTUBE_COOKIES varible to continue

# How to use it on Linux

Doc:

    curl https://<yourproxyadress>/ | jq

Health:

    curl https://<yourproxyadress>/health | jq

Search: 

    curl -X POST https://<yourproxyadress>/search -H "Content-Type: application/json" -d '{"query":"музыка"}' | jq

Download:

    curl -X POST https://<yourproxyadress>/download   -H "Content-Type: application/json"   -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'   --output video-curl.mp4

Watch:

    mpv https://<yourproxyadress>/stream?url=https://www.youtube.com/watch?v=9jF2Hvv8j7s&quality=best

For greater simplicity, use the <a href="https://github.com/vangrapf/vangrapf-cli">Vangrapf CLI</a> on Linux.

Aviable proxy <a href="https://github.com/vangrapf/proxylist">here</a>
