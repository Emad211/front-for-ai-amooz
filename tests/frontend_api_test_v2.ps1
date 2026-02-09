#!/usr/bin/env pwsh
# =============================================================================
# Frontend-Backend API Integration Test (v2 — PowerShell 7+ compatible)
# Tests EVERY real API endpoint that the frontend calls
# =============================================================================

$ErrorActionPreference = 'Continue'
$API = "http://localhost:8000/api"
$FRONTEND = "http://localhost:9002"
$passed = 0; $failed = 0; $skipped = 0; $total = 0

function Test-Api {
  param(
    [string]$Name,
    [string]$Method = "GET",
    [string]$Url,
    [string]$Body = $null,
    [hashtable]$Headers = @{},
    [int[]]$ExpectedStatus = @(200),
    [string]$ContentType = "application/json",
    [scriptblock]$Validate = $null
  )
  $script:total++
  try {
    $params = @{
      Method = $Method
      Uri = $Url
      Headers = $Headers
      UseBasicParsing = $true
      SkipHttpErrorCheck = $true  # PS7+: don't throw on non-2xx
    }
    if ($Body) {
      $params.Body = $Body
      $params.ContentType = $ContentType
    }
    
    $resp = Invoke-WebRequest @params
    $status = $resp.StatusCode
    $content = $resp.Content
    
    if ($ExpectedStatus -contains $status) {
      if ($Validate) {
        $json = $null
        try { $json = $content | ConvertFrom-Json -ErrorAction SilentlyContinue } catch {}
        $result = & $Validate $json $content $resp
        if ($result -eq $false) {
          $script:failed++
          Write-Host "  FAIL  $Name (status=$status but validation failed)" -ForegroundColor Red
          return @{ ok = $false; status = $status; content = $content; json = $json }
        }
      }
      $script:passed++
      Write-Host "  PASS  $Name (status=$status)" -ForegroundColor Green
      $json = $null
      try { $json = $content | ConvertFrom-Json -ErrorAction SilentlyContinue } catch {}
      return @{ ok = $true; status = $status; content = $content; json = $json }
    } else {
      $script:failed++
      $preview = if ($content.Length -gt 200) { $content.Substring(0, 200) } else { $content }
      Write-Host "  FAIL  $Name (expected=$($ExpectedStatus -join ',') got=$status)" -ForegroundColor Red
      Write-Host "        Response: $preview" -ForegroundColor DarkGray
      return @{ ok = $false; status = $status; content = $content }
    }
  } catch {
    $script:failed++
    Write-Host "  FAIL  $Name (exception: $($_.Exception.Message))" -ForegroundColor Red
    return @{ ok = $false; error = $_.Exception.Message }
  }
}

function Skip-Test {
  param([string]$Name, [string]$Reason)
  $script:total++; $script:skipped++
  Write-Host "  SKIP  $Name ($Reason)" -ForegroundColor Yellow
}

function Auth-Headers { param([string]$Token) return @{ Authorization = "Bearer $Token" } }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 1: HEALTH & CONNECTIVITY" -ForegroundColor Cyan
Write-Host "========================================`n"

Test-Api -Name "Backend health check" -Url "$API/health/" -Validate {
  param($j) $j.status -eq "healthy"
}

Test-Api -Name "Backend API docs" -Url "http://localhost:8000/api/docs/"

Test-Api -Name "CORS preflight from localhost:9002" -Method "OPTIONS" -Url "$API/token/" `
  -Headers @{ Origin = "http://localhost:9002"; "Access-Control-Request-Method" = "POST"; "Access-Control-Request-Headers" = "content-type" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 2: FRONTEND PAGES (Public)" -ForegroundColor Cyan
Write-Host "========================================`n"

