#!/usr/bin/env pwsh
# =============================================================================
# Frontend-Backend API Integration Test
# Tests EVERY real API endpoint that the frontend calls
# Simulates the exact same HTTP calls the browser would make
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
      ErrorAction = 'Stop'
    }
    if ($Body) {
      $params.Body = $Body
      $params.ContentType = $ContentType
    }
    # UseBasicParsing avoids IE rendering
    $resp = Invoke-WebRequest @params -UseBasicParsing -MaximumRedirection 0 2>&1
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
      Write-Host "  FAIL  $Name (expected=$($ExpectedStatus -join ',') got=$status)" -ForegroundColor Red
      Write-Host "        Response: $($content.Substring(0, [Math]::Min(200, $content.Length)))" -ForegroundColor DarkGray
      return @{ ok = $false; status = $status; content = $content }
    }
  } catch {
    $ex = $_.Exception
    if ($ex.Response) {
      $status = [int]$ex.Response.StatusCode
      $reader = [System.IO.StreamReader]::new($ex.Response.GetResponseStream())
      $content = $reader.ReadToEnd()
      $reader.Close()
      if ($ExpectedStatus -contains $status) {
        $script:passed++
        Write-Host "  PASS  $Name (status=$status)" -ForegroundColor Green
        $json = $null
        try { $json = $content | ConvertFrom-Json -ErrorAction SilentlyContinue } catch {}
        return @{ ok = $true; status = $status; content = $content; json = $json }
      }
      $script:failed++
      Write-Host "  FAIL  $Name (expected=$($ExpectedStatus -join ',') got=$status)" -ForegroundColor Red
      Write-Host "        Error: $($content.Substring(0, [Math]::Min(200, $content.Length)))" -ForegroundColor DarkGray
      return @{ ok = $false; status = $status; content = $content }
    }
    $script:failed++
    Write-Host "  FAIL  $Name (exception: $($ex.Message))" -ForegroundColor Red
    return @{ ok = $false; error = $ex.Message }
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

Test-Api -Name "Backend API root (docs)" -Url "http://localhost:8000/api/docs/" -ExpectedStatus @(200)

# Test CORS preflight from frontend origin
$r = Test-Api -Name "CORS preflight from localhost:9002" -Method "OPTIONS" -Url "$API/token/" `
  -Headers @{ Origin = "http://localhost:9002"; "Access-Control-Request-Method" = "POST"; "Access-Control-Request-Headers" = "content-type" } `
  -ExpectedStatus @(200)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 2: FRONTEND PAGES" -ForegroundColor Cyan
Write-Host "========================================`n"

$frontendPages = @(
  @{ name = "Landing page (/)"; path = "/" },
  @{ name = "Start page (/start)"; path = "/start" },
  @{ name = "Login page (/login)"; path = "/login" },
  @{ name = "Admin login (/admin-login)"; path = "/admin-login" },
  @{ name = "Join code (/join-code)"; path = "/join-code" },
  @{ name = "Teacher signup (/teacher-signup)"; path = "/teacher-signup" }
)

foreach ($page in $frontendPages) {
  Test-Api -Name $page.name -Url "$FRONTEND$($page.path)" -ExpectedStatus @(200)
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 3: TEACHER REGISTRATION" -ForegroundColor Cyan
Write-Host "========================================`n"

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$teacherBody = @{
  username = "test_teacher_$ts"
  password = "TestPass123!"
  email = "teacher_$ts@test.com"
  first_name = "Test"
  last_name = "Teacher"
  phone = "0912$($ts % 10000000)"
  role = "teacher"
}  | ConvertTo-Json

$regResult = Test-Api -Name "Register teacher (lowercase role)" -Method "POST" -Url "$API/auth/register/" `
  -Body $teacherBody -ExpectedStatus @(201) -Validate {
  param($j) $j.tokens -and $j.tokens.access -and $j.user
}

$teacherAccess = $null; $teacherRefresh = $null; $teacherId = $null
if ($regResult.ok) {
  $teacherAccess = $regResult.json.tokens.access
  $teacherRefresh = $regResult.json.tokens.refresh
  $teacherId = $regResult.json.user.id
}

# Register with uppercase role
$ts2 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$teacherBody2 = @{
  username = "test_teacher2_$ts2"
  password = "TestPass123!"
  email = "teacher2_$ts2@test.com"
  first_name = "Test2"
  last_name = "Teacher2"
  phone = "0913$($ts2 % 10000000)"
  role = "TEACHER"
}  | ConvertTo-Json

Test-Api -Name "Register teacher (uppercase role)" -Method "POST" -Url "$API/auth/register/" `
  -Body $teacherBody2 -ExpectedStatus @(201) -Validate {
  param($j) $j.user.role -eq "TEACHER"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 4: LOGIN / TOKEN" -ForegroundColor Cyan
Write-Host "========================================`n"

$loginBody = @{
  username = "test_teacher_$ts"
  password = "TestPass123!"
} | ConvertTo-Json

$loginResult = Test-Api -Name "Login (POST /api/token/)" -Method "POST" -Url "$API/token/" `
  -Body $loginBody -ExpectedStatus @(200) -Validate {
  param($j) $j.access -and $j.refresh
}

if ($loginResult.ok) {
  $teacherAccess = $loginResult.json.access
  $teacherRefresh = $loginResult.json.refresh
}

# Token refresh
if ($teacherRefresh) {
  $refreshBody = @{ refresh = $teacherRefresh } | ConvertTo-Json
  $refreshResult = Test-Api -Name "Token refresh" -Method "POST" -Url "$API/token/refresh/" `
    -Body $refreshBody -ExpectedStatus @(200) -Validate {
    param($j) $j.access
  }
  if ($refreshResult.ok) {
    $teacherAccess = $refreshResult.json.access
  }
}

# Invalid login
Test-Api -Name "Login with wrong password" -Method "POST" -Url "$API/token/" `
  -Body '{"username":"nonexistent","password":"wrong"}' -ExpectedStatus @(401)

# Missing fields
Test-Api -Name "Login with empty body" -Method "POST" -Url "$API/token/" `
  -Body '{}' -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 5: ACCOUNTS / ME (Teacher)" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $headers = Auth-Headers $teacherAccess

  $meResult = Test-Api -Name "GET /accounts/me/" -Url "$API/accounts/me/" -Headers $headers -Validate {
    param($j) $j.role -eq "TEACHER" -and $j.username
  }

  Test-Api -Name "PATCH /accounts/me/ (update profile)" -Method "PATCH" -Url "$API/accounts/me/" `
    -Headers ($headers + @{ "Content-Type" = "application/json" }) `
    -Body '{"first_name":"Updated","bio":"Test bio"}' -Validate {
    param($j) $j.first_name -eq "Updated"
  }

  # Unauthenticated access
  Test-Api -Name "GET /accounts/me/ without auth" -Url "$API/accounts/me/" -ExpectedStatus @(401)

  # Token with typo
  Test-Api -Name "GET /accounts/me/ with bad token" -Url "$API/accounts/me/" `
    -Headers @{ Authorization = "Bearer invalid.token.here" } -ExpectedStatus @(401)
} else {
  Skip-Test "Accounts tests" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 6: STUDENT REGISTRATION & LOGIN (Invite Flow)" -ForegroundColor Cyan
Write-Host "========================================`n"

$studentTs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$studentBody = @{
  username = "test_student_$studentTs"
  password = "StudentPass123!"
  email = "student_$studentTs@test.com"
  first_name = "Test"
  last_name = "Student"
  phone = "0914$($studentTs % 10000000)"
  role = "student"
}  | ConvertTo-Json

$studentReg = Test-Api -Name "Register student" -Method "POST" -Url "$API/auth/register/" `
  -Body $studentBody -ExpectedStatus @(201) -Validate {
  param($j) $j.user.role -eq "STUDENT"
}

$studentAccess = $null; $studentRefresh = $null; $studentId = $null
if ($studentReg.ok) {
  $studentAccess = $studentReg.json.tokens.access
  $studentRefresh = $studentReg.json.tokens.refresh
  $studentId = $studentReg.json.user.id
}

# Student login
$studentLogin = @{
  username = "test_student_$studentTs"
  password = "StudentPass123!"
} | ConvertTo-Json

$studentLoginResult = Test-Api -Name "Student login" -Method "POST" -Url "$API/token/" `
  -Body $studentLogin -ExpectedStatus @(200)

if ($studentLoginResult.ok) {
  $studentAccess = $studentLoginResult.json.access
  $studentRefresh = $studentLoginResult.json.refresh
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 7: TEACHER ANALYTICS (Real API)" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess

  Test-Api -Name "Analytics stats (default)" -Url "$API/classes/teacher/analytics/stats/" -Headers $h
  Test-Api -Name "Analytics stats (30 days)" -Url "$API/classes/teacher/analytics/stats/?days=30" -Headers $h
  Test-Api -Name "Analytics chart data" -Url "$API/classes/teacher/analytics/chart/" -Headers $h
  Test-Api -Name "Analytics chart (90 days)" -Url "$API/classes/teacher/analytics/chart/?days=90" -Headers $h
  Test-Api -Name "Analytics distribution" -Url "$API/classes/teacher/analytics/distribution/" -Headers $h
  Test-Api -Name "Analytics activities" -Url "$API/classes/teacher/analytics/activities/" -Headers $h
  Test-Api -Name "Analytics CSV export" -Url "$API/classes/teacher/analytics/export-csv/" -Headers $h
} else {
  Skip-Test "Teacher analytics" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 8: TEACHER STUDENTS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  Test-Api -Name "GET teacher students list" -Url "$API/classes/teacher/students/" -Headers $h
} else {
  Skip-Test "Teacher students" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 9: CLASS CREATION SESSIONS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess

  $sessResult = Test-Api -Name "List creation sessions" -Url "$API/classes/creation-sessions/" -Headers $h

  # If there are sessions, test detail
  if ($sessResult.ok -and $sessResult.json -and $sessResult.json.Count -gt 0) {
    $sessId = $sessResult.json[0].id
    Test-Api -Name "Get session detail ($sessId)" -Url "$API/classes/creation-sessions/$sessId/" -Headers $h
    Test-Api -Name "List session invites ($sessId)" -Url "$API/classes/creation-sessions/$sessId/invites/" -Headers $h
    Test-Api -Name "List session announcements ($sessId)" -Url "$API/classes/creation-sessions/$sessId/announcements/" -Headers $h
    Test-Api -Name "List session prerequisites ($sessId)" -Url "$API/classes/creation-sessions/$sessId/prerequisites/" -Headers $h
  } else {
    Skip-Test "Session detail tests" "No existing sessions"
  }

  # Test 404 for nonexistent session
  Test-Api -Name "Get nonexistent session" -Url "$API/classes/creation-sessions/99999/" -Headers $h -ExpectedStatus @(404)
} else {
  Skip-Test "Class creation sessions" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 10: EXAM PREP SESSIONS (Teacher)" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess

  $examSessResult = Test-Api -Name "List exam prep sessions" -Url "$API/classes/exam-prep-sessions/" -Headers $h

  if ($examSessResult.ok -and $examSessResult.json -and $examSessResult.json.Count -gt 0) {
    $examSessId = $examSessResult.json[0].id
    Test-Api -Name "Get exam prep session detail ($examSessId)" -Url "$API/classes/exam-prep-sessions/$examSessId/" -Headers $h
    Test-Api -Name "List exam prep invites ($examSessId)" -Url "$API/classes/exam-prep-sessions/$examSessId/invites/" -Headers $h
    Test-Api -Name "List exam prep announcements ($examSessId)" -Url "$API/classes/exam-prep-sessions/$examSessId/announcements/" -Headers $h
  } else {
    Skip-Test "Exam prep session detail tests" "No existing exam prep sessions"
  }
} else {
  Skip-Test "Exam prep sessions" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 11: STUDENT ENDPOINTS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($studentAccess) {
  $h = Auth-Headers $studentAccess

  Test-Api -Name "Student courses list" -Url "$API/classes/student/courses/" -Headers $h
  Test-Api -Name "Student exam preps list" -Url "$API/classes/student/exam-preps/" -Headers $h
  Test-Api -Name "Student notifications" -Url "$API/classes/student/notifications/" -Headers $h

  # Test student accessing teacher endpoints (should be forbidden)
  Test-Api -Name "Student cannot access teacher analytics" -Url "$API/classes/teacher/analytics/stats/" `
    -Headers $h -ExpectedStatus @(403)
  Test-Api -Name "Student cannot access teacher students" -Url "$API/classes/teacher/students/" `
    -Headers $h -ExpectedStatus @(403)
} else {
  Skip-Test "Student endpoints" "No student token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 12: NOTIFICATIONS" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess

  Test-Api -Name "Teacher notifications" -Url "$API/notifications/teacher/" -Headers $h

  # Mark all as read
  Test-Api -Name "Mark all notifications read" -Method "POST" -Url "$API/notifications/read-all/" `
    -Headers ($h + @{ "Content-Type" = "application/json" }) -ExpectedStatus @(200)
} else {
  Skip-Test "Notification tests" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 13: ADMIN ENDPOINTS" -ForegroundColor Cyan
Write-Host "========================================`n"

# Admin: recipients list, broadcast
if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  # Teacher should NOT have admin access
  Test-Api -Name "Teacher cannot access admin recipients" -Url "$API/notifications/admin/recipients/" `
    -Headers $h -ExpectedStatus @(403)
} else {
  Skip-Test "Admin endpoint tests" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 14: PASSWORD CHANGE" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherAccess) {
  $h = Auth-Headers $teacherAccess
  
  $changePwBody = @{
    old_password = "TestPass123!"
    new_password = "NewTestPass456!"
  } | ConvertTo-Json

  Test-Api -Name "Change password" -Method "POST" -Url "$API/accounts/change-password/" `
    -Headers ($h + @{ "Content-Type" = "application/json" }) -Body $changePwBody -ExpectedStatus @(200)

  # Login with new password
  $newLoginBody = @{
    username = "test_teacher_$ts"
    password = "NewTestPass456!"
  } | ConvertTo-Json

  $newLogin = Test-Api -Name "Login with new password" -Method "POST" -Url "$API/token/" `
    -Body $newLoginBody -ExpectedStatus @(200)

  if ($newLogin.ok) {
    $teacherAccess = $newLogin.json.access
    $teacherRefresh = $newLogin.json.refresh
  }

  # Old password should fail
  $oldLoginBody = @{
    username = "test_teacher_$ts"
    password = "TestPass123!"
  } | ConvertTo-Json

  Test-Api -Name "Old password rejected after change" -Method "POST" -Url "$API/token/" `
    -Body $oldLoginBody -ExpectedStatus @(401)
} else {
  Skip-Test "Password change tests" "No teacher token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 15: INVITE VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================`n"

# Test invite-login with invalid code  
Test-Api -Name "Invite login with invalid code" -Method "POST" -Url "$API/auth/invite-login/" `
  -Body '{"code":"INVALID123","phone":"09120000000"}' -ExpectedStatus @(400, 404)

# Test invite-login with missing fields
Test-Api -Name "Invite login missing phone" -Method "POST" -Url "$API/auth/invite-login/" `
  -Body '{"code":"INVALID123"}' -ExpectedStatus @(400)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 16: LOGOUT" -ForegroundColor Cyan
Write-Host "========================================`n"

if ($teacherRefresh) {
  $logoutBody = @{ refresh = $teacherRefresh } | ConvertTo-Json
  Test-Api -Name "Logout (blacklist refresh)" -Method "POST" -Url "$API/auth/logout/" `
    -Headers (Auth-Headers $teacherAccess) `
    -Body $logoutBody -ExpectedStatus @(200, 204, 205)

  # Verify old refresh token is blacklisted
  $refreshBody = @{ refresh = $teacherRefresh } | ConvertTo-Json
  Test-Api -Name "Refresh with blacklisted token fails" -Method "POST" -Url "$API/token/refresh/" `
    -Body $refreshBody -ExpectedStatus @(401)
} else {
  Skip-Test "Logout tests" "No refresh token"
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 17: CROSS-ORIGIN (CORS) VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================`n"

# Simulate browser CORS preflight for common API endpoints
$corsEndpoints = @("/token/", "/auth/register/", "/accounts/me/", "/classes/creation-sessions/")
foreach ($ep in $corsEndpoints) {
  Test-Api -Name "CORS preflight $ep" -Method "OPTIONS" -Url "$API$ep" `
    -Headers @{ Origin = "http://localhost:9002"; "Access-Control-Request-Method" = "POST"; "Access-Control-Request-Headers" = "content-type,authorization" } `
    -ExpectedStatus @(200) -Validate {
    param($j, $c, $resp) 
    $acaoHeader = $resp.Headers["Access-Control-Allow-Origin"]
    $acaoHeader -and ($acaoHeader -eq "http://localhost:9002" -or $acaoHeader -eq "*")
  }
}

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 18: ERROR HANDLING & EDGE CASES" -ForegroundColor Cyan
Write-Host "========================================`n"

# Malformed JSON body
Test-Api -Name "Malformed JSON to /token/" -Method "POST" -Url "$API/token/" `
  -Body "not json at all" -ExpectedStatus @(400)

# Register with duplicate username
$dupBody = @{
  username = "test_student_$studentTs"
  password = "AnotherPass123!"
  email = "dup_$studentTs@test.com"
  role = "student"
}  | ConvertTo-Json

Test-Api -Name "Register duplicate username" -Method "POST" -Url "$API/auth/register/" `
  -Body $dupBody -ExpectedStatus @(400) -Validate {
  param($j) $j -ne $null
}

# Register with weak password
$weakBody = @{
  username = "weakuser_$ts"
  password = "123"
  email = "weak@test.com"
  role = "student"
}  | ConvertTo-Json

Test-Api -Name "Register with weak password" -Method "POST" -Url "$API/auth/register/" `
  -Body $weakBody -ExpectedStatus @(400)

# Register with invalid role
$badRoleBody = @{
  username = "badrole_$ts"
  password = "TestPass123!"
  email = "badrole@test.com"
  role = "superadmin"
} | ConvertTo-Json

Test-Api -Name "Register with invalid role" -Method "POST" -Url "$API/auth/register/" `
  -Body $badRoleBody -ExpectedStatus @(400)

# Non-existent endpoint
Test-Api -Name "404 for non-existent endpoint" -Url "$API/nonexistent/endpoint/" -ExpectedStatus @(404)

# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " SECTION 19: FRONTEND PROTECTED PAGES (should load but redirect)" -ForegroundColor Cyan
Write-Host "========================================`n"

# These pages may return 200 (SPA shell) since Next.js renders them client-side
$protectedPages = @(
  @{ name = "Student home (/home)"; path = "/home" },
  @{ name = "Student classes (/classes)"; path = "/classes" },
  @{ name = "Teacher dashboard (/teacher)"; path = "/teacher" },
  @{ name = "Teacher analytics (/teacher/analytics)"; path = "/teacher/analytics" },
  @{ name = "Teacher create class (/teacher/create-class)"; path = "/teacher/create-class" },
  @{ name = "Teacher my classes (/teacher/my-classes)"; path = "/teacher/my-classes" },
  @{ name = "Student exam prep (/exam-prep)"; path = "/exam-prep" },
  @{ name = "Student notifications (/notifications)"; path = "/notifications" },
  @{ name = "Student profile (/profile)"; path = "/profile" },
  @{ name = "Admin maintenance (/admin/maintenance)"; path = "/admin/maintenance" }
)

foreach ($page in $protectedPages) {
  # Next.js SPA: server returns 200 with HTML shell, client-side JS handles auth redirect
  Test-Api -Name $page.name -Url "$FRONTEND$($page.path)" -ExpectedStatus @(200, 302, 307)
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
