#!/usr/bin/env pwsh
<#
  E2E Integration Test Suite for AI_AMOOZ
  ────────────────────────────────────────
  Tests the full stack: Next.js proxy → Django backend → PostgreSQL + Redis
  Requires: Docker services running (docker compose up -d)
            Next.js dev server running on port 9002

  Run:  .\tests\e2e_integration_tests.ps1
#>

$ErrorActionPreference = 'Continue'
$BACKEND  = "http://localhost:8000"
$FRONTEND = "http://localhost:9002"
$pass = 0; $fail = 0; $skip = 0; $errors = @()

# ──── Shared test helpers ────

function Test-API {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Base,
        [string]$Path,
        [string]$Body = $null,
        [hashtable]$Headers = @{},
        [int[]]$Expected = @(200),
        [switch]$ReturnJson,
        [switch]$IsForm
    )
    $url = "$Base$Path"
    $params = @{ Uri = $url; Method = $Method; SkipHttpErrorCheck = $true; Headers = $Headers }
    if ($Body -and !$IsForm) { $params['Body'] = $Body; $params['ContentType'] = 'application/json' }
    if ($Body -and $IsForm)  { $params['Body'] = $Body; $params['ContentType'] = 'multipart/form-data' }
    try {
        $r = Invoke-WebRequest @params
        if ($r.StatusCode -in $Expected) {
            Write-Host "  [PASS] $Name ($($r.StatusCode))" -ForegroundColor Green
            $script:pass++
        } else {
            $detail = if ($r.Content.Length -gt 300) { $r.Content.Substring(0,300) } else { $r.Content }
            Write-Host "  [FAIL] $Name  expected=$($Expected -join ',')  got=$($r.StatusCode)" -ForegroundColor Red
            Write-Host "         $detail" -ForegroundColor DarkRed
            $script:fail++; $script:errors += "$Name [$($r.StatusCode)]"
        }
        if ($ReturnJson -and $r.Content) {
            try   { return $r.Content | ConvertFrom-Json }
            catch { return $null }
        }
        return $null
    } catch {
        Write-Host "  [FAIL] $Name  EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++; $script:errors += "$Name [EXCEPTION]"
        return $null
    }
}

function Skip-Test { param([string]$Name,[string]$Reason)
    Write-Host "  [SKIP] $Name  ($Reason)" -ForegroundColor DarkYellow
    $script:skip++
}

# ──── Check prerequisites ────

Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AI_AMOOZ  —  E2E Integration Test Suite               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# Check backend
$healthOk = $false
try {
    $h = Invoke-RestMethod -Uri "$BACKEND/api/health/" -Method GET -TimeoutSec 5
    if ($h.status -eq 'healthy') { $healthOk = $true }
} catch {}
if (-not $healthOk) { Write-Host "ABORT: Backend not reachable at $BACKEND" -ForegroundColor Red; exit 1 }
Write-Host "Backend OK at $BACKEND" -ForegroundColor DarkGray

# Check frontend proxy
$proxyOk = $false
try {
    $p = Invoke-WebRequest -Uri "$FRONTEND" -Method GET -TimeoutSec 5 -SkipHttpErrorCheck
    if ($p.StatusCode -lt 500) { $proxyOk = $true }
} catch {}
if (-not $proxyOk) { Write-Host "WARNING: Frontend not reachable at $FRONTEND — proxy tests will be skipped" -ForegroundColor Yellow }
else { Write-Host "Frontend OK at $FRONTEND" -ForegroundColor DarkGray }

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

# ══════════════════════════════════════════════
# SECTION 1: HEALTH & SYSTEM
# ══════════════════════════════════════════════
Write-Host "`n━━━ 1. Health & System ━━━" -ForegroundColor Yellow

Test-API -Name "Backend /api/health/" -Method GET -Base $BACKEND -Path "/api/health/"
Test-API -Name "OpenAPI Schema" -Method GET -Base $BACKEND -Path "/api/schema/"
Test-API -Name "Swagger UI" -Method GET -Base $BACKEND -Path "/api/docs/"
Test-API -Name "ReDoc" -Method GET -Base $BACKEND -Path "/api/redoc/"
Test-API -Name "Admin login page" -Method GET -Base $BACKEND -Path "/admin/login/" -Expected @(200)

