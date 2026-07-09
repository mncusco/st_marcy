$path = "C:\Users\marce\Desktop\sitodefinitivo\ebooks\Il_Ritiro_Nella_Selva.html"
$bytes = [System.IO.File]::ReadAllBytes($path)
$utf8 = New-Object System.Text.UTF8Encoding $false
$content = $utf8.GetString($bytes)

# Check for double-encoded mojibake
# Real Italian accented chars in UTF-8:
# à = 0xC3 0xA0, è = 0xC3 0xA8, é = 0xC3 0xA9
# ì = 0xC3 0xAC, ò = 0xC3 0xB2, ù = 0xC3 0xB9
# If double-encoded, they'd appear as two sequential UTF-8 sequences

$corruptCount = 0
for ($i = 0; $i -lt $bytes.Length - 3; $i++) {
    if ($bytes[$i] -eq 0xC3) {
        $b1 = $bytes[$i+1]
        # These are the bytes that would appear if UTF-8 was decoded as Latin-1 then re-encoded
        # 0xC3 0x82 = Ã‚ (from à double-encoded: à → 0xC3 0xA0 → Latin-1 Ã  → UTF-8 0xC3 0x82 0xC3 0xA0)
        if ($b1 -eq 0x82 -or $b1 -eq 0x87 -or $b1 -eq 0x8A -or $b1 -eq 0x8E) {
            $corruptCount++
            if ($corruptCount -le 3) {
                $ctxStart = [Math]::Max(0, $i - 8)
                $ctxBytes = $bytes[$ctxStart..[Math]::Min($i+6, $bytes.Length-1)]
                $ctxStr = $utf8.GetString($ctxBytes)
                Write-Output ("CORRUPT at byte " + $i + ": C3 " + $b1.ToString("X2") + " context: " + $ctxStr)
            }
        }
    }
}
if ($corruptCount -eq 0) {
    Write-Output "No double-encoded corruption found."
}

# Now let's look at the actual content around known Italian words
$testWords = @("cos", "onest", "perch", "sincerit")
foreach ($word in $testWords) {
    $idx = $content.IndexOf($word, [System.StringComparison]::OrdinalIgnoreCase)
    if ($idx -ge 0) {
        $len = [Math]::Min(12, $content.Length - $idx)
        $sub = $content.Substring($idx, $len)
        Write-Output ("Sample for '" + $word + "': '" + $sub + "'")
    }
}

# Check if file already has correct accented chars
$goodChars = @("à", "è", "é", "ì", "ò", "ù")
foreach ($ch in $goodChars) {
    $c = [regex]::Matches($content, $ch).Count
    if ($c -gt 0) {
        Write-Output ($ch + " (correct): " + $c + " occurrences")
    }
}

# Check for HTML entity alternatives
$entities = @("&agrave;", "&egrave;", "&igrave;", "&ograve;", "&ugrave;", "&eacute;", "&aacute;", "&oacute;", "&iacute;")
foreach ($ent in $entities) {
    $c = [regex]::Matches($content, [regex]::Escape($ent)).Count
    if ($c -gt 0) {
        Write-Output ($ent + " (HTML entity): " + $c + " occurrences")
    }
}
