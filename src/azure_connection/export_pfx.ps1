param (
    [string]$Subject = "*YourCertificateSubject*",
    [string]$OutputPath = "$env:TEMP\\output.pfx"
)

$certs = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -like $Subject }
$cert = $certs[0]
$password = New-Object -TypeName System.Security.SecureString
Export-PfxCertificate -Cert $cert -FilePath $OutputPath -Password $password
Write-Output "Exported to $OutputPath"
