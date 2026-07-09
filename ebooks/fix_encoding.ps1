$path = "C:\Users\marce\Desktop\sitodefinitivo\ebooks\Il_Ritiro_Nella_Selva.html"
$bytes = [System.IO.File]::ReadAllBytes($path)

# Decode as UTF-8 to get the actual string content
$utf8 = [System.Text.Encoding]::UTF8
$content = $utf8.GetString($bytes)

# Define all corrupted character replacements
# The file has mojibake: UTF-8 bytes decoded as Latin-1 then re-encoded
# Common patterns in this file:
# 0xC3 0xA0 (à) displayed as Ã  
# 0xC3 0xA8 (è) displayed as Ã¨
# 0xC3 0xA9 (é) displayed as Ã©
# 0xC3 0xAC (ì) displayed as Ã¬
# 0xC3 0xB2 (ò) displayed as Ã²
# 0xC3 0xB9 (ù) displayed as Ã¹

# Let me check the raw bytes for actual corrupted characters
Write-Host "Scanning for byte-level corruption patterns..."
$count = 0
for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
    # Check if byte at $i is 0xC3 (start of 2-byte UTF-8 sequence)
    if ($bytes[$i] -eq 0xC3) {
        $next = $bytes[$i+1]
        $isValidItalian = $next -eq 0xA0 -or $next -eq 0xA8 -or $next -eq 0xA9 -or $next -eq 0xAC -or $next -eq 0xB2 -or $next -eq 0xB9 -or $next -eq 0x88 -or $next -eq 0x89 -or $next -eq 0x8C -or $next -eq 0x92 -or $next -eq 0x99 -or $next -eq 0x98
        if (-not $isValidItalian -and $next -ge 0x80) {
            if ($count -lt 10) {
                $ctxStart = [Math]::Max(0, $i - 20)
                $ctxEnd = [Math]::Min($bytes.Length, $i + 10)
                $ctxBytes = $bytes[$ctxStart..$ctxEnd]
                $ctxStr = $utf8.GetString($ctxBytes)
                Write-Host "Suspicious byte at $i: 0xC3 0x$($next.ToString('X2')) context: ...$ctxStr..."
            }
            $count++
        }
    }
}
Write-Host "Total suspicious 0xC3 sequences: $count"

# Now let's see what the text actually looks like around known Italian words
# Search for "cos" which should be "così" or "cosA�" if corrupted
$searchWords = @("cos", "perch", "onest", "sincerit", "Pucallpa", "significa", "attraverso")
foreach ($word in $searchWords) {
    $idx = $content.IndexOf($word, [System.StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0) {
        $ctxLen = [Math]::Min(40, $content.Length - $idx)
        $ctx = $content.Substring($idx, $ctxLen)
        Write-Host "Found '$word' at $idx: '$ctx'"
    }
}

# Also check for known HTML entities that might be corrupted
$htmlEntities = @("&agrave;", "&egrave;", "&igrave;", "&ograve;", "&ugrave;", "&eacute;")
foreach ($ent in $htmlEntities) {
    $c = [regex]::Matches($content, [regex]::Escape($ent)).Count
    if ($c -gt 0) { Write-Host "HTML entity '$ent' found $c times" }
}
