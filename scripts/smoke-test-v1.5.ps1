<#
.SYNOPSIS
  v1.5 代理端點 smoke test — 驗證 X-SDK-Key + X-User-Token + X-Project-Code 三因子認證。

.DESCRIPTION
  跑 6 個 case 涵蓋 happy path 與各種 4xx 錯誤分支:
    1. ✅ 三個 header 齊全          → 200 success
    2. ❌ 缺 X-Project-Code          → 400 project_code_required
    3. ❌ X-Project-Code 對不到專案  → 400 project_invalid
    4. ❌ 缺 X-SDK-Key                → 401 unauthorized
    5. ❌ 缺 X-User-Token             → 401 unauthorized
    6. ✅ GET /api/v1/models(公開)  → 200 模型清單

.EXAMPLE
  .\scripts\smoke-test-v1.5.ps1 `
    -SdkKey 'ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' `
    -UserToken 'gAAAAA...' `
    -ProjectCode '53299897503322112' `
    -Model 'openai/gpt-4o-mini'

.PARAMETER ApiBase
  代理端 base URL。預設 http://localhost:8800

.PARAMETER SdkKey
  X-SDK-Key 明文(必填)。

.PARAMETER UserToken
  X-User-Token 加密字串(必填)。

.PARAMETER ProjectCode
  X-Project-Code(專案管理頁的「代碼」欄,必填)。

.PARAMETER Model
  測試呼叫使用的模型 id。預設 openai/gpt-4o-mini(請先在後台確認該模型已啟用)。
#>
[CmdletBinding()]
param(
    [string]$ApiBase = 'http://localhost:8800',
    [Parameter(Mandatory = $true)][string]$SdkKey,
    [Parameter(Mandatory = $true)][string]$UserToken,
    [Parameter(Mandatory = $true)][string]$ProjectCode,
    [string]$Model = 'openai/gpt-4o-mini'
)

$ErrorActionPreference = 'Continue'

$ChatUrl   = "$ApiBase/api/v1/model/chat"
$ModelsUrl = "$ApiBase/api/v1/models"
$Body      = @{ model = $Model; text = 'smoke test ping' } | ConvertTo-Json -Compress

$Results = [System.Collections.Generic.List[object]]::new()

function Invoke-Case {
    param(
        [string]$Name,
        [hashtable]$Headers,
        [int]$ExpectedStatus,
        [string]$ExpectedDetailContains = $null,
        [string]$Method = 'POST',
        [string]$Url = $ChatUrl,
        [string]$RequestBody = $Body
    )
    Write-Host ""
    Write-Host "── $Name " -NoNewline
    Write-Host "(expect $ExpectedStatus)" -ForegroundColor DarkGray

    try {
        $params = @{
            Uri                = $Url
            Method             = $Method
            Headers            = $Headers
            SkipHttpErrorCheck = $true
            TimeoutSec         = 60
        }
        if ($Method -ne 'GET') {
            $params['Body']        = $RequestBody
            $params['ContentType'] = 'application/json'
        }
        $resp = Invoke-WebRequest @params
        $status = [int]$resp.StatusCode
        $payload = $null
        try { $payload = $resp.Content | ConvertFrom-Json } catch { }
        $detail = if ($payload) { $payload.detail } else { '(no body)' }

        $pass = ($status -eq $ExpectedStatus) -and `
                ([string]::IsNullOrEmpty($ExpectedDetailContains) -or `
                 ($detail -and $detail.ToString().Contains($ExpectedDetailContains)))

        if ($pass) {
            Write-Host "   PASS" -ForegroundColor Green -NoNewline
            Write-Host " · HTTP $status · detail=$detail"
        } else {
            Write-Host "   FAIL" -ForegroundColor Red -NoNewline
            Write-Host " · HTTP $status · detail=$detail"
            if ($payload) {
                $payload | ConvertTo-Json -Depth 4 | Write-Host -ForegroundColor DarkGray
            }
        }
        $Results.Add([pscustomobject]@{ Case = $Name; Pass = $pass; Status = $status; Detail = $detail }) | Out-Null
    }
    catch {
        Write-Host "   FAIL" -ForegroundColor Red -NoNewline
        Write-Host " · 例外: $($_.Exception.Message)"
        $Results.Add([pscustomobject]@{ Case = $Name; Pass = $false; Status = -1; Detail = $_.Exception.Message }) | Out-Null
    }
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " DF-OpenRouter-Dispatch v1.5 smoke test" -ForegroundColor Cyan
Write-Host " API: $ApiBase" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Case 1: happy path
Invoke-Case `
    -Name '1. 三 header 齊全' `
    -Headers @{
        'X-SDK-Key'       = $SdkKey
        'X-User-Token'    = $UserToken
        'X-Project-Code'  = $ProjectCode
    } `
    -ExpectedStatus 200 `
    -ExpectedDetailContains 'success'

# Case 2: 缺 X-Project-Code
Invoke-Case `
    -Name '2. 缺 X-Project-Code' `
    -Headers @{
        'X-SDK-Key'    = $SdkKey
        'X-User-Token' = $UserToken
    } `
    -ExpectedStatus 400 `
    -ExpectedDetailContains 'project_code_required'

# Case 3: X-Project-Code 不存在
Invoke-Case `
    -Name '3. X-Project-Code 無效' `
    -Headers @{
        'X-SDK-Key'       = $SdkKey
        'X-User-Token'    = $UserToken
        'X-Project-Code'  = '00000000000000000'
    } `
    -ExpectedStatus 400 `
    -ExpectedDetailContains 'project_invalid'

# Case 4: 缺 X-SDK-Key
Invoke-Case `
    -Name '4. 缺 X-SDK-Key' `
    -Headers @{
        'X-User-Token'    = $UserToken
        'X-Project-Code'  = $ProjectCode
    } `
    -ExpectedStatus 401 `
    -ExpectedDetailContains 'unauthorized'

# Case 5: 缺 X-User-Token
Invoke-Case `
    -Name '5. 缺 X-User-Token' `
    -Headers @{
        'X-SDK-Key'       = $SdkKey
        'X-Project-Code'  = $ProjectCode
    } `
    -ExpectedStatus 401 `
    -ExpectedDetailContains 'unauthorized'

# Case 6: 公開模型清單(不需任何 header)
Invoke-Case `
    -Name '6. GET /models (公開)' `
    -Headers @{} `
    -ExpectedStatus 200 `
    -ExpectedDetailContains 'success' `
    -Method 'GET' `
    -Url $ModelsUrl

# 摘要
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Summary" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
$pass = ($Results | Where-Object Pass).Count
$total = $Results.Count
foreach ($r in $Results) {
    $color = if ($r.Pass) { 'Green' } else { 'Red' }
    $mark  = if ($r.Pass) { 'PASS' } else { 'FAIL' }
    Write-Host ("  [{0}] HTTP {1,-3}  {2}" -f $mark, $r.Status, $r.Case) -ForegroundColor $color
}
Write-Host ""
Write-Host (" {0} / {1} passed" -f $pass, $total) -ForegroundColor $(if ($pass -eq $total) { 'Green' } else { 'Yellow' })
Write-Host ""

if ($pass -eq $total) {
    Write-Host " ✅ 全部通過 — v1.5 代理鏈運作正常。" -ForegroundColor Green
    exit 0
} else {
    Write-Host " ❌ 部分 case 失敗 — 請檢視上方輸出。" -ForegroundColor Red
    exit 1
}
