# Windows Firefox → Mac Docker. Google OAuth allows HTTP only on loopback.
# Keep this window open. Ctrl+C stops the tunnel.
param(
    [string]$Mac = "red@10.37.129.2",
    [int]$Port = 8798
)

ssh -o BatchMode=yes -o ConnectTimeout=8 -o ExitOnForwardFailure=yes -N -L "127.0.0.1:${Port}:127.0.0.1:${Port}" $Mac
