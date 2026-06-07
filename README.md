# vangrapf-proxy-DeployF
Vangrapf proxy for Deploy-F

Check health: 

    curl https://<yourproxyadress>/health

Download video:

    curl -X POST https://<yourproxyadress>/download -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=jNQXAC9IVRw"}' --output video.mp4