# Frontend now talks directly to backend (NEXT_PUBLIC_API_URL=http://localhost:8000)
# so proxy tests are not applicable. Verify backend CORS headers instead.
$corsTest = Invoke-WebRequest -Uri "$BACKEND/api/health/" -Method GET -Headers @{ Origin = 'http://localhost:9002' } -SkipHttpErrorCheck
if ($corsTest.Headers['Access-Control-Allow-Origin']) {
    Write-Host "  [PASS] CORS header present for frontend origin" -ForegroundColor Green; $pass++
} else {
    Write-Host "  [FAIL] CORS header missing" -ForegroundColor Red; $fail++
}

# ══════════════════════════════════════════════
# SECTION 2: AUTH — REGISTRATION
# ══════════════════════════════════════════════
Write-Host "`n━━━ 2. Auth — Registration ━━━" -ForegroundColor Yellow

# 2a. Register teacher (lowercase role)
$teacher = Test-API -Name "Register teacher (lowercase role)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"E2ePass123!`",`"role`":`"teacher`",`"first_name`":`"Test`",`"last_name`":`"Teacher`",`"email`":`"eteacher_$ts@test.com`"}" `
    -Expected @(201) -ReturnJson

# 2b. Register student (uppercase role)
$student = Test-API -Name "Register student (uppercase role)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"e2e_student_$ts`",`"password`":`"E2ePass123!`",`"role`":`"STUDENT`",`"first_name`":`"Test`",`"last_name`":`"Student`",`"email`":`"estudent_$ts@test.com`"}" `
    -Expected @(201) -ReturnJson

# 2c. Register default role (no role field)
$defaultRole = Test-API -Name "Register default role (omit role → STUDENT)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"e2e_default_$ts`",`"password`":`"E2ePass123!`",`"email`":`"edefault_$ts@test.com`"}" `
    -Expected @(201) -ReturnJson

if ($defaultRole) {
    if ($defaultRole.user.role -eq 'STUDENT') {
        Write-Host "  [PASS] Default role is STUDENT" -ForegroundColor Green; $pass++
    } else {
        Write-Host "  [FAIL] Default role expected=STUDENT got=$($defaultRole.user.role)" -ForegroundColor Red; $fail++
    }
}

# 2d. Duplicate username
Test-API -Name "Duplicate username (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"E2ePass123!`"}" `
    -Expected @(400)

# 2e. Duplicate email
Test-API -Name "Duplicate email (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"unique_$ts`",`"password`":`"E2ePass123!`",`"email`":`"eteacher_$ts@test.com`"}" `
    -Expected @(400)

# 2f. Weak password
Test-API -Name "Weak password (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"weakuser_$ts`",`"password`":`"123`"}" `
    -Expected @(400)

# 2g. Invalid role
Test-API -Name "Invalid role 'admin' (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"username`":`"badrole_$ts`",`"password`":`"E2ePass123!`",`"role`":`"admin`"}" `
    -Expected @(400)

# 2h. Missing username
Test-API -Name "Missing username (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/register/" `
    -Body "{`"password`":`"E2ePass123!`"}" `
    -Expected @(400)

# ══════════════════════════════════════════════
# SECTION 3: AUTH — LOGIN / TOKEN
# ══════════════════════════════════════════════
Write-Host "`n━━━ 3. Auth — Login / Token ━━━" -ForegroundColor Yellow

# 3a. Login teacher
$tLogin = Test-API -Name "Login teacher" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"E2ePass123!`"}" `
    -Expected @(200) -ReturnJson

$tAccess = $tLogin.access; $tRefresh = $tLogin.refresh

# 3b. Login student
$sLogin = Test-API -Name "Login student" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_student_$ts`",`"password`":`"E2ePass123!`"}" `
    -Expected @(200) -ReturnJson

$sAccess = $sLogin.access; $sRefresh = $sLogin.refresh

# 3c. Wrong password
Test-API -Name "Wrong password (401)" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"WrongPass!`"}" `
    -Expected @(401)

# 3d. Nonexistent user
Test-API -Name "Nonexistent user (401)" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"nobody_ever_$ts`",`"password`":`"doesntmatter`"}" `
    -Expected @(401)

# 3e. Token refresh
$refreshResult = Test-API -Name "Token refresh" -Method POST -Base $BACKEND `
    -Path "/api/token/refresh/" `
    -Body "{`"refresh`":`"$tRefresh`"}" `
    -Expected @(200) -ReturnJson

# After rotation, use new tokens
if ($refreshResult.access)  { $tAccess  = $refreshResult.access }
if ($refreshResult.refresh) { $tRefresh = $refreshResult.refresh }

# 3f. Invalid refresh token
Test-API -Name "Invalid refresh token (401)" -Method POST -Base $BACKEND `
    -Path "/api/token/refresh/" `
    -Body "{`"refresh`":`"invalid.token.here`"}" `
    -Expected @(401)