@("/" , "/start", "/login", "/admin-login", "/join-code", "/teacher-signup") | ForEach-Object {
  Test-Api -Name "Frontend $_" -Url "$FRONTEND$_"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 3: TEACHER REGISTRATION" -ForegroundColor Cyan
Write-Host "========================================`n"

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

# Lowercase role
$teacherBody = @{ username="ftTeacher_$ts"; password="TestPass123!"; email="ft_$ts@test.com"; first_name="FT"; last_name="Teacher"; phone="0912$($ts % 10000000)"; role="teacher" } | ConvertTo-Json
$regResult = Test-Api -Name "Register teacher (lowercase)" -Method "POST" -Url "$API/auth/register/" -Body $teacherBody -ExpectedStatus @(201) -Validate { param($j) $j.tokens.access -and $j.user.role -eq "TEACHER" }

$teacherAccess = $null; $teacherRefresh = $null
if ($regResult.ok) { $teacherAccess = $regResult.json.tokens.access; $teacherRefresh = $regResult.json.tokens.refresh }

# Uppercase role
$ts2 = $ts + 1
$teacherBody2 = @{ username="ftTeacher2_$ts2"; password="TestPass123!"; email="ft2_$ts2@test.com"; first_name="FT2"; last_name="Teacher2"; phone="0913$($ts2 % 10000000)"; role="TEACHER" } | ConvertTo-Json
Test-Api -Name "Register teacher (uppercase)" -Method "POST" -Url "$API/auth/register/" -Body $teacherBody2 -ExpectedStatus @(201)

# Invalid role
$badRole = @{ username="badRole_$ts"; password="TestPass123!"; email="bad_$ts@test.com"; role="superadmin" } | ConvertTo-Json
Test-Api -Name "Register with invalid role" -Method "POST" -Url "$API/auth/register/" -Body $badRole -ExpectedStatus @(400)

# Weak password
$weakPw = @{ username="weakpw_$ts"; password="123"; email="weak_$ts@test.com"; role="student" } | ConvertTo-Json
Test-Api -Name "Register with weak password" -Method "POST" -Url "$API/auth/register/" -Body $weakPw -ExpectedStatus @(400)

# Duplicate username
$dupBody = @{ username="ftTeacher_$ts"; password="TestPass123!"; email="dup_$ts@test.com"; role="teacher" } | ConvertTo-Json
Test-Api -Name "Register duplicate username" -Method "POST" -Url "$API/auth/register/" -Body $dupBody -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 4: LOGIN / TOKEN" -ForegroundColor Cyan
Write-Host "========================================`n"

$loginBody = @{ username="ftTeacher_$ts"; password="TestPass123!" } | ConvertTo-Json
$loginResult = Test-Api -Name "Login teacher" -Method "POST" -Url "$API/token/" -Body $loginBody -ExpectedStatus @(200) -Validate { param($j) $j.access -and $j.refresh }
if ($loginResult.ok) { $teacherAccess = $loginResult.json.access; $teacherRefresh = $loginResult.json.refresh }

# Token refresh
if ($teacherRefresh) {
  $refreshResult = Test-Api -Name "Token refresh" -Method "POST" -Url "$API/token/refresh/" -Body (@{ refresh=$teacherRefresh } | ConvertTo-Json) -ExpectedStatus @(200) -Validate { param($j) $j.access }
  if ($refreshResult.ok) {
    $teacherAccess = $refreshResult.json.access
    # When ROTATE_REFRESH_TOKENS is enabled, the response includes a new refresh token
    if ($refreshResult.json.refresh) { $teacherRefresh = $refreshResult.json.refresh }
  }
}

# Invalid credentials
Test-Api -Name "Login wrong password" -Method "POST" -Url "$API/token/" -Body '{"username":"noone","password":"wrong"}' -ExpectedStatus @(401)
Test-Api -Name "Login empty body" -Method "POST" -Url "$API/token/" -Body '{}' -ExpectedStatus @(400)
Test-Api -Name "Login malformed JSON" -Method "POST" -Url "$API/token/" -Body "not json" -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 5: ACCOUNTS / ME" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "GET /accounts/me/" -Url "$API/accounts/me/" -Headers $h -Validate { param($j) $j.role -eq "TEACHER" -and $j.username }
  Test-Api -Name "PATCH /accounts/me/" -Method "PATCH" -Url "$API/accounts/me/" -Headers $h -Body '{"first_name":"Updated","bio":"Test bio"}' -ContentType "application/json" -Validate { param($j) $j.first_name -eq "Updated" }
  Test-Api -Name "GET /accounts/me/ no auth" -Url "$API/accounts/me/" -ExpectedStatus @(401)
  Test-Api -Name "GET /accounts/me/ bad token" -Url "$API/accounts/me/" -Headers @{ Authorization="Bearer bad.token.here" } -ExpectedStatus @(401)
} else { Skip-Test "Accounts tests" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 6: STUDENT REGISTRATION & LOGIN" -ForegroundColor Cyan
Write-Host "========================================`n"

$sTs = $ts + 100
$studentBody = @{ username="ftStudent_$sTs"; password="StudentPass123!"; email="fts_$sTs@test.com"; first_name="FT"; last_name="Student"; phone="0914$($sTs % 10000000)"; role="student" } | ConvertTo-Json
$studentReg = Test-Api -Name "Register student" -Method "POST" -Url "$API/auth/register/" -Body $studentBody -ExpectedStatus @(201) -Validate { param($j) $j.user.role -eq "STUDENT" }

$studentAccess = $null; $studentRefresh = $null
if ($studentReg.ok) { $studentAccess = $studentReg.json.tokens.access; $studentRefresh = $studentReg.json.tokens.refresh }

$studentLoginBody = @{ username="ftStudent_$sTs"; password="StudentPass123!" } | ConvertTo-Json
$studentLogin = Test-Api -Name "Student login" -Method "POST" -Url "$API/token/" -Body $studentLoginBody -ExpectedStatus @(200)
if ($studentLogin.ok) { $studentAccess = $studentLogin.json.access; $studentRefresh = $studentLogin.json.refresh }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 7: TEACHER ANALYTICS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "Analytics stats" -Url "$API/classes/teacher/analytics/stats/" -Headers $h
  Test-Api -Name "Analytics stats (30d)" -Url "$API/classes/teacher/analytics/stats/?days=30" -Headers $h
  Test-Api -Name "Analytics chart" -Url "$API/classes/teacher/analytics/chart/" -Headers $h
  Test-Api -Name "Analytics chart (90d)" -Url "$API/classes/teacher/analytics/chart/?days=90" -Headers $h
  Test-Api -Name "Analytics distribution" -Url "$API/classes/teacher/analytics/distribution/" -Headers $h
  Test-Api -Name "Analytics activities" -Url "$API/classes/teacher/analytics/activities/" -Headers $h
  Test-Api -Name "Analytics CSV export" -Url "$API/classes/teacher/analytics/export-csv/" -Headers $h
} else { Skip-Test "Teacher analytics" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 8: TEACHER STUDENTS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "Teacher students list" -Url "$API/classes/teacher/students/" -Headers $h
} else { Skip-Test "Teacher students" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 9: CLASS CREATION SESSIONS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  $sessResult = Test-Api -Name "List creation sessions" -Url "$API/classes/creation-sessions/" -Headers $h
  
  if ($sessResult.ok -and $sessResult.json -and $sessResult.json.Count -gt 0) {
    $sessId = $sessResult.json[0].id
    Test-Api -Name "Session detail ($sessId)" -Url "$API/classes/creation-sessions/$sessId/" -Headers $h
    Test-Api -Name "Session invites ($sessId)" -Url "$API/classes/creation-sessions/$sessId/invites/" -Headers $h
    Test-Api -Name "Session announcements ($sessId)" -Url "$API/classes/creation-sessions/$sessId/announcements/" -Headers $h
    Test-Api -Name "Session prerequisites ($sessId)" -Url "$API/classes/creation-sessions/$sessId/prerequisites/" -Headers $h
  } else {
    Skip-Test "Session detail tests" "No sessions exist"
  }

  Test-Api -Name "Nonexistent session 404" -Url "$API/classes/creation-sessions/99999/" -Headers $h -ExpectedStatus @(404)
} else { Skip-Test "Creation sessions" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 10: EXAM PREP SESSIONS (Teacher)" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  $examSess = Test-Api -Name "List exam prep sessions" -Url "$API/classes/exam-prep-sessions/" -Headers $h

  if ($examSess.ok -and $examSess.json -and $examSess.json.Count -gt 0) {
    $eid = $examSess.json[0].id
    Test-Api -Name "Exam prep session detail ($eid)" -Url "$API/classes/exam-prep-sessions/$eid/" -Headers $h
    Test-Api -Name "Exam prep invites ($eid)" -Url "$API/classes/exam-prep-sessions/$eid/invites/" -Headers $h
    Test-Api -Name "Exam prep announcements ($eid)" -Url "$API/classes/exam-prep-sessions/$eid/announcements/" -Headers $h
  } else {
    Skip-Test "Exam prep detail tests" "No exam prep sessions"
  }
} else { Skip-Test "Exam prep sessions" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 11: STUDENT ENDPOINTS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($studentAccess) {
  $h = Auth-Headers $studentAccess
  Test-Api -Name "Student courses" -Url "$API/classes/student/courses/" -Headers $h
  Test-Api -Name "Student exam preps" -Url "$API/classes/student/exam-preps/" -Headers $h
  Test-Api -Name "Student notifications" -Url "$API/classes/student/notifications/" -Headers $h

  # Role isolation: student cannot access teacher endpoints
  Test-Api -Name "Student -> teacher analytics (403)" -Url "$API/classes/teacher/analytics/stats/" -Headers $h -ExpectedStatus @(403)
  Test-Api -Name "Student -> teacher students (403)" -Url "$API/classes/teacher/students/" -Headers $h -ExpectedStatus @(403)
  Test-Api -Name "Student -> creation sessions (403)" -Url "$API/classes/creation-sessions/" -Headers $h -ExpectedStatus @(403)
} else { Skip-Test "Student endpoints" "No student token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 12: NOTIFICATIONS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "Teacher notifications" -Url "$API/notifications/teacher/" -Headers $h
  Test-Api -Name "Mark all read" -Method "POST" -Url "$API/notifications/read-all/" -Headers $h -Body '{}' -ContentType "application/json"
} else { Skip-Test "Notification tests" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 13: ADMIN ISOLATION" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "Teacher -> admin recipients (403)" -Url "$API/notifications/admin/recipients/" -Headers $h -ExpectedStatus @(403)
  Test-Api -Name "Teacher -> admin broadcast (403)" -Method "POST" -Url "$API/notifications/admin/broadcast/" -Headers $h -Body '{"message":"test"}' -ContentType "application/json" -ExpectedStatus @(403)
}

if ($studentAccess) {
  $h = Auth-Headers $studentAccess
  Test-Api -Name "Student -> admin recipients (403)" -Url "$API/notifications/admin/recipients/" -Headers $h -ExpectedStatus @(403)
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 14: PASSWORD CHANGE" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  
  # Change password
  $cpBody = @{ old_password="TestPass123!"; new_password="NewTestPass456!" } | ConvertTo-Json
  $cpResult = Test-Api -Name "Change password" -Method "POST" -Url "$API/auth/password-change/" -Headers $h -Body $cpBody -ContentType "application/json" -ExpectedStatus @(200)

  if ($cpResult.ok) {
    # New password works
    $newLoginBody = @{ username="ftTeacher_$ts"; password="NewTestPass456!" } | ConvertTo-Json
    $newLogin = Test-Api -Name "Login with new password" -Method "POST" -Url "$API/token/" -Body $newLoginBody -ExpectedStatus @(200) -Validate { param($j) $j.access }
    if ($newLogin.ok) { $teacherAccess = $newLogin.json.access; $teacherRefresh = $newLogin.json.refresh }

    # Old password should fail
    $oldLoginBody = @{ username="ftTeacher_$ts"; password="TestPass123!" } | ConvertTo-Json
    Test-Api -Name "Old password rejected" -Method "POST" -Url "$API/token/" -Body $oldLoginBody -ExpectedStatus @(401)
  } else {
    Skip-Test "Password change follow-ups" "Change password failed"
  }

  # Wrong old password
  $wrongOldBody = @{ old_password="WrongOld123!"; new_password="Whatever123!" } | ConvertTo-Json
  Test-Api -Name "Change password wrong old" -Method "POST" -Url "$API/auth/password-change/" -Headers (Auth-Headers $teacherAccess) -Body $wrongOldBody -ContentType "application/json" -ExpectedStatus @(400)
} else { Skip-Test "Password change" "No teacher token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 15: INVITE LOGIN" -ForegroundColor Cyan
Write-Host "========================================`n"

Test-Api -Name "Invite login invalid code" -Method "POST" -Url "$API/auth/invite-login/" -Body '{"code":"INVALID123","phone":"09120000000"}' -ExpectedStatus @(400, 404)
Test-Api -Name "Invite login missing phone" -Method "POST" -Url "$API/auth/invite-login/" -Body '{"code":"INVALID123"}' -ExpectedStatus @(400)
Test-Api -Name "Invite login empty body" -Method "POST" -Url "$API/auth/invite-login/" -Body '{}' -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 16: LOGOUT & TOKEN BLACKLIST" -ForegroundColor Cyan
Write-Host "========================================`n"

# Get a fresh token pair specifically for logout test (previous tokens may have been rotated)
$logoutPwd = if ($cpResult -and $cpResult.ok) { "NewTestPass456!" } else { "TestPass123!" }
$logoutLoginBody = @{ username="ftTeacher_$ts"; password=$logoutPwd } | ConvertTo-Json
$logoutLogin = Test-Api -Name "Re-login for logout test" -Method "POST" -Url "$API/token/" -Body $logoutLoginBody -ExpectedStatus @(200) -Validate { param($j) $j.access -and $j.refresh }
if ($logoutLogin.ok) {
  $logoutAccess = $logoutLogin.json.access
  $logoutRefresh = $logoutLogin.json.refresh
} else {
  $logoutAccess = $teacherAccess
  $logoutRefresh = $teacherRefresh
}

if ($logoutRefresh) {
  $logoutBody = @{ refresh=$logoutRefresh } | ConvertTo-Json
  Test-Api -Name "Logout (blacklist refresh)" -Method "POST" -Url "$API/auth/logout/" -Headers (Auth-Headers $logoutAccess) -Body $logoutBody -ContentType "application/json" -ExpectedStatus @(200, 204, 205)
  
  # Blacklisted refresh token should fail
  Test-Api -Name "Refresh blacklisted token (401)" -Method "POST" -Url "$API/token/refresh/" -Body (@{ refresh=$logoutRefresh } | ConvertTo-Json) -ExpectedStatus @(401)
} else { Skip-Test "Logout tests" "No refresh token" }

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 17: CORS VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================`n"

@("/token/", "/auth/register/", "/accounts/me/", "/classes/creation-sessions/") | ForEach-Object {
  Test-Api -Name "CORS preflight $_" -Method "OPTIONS" -Url "$API$_" `
    -Headers @{ Origin="http://localhost:9002"; "Access-Control-Request-Method"="POST"; "Access-Control-Request-Headers"="content-type,authorization" } -Validate {
    param($j, $c, $resp) 
    $acao = $resp.Headers["Access-Control-Allow-Origin"]
    if ($acao -is [array]) { $acao = $acao[0] }
    $acao -and ($acao -eq "http://localhost:9002" -or $acao -eq "*")
  }
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 18: ERROR HANDLING" -ForegroundColor Cyan
Write-Host "========================================`n"

Test-Api -Name "404 nonexistent endpoint" -Url "$API/doesnt/exist/" -ExpectedStatus @(404)
Test-Api -Name "405 wrong method" -Method "DELETE" -Url "$API/token/" -ExpectedStatus @(405)
Test-Api -Name "Register missing required fields" -Method "POST" -Url "$API/auth/register/" -Body '{"role":"student"}' -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 19: FRONTEND PROTECTED PAGES" -ForegroundColor Cyan
Write-Host "========================================`n"

@("/home", "/classes", "/teacher", "/teacher/analytics", "/teacher/create-class",
  "/teacher/my-classes", "/teacher/my-exams", "/teacher/students", "/teacher/settings",
  "/exam-prep", "/notifications", "/profile", "/admin/maintenance") | ForEach-Object {
  Test-Api -Name "Frontend $_" -Url "$FRONTEND$_" -ExpectedStatus @(200, 302, 307)
}

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "           TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Total:   $total" -ForegroundColor White
Write-Host "  Passed:  $passed" -ForegroundColor Green
Write-Host "  Failed:  $failed" -ForegroundColor $(if ($failed -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped: $skipped" -ForegroundColor $(if ($skipped -gt 0) { "Yellow" } else { "Green" })
Write-Host "========================================`n" -ForegroundColor Cyan

if ($failed -gt 0) {
  Write-Host "SOME TESTS FAILED!" -ForegroundColor Red
  exit 1
} else {
  Write-Host "ALL TESTS PASSED!" -ForegroundColor Green
  exit 0
}
