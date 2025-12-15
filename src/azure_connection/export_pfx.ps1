param (
    [string]$Subject = "*YourCertificateSubject*",
    [string]$OutputPath = "$env:TEMP\\output.pfx"
)

$certs = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -like $Subject }

# Handle both array and single object cases
try {
    if ($certs -is [System.Collections.IEnumerable]) {
        $sorted_certs = $certs | Sort-Object NotAfter -Descending
        $cert = $sorted_certs[0]
    } else {
        $cert = $certs
    }

    $password = New-Object -TypeName System.Security.SecureString
    Export-PfxCertificate -Cert $cert -FilePath $OutputPath -Password $password
    Write-Output "Exported to $OutputPath"
}
catch {
    Write-Error "Failed to export certificate: $_"
}