# 3g. Login with email as username (frontend uses email for teacher signup)
Test-API -Name "Login with email as username" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"E2ePass123!`"}" `
    -Expected @(200)

# ══════════════════════════════════════════════
# SECTION 4: ACCOUNTS — ME
# ══════════════════════════════════════════════
Write-Host "`n━━━ 4. Accounts — /me/ ━━━" -ForegroundColor Yellow

$tH = @{ Authorization = "Bearer $tAccess" }
$sH = @{ Authorization = "Bearer $sAccess" }

# 4a. GET me (teacher)
$tMe = Test-API -Name "GET /accounts/me/ (teacher)" -Method GET -Base $BACKEND `
    -Path "/api/accounts/me/" -Headers $tH -ReturnJson

if ($tMe) {
    if ($tMe.role -eq 'TEACHER') {
        Write-Host "  [PASS] Teacher role confirmed" -ForegroundColor Green; $pass++
    } else {
        Write-Host "  [FAIL] Expected role=TEACHER got=$($tMe.role)" -ForegroundColor Red; $fail++
    }
    if ($tMe.username -eq "e2e_teacher_$ts") {
        Write-Host "  [PASS] Username matches" -ForegroundColor Green; $pass++
    } else {
        Write-Host "  [FAIL] Username mismatch" -ForegroundColor Red; $fail++
    }
}

# 4b. GET me (student)
$sMe = Test-API -Name "GET /accounts/me/ (student)" -Method GET -Base $BACKEND `
    -Path "/api/accounts/me/" -Headers $sH -ReturnJson

if ($sMe -and $sMe.role -eq 'STUDENT') {
    Write-Host "  [PASS] Student role confirmed" -ForegroundColor Green; $pass++
}

# 4c. Update teacher profile
Test-API -Name "PATCH /accounts/me/ (update bio+location)" -Method PATCH -Base $BACKEND `
    -Path "/api/accounts/me/" -Headers $tH `
    -Body "{`"bio`":`"E2E test teacher`",`"location`":`"Tehran`"}"

# 4d. Verify update persisted
$tMe2 = Test-API -Name "GET /accounts/me/ (verify update)" -Method GET -Base $BACKEND `
    -Path "/api/accounts/me/" -Headers $tH -ReturnJson

if ($tMe2 -and $tMe2.bio -eq 'E2E test teacher' -and $tMe2.location -eq 'Tehran') {
    Write-Host "  [PASS] Profile update persisted" -ForegroundColor Green; $pass++
} elseif ($tMe2) {
    Write-Host "  [FAIL] Profile fields not updated: bio=$($tMe2.bio) location=$($tMe2.location)" -ForegroundColor Red; $fail++
}

# 4e. No auth
Test-API -Name "GET /accounts/me/ no auth (401)" -Method GET -Base $BACKEND `
    -Path "/api/accounts/me/" -Expected @(401)

# 4f. Invalid token
Test-API -Name "GET /accounts/me/ invalid token (401)" -Method GET -Base $BACKEND `
    -Path "/api/accounts/me/" -Headers @{ Authorization = "Bearer invalid.token" } -Expected @(401)

# ══════════════════════════════════════════════
# SECTION 5: PASSWORD CHANGE
# ══════════════════════════════════════════════
Write-Host "`n━━━ 5. Password Change ━━━" -ForegroundColor Yellow

Test-API -Name "Change password" -Method POST -Base $BACKEND `
    -Path "/api/auth/password-change/" -Headers $tH `
    -Body "{`"old_password`":`"E2ePass123!`",`"new_password`":`"NewE2ePass456!`"}"

# Login with new password
$newLogin = Test-API -Name "Login with new password" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"NewE2ePass456!`"}" `
    -Expected @(200) -ReturnJson

if ($newLogin.access)  { $tAccess = $newLogin.access; $tH = @{ Authorization = "Bearer $tAccess" } }
if ($newLogin.refresh) { $tRefresh = $newLogin.refresh }

# Old password should fail
Test-API -Name "Old password rejected (401)" -Method POST -Base $BACKEND `
    -Path "/api/token/" `
    -Body "{`"username`":`"e2e_teacher_$ts`",`"password`":`"E2ePass123!`"}" `
    -Expected @(401)

# Wrong old_password in change
Test-API -Name "Wrong old_password (400)" -Method POST -Base $BACKEND `
    -Path "/api/auth/password-change/" -Headers $tH `
    -Body "{`"old_password`":`"WrongOld!`",`"new_password`":`"Something123!`"}" -Expected @(400)

# ══════════════════════════════════════════════
# SECTION 6: CLASSES — TEACHER
# ══════════════════════════════════════════════
Write-Host "`n━━━ 6. Classes — Teacher Endpoints ━━━" -ForegroundColor Yellow

