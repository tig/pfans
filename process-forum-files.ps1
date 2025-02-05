# Script to process .htm files in PorscheFans directory and create JSON output

$outputDir = "./output"
$outputFile = "$outputDir/forum_posts.json"
$baseDir = "./PorscheFans"
# $maxFiles = 200  # Uncomment and set to limit the number of files processed

# Create output directory if it doesn't exist
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

Write-Host "Creating index in: $outputFile$(if($maxFiles){" (limited to $maxFiles files)"})"

# Get all .htm files recursively
$files = Get-ChildItem -Path $baseDir -Filter "*.htm" -Recurse
if ($maxFiles) {
    $files = $files | Select-Object -First $maxFiles
}

# Create array to hold all records
$records = @()

foreach ($file in $files) {
    Write-Host "." -NoNewline
    # Get relative path segments
    $relativePath = $file.FullName.Replace((Resolve-Path $baseDir).Path, '').TrimStart('\', '/')
    $pathSegments = $relativePath.Split([IO.Path]::DirectorySeparatorChar)
    
    # Read the HTML content
    $htmlContent = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    
    # Create record object
    $record = @{
        subforum = $pathSegments[0]  # First folder level is subforum
        date = $pathSegments[1]      # Second folder level is date
        filename = $file.Name
        fullPath = $relativePath
        sizeBytes = $file.Length
        lastModified = $file.LastWriteTime.ToString('o')  # ISO 8601 format
        content = $htmlContent
    }
    
    $records += $record
}

Write-Host "`nConverting to JSON..."
# Convert to JSON and save
$records | ConvertTo-Json -Depth 10 -Compress | Set-Content -Path $outputFile -Encoding UTF8

Write-Host "Processed $($records.Count) files. Output saved to $outputFile" 