# Script to process mailing list archives and create JSON output

$outputDir = "./output"
$outputFile = "$outputDir/mailing_list_archive.json"
$baseDir = "./PorscheFans"
$maxFiles = 1000  # Uncomment and set to limit number of files processed

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
    
    # Read the HTML content
    $htmlContent = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    
    # Extract metadata from META tags
    $metadata = @{}
    foreach ($prop in @('To', 'From', 'Subject', 'Date', 'Organization', 'Reply-to')) {
        if ($htmlContent -match "<META NAME=`"MsgProp$prop`" CONTENT=`"(.*?)`">") {
            $metadata[$prop.ToLower()] = $matches[1]
        }
    }
    
    # Get message body (everything after </HEAD><BODY> and before </BODY>)
    $body = ""
    if ($htmlContent -match "(?s)</HEAD><BODY>(.*?)</BODY>") {
        $body = $matches[1].Trim()
    }
    
    # Create record object
    $record = @{
        filename = $file.Name
        folder = $file.Directory.Name
        subforum = $file.Directory.Parent.Name
        metadata = $metadata
        body = $body
        path = $file.FullName.Replace((Resolve-Path $baseDir).Path, '').TrimStart('\', '/')
    }
    
    $records += $record
}

Write-Host "`nConverting to JSON..."
# Convert to JSON and save
$records | ConvertTo-Json -Depth 10 -Compress | Set-Content -Path $outputFile -Encoding UTF8

Write-Host "Processed $($records.Count) files. Output saved to $outputFile" 