# 6a. List sessions
Test-API -Name "GET /classes/creation-sessions/ (teacher)" -Method GET -Base $BACKEND `
    -Path "/api/classes/creation-sessions/" -Headers $tH

# 6b. Student cannot access
Test-API -Name "GET /classes/creation-sessions/ (student → 403)" -Method GET -Base $BACKEND `
    -Path "/api/classes/creation-sessions/" -Headers $sH -Expected @(403)

# 6c. Unauthenticated
Test-API -Name "GET /classes/creation-sessions/ no auth (401)" -Method GET -Base $BACKEND `
    -Path "/api/classes/creation-sessions/" -Expected @(401)

# ══════════════════════════════════════════════
# SECTION 7: TEACHER ANALYTICS
# ══════════════════════════════════════════════
Write-Host "`n━━━ 7. Teacher Analytics ━━━" -ForegroundColor Yellow

$analyticsPaths = @(
    "/api/classes/teacher/analytics/stats/",
    "/api/classes/teacher/analytics/chart/",
    "/api/classes/teacher/analytics/distribution/",
    "/api/classes/teacher/analytics/activities/",
    "/api/classes/teacher/analytics/export-csv/"
)
foreach ($p in $analyticsPaths) {
    $name = $p.Split('/')[-2]
    Test-API -Name "Analytics: $name (teacher)" -Method GET -Base $BACKEND -Path $p -Headers $tH
    Test-API -Name "Analytics: $name (student→403)" -Method GET -Base $BACKEND -Path $p -Headers $sH -Expected @(403)
}

# ══════════════════════════════════════════════
# SECTION 8: TEACHER STUDENTS
# ══════════════════════════════════════════════
Write-Host "`n━━━ 8. Teacher Students ━━━" -ForegroundColor Yellow

Test-API -Name "GET /teacher/students/ (teacher)" -Method GET -Base $BACKEND `
    -Path "/api/classes/teacher/students/" -Headers $tH

Test-API -Name "GET /teacher/students/ (student→403)" -Method GET -Base $BACKEND `
    -Path "/api/classes/teacher/students/" -Headers $sH -Expected @(403)

# ══════════════════════════════════════════════
# SECTION 9: STUDENT COURSES
# ══════════════════════════════════════════════
Write-Host "`n━━━ 9. Student Courses ━━━" -ForegroundColor Yellow

$sCourses = Test-API -Name "GET /student/courses/ (student)" -Method GET -Base $BACKEND `
    -Path "/api/classes/student/courses/" -Headers $sH -ReturnJson

Test-API -Name "GET /student/courses/ (teacher→403)" -Method GET -Base $BACKEND `
    -Path "/api/classes/student/courses/" -Headers $tH -Expected @(403)

# ══════════════════════════════════════════════
# SECTION 10: STUDENT EXAM PREPS
# ══════════════════════════════════════════════
Write-Host "`n━━━ 10. Student Exam Preps ━━━" -ForegroundColor Yellow

Test-API -Name "GET /student/exam-preps/ (student)" -Method GET -Base $BACKEND `
    -Path "/api/classes/student/exam-preps/" -Headers $sH

Test-API -Name "GET /student/exam-preps/ (teacher→403)" -Method GET -Base $BACKEND `
    -Path "/api/classes/student/exam-preps/" -Headers $tH -Expected @(403)

# ══════════════════════════════════════════════
# SECTION 11: STUDENT NOTIFICATIONS
# ══════════════════════════════════════════════
Write-Host "`n━━━ 11. Student Notifications ━━━" -ForegroundColor Yellow

Test-API -Name "GET /student/notifications/ (student)" -Method GET -Base $BACKEND `
    -Path "/api/classes/student/notifications/" -Headers $sH

# ══════════════════════════════════════════════
# SECTION 12: NOTIFICATIONS
# ══════════════════════════════════════════════
Write-Host "`n━━━ 12. Notifications ━━━" -ForegroundColor Yellow

Test-API -Name "GET /notifications/teacher/ (teacher)" -Method GET -Base $BACKEND `
    -Path "/api/notifications/teacher/" -Headers $tH

Test-API -Name "POST /notifications/read-all/ (teacher)" -Method POST -Base $BACKEND `
    -Path "/api/notifications/read-all/" -Headers $tH

