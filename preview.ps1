# Preview the map on this computer.
# Browsers won't run the map from a file on disk, so this starts a tiny web server for this folder,
# reachable only from this computer, and opens the map in your browser. Close this window to stop it.
param([switch]$NoBrowser)

$root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
$types = @{
  '.html' = 'text/html; charset=utf-8'; '.js' = 'text/javascript; charset=utf-8'; '.css' = 'text/css; charset=utf-8'
  '.json' = 'application/json; charset=utf-8'; '.svg' = 'image/svg+xml'; '.jpg' = 'image/jpeg'; '.png' = 'image/png'; '.md' = 'text/plain; charset=utf-8'
}

# find a free port
$listener = $null
foreach ($port in 8780..8799) {
  try { $l = New-Object System.Net.HttpListener; $l.Prefixes.Add("http://localhost:$port/"); $l.Start(); $listener = $l; break } catch { }
}
if (-not $listener) { Write-Host 'Could not find a free port between 8780 and 8799.'; Read-Host 'Press Enter to close'; exit 1 }

$url = "http://localhost:$port/index.html"
Write-Host ''
Write-Host "  The Cyber Attack Map is running at $url"
Write-Host '  Keep this window open while you look at it. Close it to stop.'
Write-Host ''
if (-not $NoBrowser) { Start-Process $url }

try {
  while ($listener.IsListening) {
    $ctx = $listener.GetContext(); $req = $ctx.Request; $res = $ctx.Response
    try {
      $rel = [Uri]::UnescapeDataString($req.Url.AbsolutePath).TrimStart('/')
      if ($rel -eq '') { $rel = 'index.html' }
      $file = [IO.Path]::GetFullPath((Join-Path $root $rel))
      if ($req.HttpMethod -ne 'GET') { $res.StatusCode = 405 }
      elseif (-not $file.StartsWith($root) -or -not (Test-Path $file -PathType Leaf)) { $res.StatusCode = 404 }
      else {
        $ext = [IO.Path]::GetExtension($file).ToLower()
        $res.ContentType = $(if ($types[$ext]) { $types[$ext] } else { 'application/octet-stream' })
        $bytes = [IO.File]::ReadAllBytes($file)
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
      }
    } catch { $res.StatusCode = 500 } finally { $res.OutputStream.Close() }
  }
} finally { $listener.Stop() }