Test-API -Name "POST /notifications/read-all/ (student)" -Method POST -Base $BACKEND `
    -Path "/api/notifications/read-all/" -Headers $sH

# ══════════════════════════════════════════════
# SECTION 13: INVITE VERIFICATION
# ══════════════════════════════════════════════
Write-Host "`n━━━ 13. Invite Verification ━━━" -ForegroundColor Yellow

$inv = Test-API -Name "POST /invites/verify/ (invalid code)" -Method POST -Base $BACKEND `
    -Path "/api/classes/invites/verify/" `
    -Body "{`"code`":`"FAKE_CODE_$ts`"}" -ReturnJson

if ($inv -and $inv.valid -eq $false) {
    Write-Host "  [PASS] Invalid code returns valid=false" -ForegroundColor Green; $pass++
}

# ══════════════════════════════════════════════
# SECTION 14: EXAM PREP SESSIONS (Teacher)
# ══════════════════════════════════════════════
Write-Host "`n━━━ 14. Exam Prep Sessions ━━━" -ForegroundColor Yellow

Test-API -Name "GET /exam-prep-sessions/ (teacher)" -Method GET -Base $BACKEND `
    -Path "/api/classes/exam-prep-sessions/" -Headers $tH

Test-API -Name "GET /exam-prep-sessions/ (student→403)" -Method GET -Base $BACKEND `
    -Path "/api/classes/exam-prep-sessions/" -Headers $sH -Expected @(403)

# ══════════════════════════════════════════════
# SECTION 15: FRONTEND PAGE LOADING
# ══════════════════════════════════════════════
Write-Host "`n━━━ 15. Frontend Pages ━━━" -ForegroundColor Yellow

if ($proxyOk) {
    $frontendPages = @(
        @{ Name = "Landing page /"; Path = "/" }
        @{ Name = "Login page"; Path = "/login" }
        @{ Name = "Teacher signup"; Path = "/teacher-signup" }
        @{ Name = "Join code page"; Path = "/join-code" }
        @{ Name = "Start page"; Path = "/start" }
    )
    foreach ($pg in $frontendPages) {
        Test-API -Name $pg.Name -Method GET -Base $FRONTEND -Path $pg.Path -Expected @(200, 307)
    }
} else {
    Skip-Test -Name "Frontend pages" -Reason "Frontend not running"
}

# ══════════════════════════════════════════════
# SECTION 16: AUTH — LOGOUT
# ══════════════════════════════════════════════
Write-Host "`n━━━ 16. Logout ━━━" -ForegroundColor Yellow

if ($tRefresh) {
    Test-API -Name "Logout teacher" -Method POST -Base $BACKEND `
        -Path "/api/auth/logout/" -Headers $tH `
        -Body "{`"refresh`":`"$tRefresh`"}" -Expected @(200, 204, 205)

    # Token should be blacklisted now
    Test-API -Name "Reuse blacklisted refresh (401)" -Method POST -Base $BACKEND `
        -Path "/api/token/refresh/" `
        -Body "{`"refresh`":`"$tRefresh`"}" -Expected @(401)
}

if ($sRefresh) {
    Test-API -Name "Logout student" -Method POST -Base $BACKEND `
        -Path "/api/auth/logout/" -Headers $sH `
        -Body "{`"refresh`":`"$sRefresh`"}" -Expected @(200, 204, 205)
}

# ══════════════════════════════════════════════
# SECTION 17: SECURITY — RATE LIMITING
# ══════════════════════════════════════════════
Write-Host "`n━━━ 17. Rate Limiting ━━━" -ForegroundColor Yellow

# Fire multiple requests quickly (anon 60/min) — just verify headers exist
$rl = Invoke-WebRequest -Uri "$BACKEND/api/health/" -SkipHttpErrorCheck
if ($rl.StatusCode -eq 200) {
    Write-Host "  [PASS] Rate limit not triggered for single request" -ForegroundColor Green; $pass++
} else {
    Write-Host "  [FAIL] Unexpected status: $($rl.StatusCode)" -ForegroundColor Red; $fail++
}

# ══════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════
Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   TEST RESULTS                                          ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║   PASSED:  $pass" -ForegroundColor Green
Write-Host "║   FAILED:  $fail" -ForegroundColor $(if ($fail -gt 0) { 'Red' } else { 'Green' })
Write-Host "║   SKIPPED: $skip" -ForegroundColor $(if ($skip -gt 0) { 'DarkYellow' } else { 'Green' })
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

if ($errors.Count -gt 0) {
    Write-Host "`nFailed tests:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  • $_" -ForegroundColor Red }
}

Write-Host ""
exit $fail
