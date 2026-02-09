#!/usr/bin/env pwsh
# Live API test script for AI_AMOOZ backend on http://localhost:8000
# Tests every endpoint category against the running Docker deployment.

$ErrorActionPreference = 'Continue'
$BASE = "http://localhost:8000"
$pass = 0
$fail = 0
$errors = @()

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Url,
        [string]$Body = $null,
        [hashtable]$Headers = @{},
        [int[]]$ExpectedStatus = @(200),
        [switch]$ReturnContent
    )
    $params = @{
        Uri = "$BASE$Url"
        Method = $Method
        SkipHttpErrorCheck = $true
        Headers = $Headers
    }
    if ($Body) {
        $params['Body'] = $Body
        $params['ContentType'] = 'application/json'
    }
    try {
        $r = Invoke-WebRequest @params
        if ($r.StatusCode -in $ExpectedStatus) {
            Write-Host "  PASS  $Name ($($r.StatusCode))" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "  FAIL  $Name - Expected $($ExpectedStatus -join ',') got $($r.StatusCode)" -ForegroundColor Red
            Write-Host "        $($r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))" -ForegroundColor DarkRed
            $script:fail++
            $script:errors += "$Name : $($r.StatusCode)"
        }
        if ($ReturnContent) { return $r.Content }
        return $null
    } catch {
        Write-Host "  FAIL  $Name - Exception: $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++
        $script:errors += "$Name : EXCEPTION"
        return $null
    }
}

Write-Host "`n========== AI_AMOOZ LIVE API TESTS ==========" -ForegroundColor Cyan
Write-Host "Target: $BASE`n"

# ─── 1. HEALTH / SYSTEM ───
Write-Host "--- Health / System ---" -ForegroundColor Yellow
Test-Endpoint -Name "Health Check" -Method GET -Url "/api/health/"
Test-Endpoint -Name "OpenAPI Schema" -Method GET -Url "/api/schema/"
Test-Endpoint -Name "Swagger UI" -Method GET -Url "/api/docs/"
Test-Endpoint -Name "ReDoc" -Method GET -Url "/api/redoc/"

# ─── 2. AUTH - REGISTER ───
Write-Host "`n--- Auth: Register ---" -ForegroundColor Yellow
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

# Teacher
$teacherBody = "{`"username`":`"live_teacher_$ts`",`"password`":`"SecurePass123!`",`"role`":`"teacher`",`"first_name`":`"Ali`",`"last_name`":`"Karimi`",`"email`":`"t_$ts@test.com`"}"
$teacherJson = Test-Endpoint -Name "Register Teacher (lowercase role)" -Method POST -Url "/api/auth/register/" -Body $teacherBody -ExpectedStatus @(201) -ReturnContent
$teacher = $teacherJson | ConvertFrom-Json
$tAccess = $teacher.tokens.access
$tRefresh = $teacher.tokens.refresh

# Student
$studentBody = "{`"username`":`"live_student_$ts`",`"password`":`"SecurePass123!`",`"role`":`"STUDENT`",`"first_name`":`"Sara`",`"last_name`":`"Hosseini`",`"email`":`"s_$ts@test.com`"}"
$studentJson = Test-Endpoint -Name "Register Student (uppercase role)" -Method POST -Url "/api/auth/register/" -Body $studentBody -ExpectedStatus @(201) -ReturnContent
$student = $studentJson | ConvertFrom-Json
$sAccess = $student.tokens.access
$sRefresh = $student.tokens.refresh

# Duplicate username
Test-Endpoint -Name "Register Duplicate Username (expect 400)" -Method POST -Url "/api/auth/register/" -Body $teacherBody -ExpectedStatus @(400)

# Weak password
$weakBody = "{`"username`":`"weakuser_$ts`",`"password`":`"123`"}"
Test-Endpoint -Name "Register Weak Password (expect 400)" -Method POST -Url "/api/auth/register/" -Body $weakBody -ExpectedStatus @(400)

# ─── 3. AUTH - LOGIN ───
Write-Host "`n--- Auth: Login (Token) ---" -ForegroundColor Yellow
$loginBody = "{`"username`":`"live_teacher_$ts`",`"password`":`"SecurePass123!`"}"
$loginJson = Test-Endpoint -Name "Login Teacher" -Method POST -Url "/api/token/" -Body $loginBody -ExpectedStatus @(200) -ReturnContent
$loginData = $loginJson | ConvertFrom-Json
$tAccess = $loginData.access
$tRefresh = $loginData.refresh

$badLogin = "{`"username`":`"live_teacher_$ts`",`"password`":`"WrongPass999`"}"
Test-Endpoint -Name "Login Bad Password (expect 401)" -Method POST -Url "/api/token/" -Body $badLogin -ExpectedStatus @(401)

# Token refresh
$refreshBody = "{`"refresh`":`"$tRefresh`"}"
$refreshJson = Test-Endpoint -Name "Token Refresh" -Method POST -Url "/api/token/refresh/" -Body $refreshBody -ExpectedStatus @(200) -ReturnContent
$newTokens = $refreshJson | ConvertFrom-Json
$tAccess = $newTokens.access

# ─── 4. ACCOUNTS - ME ───
Write-Host "`n--- Accounts: Me ---" -ForegroundColor Yellow
$authH = @{ Authorization = "Bearer $tAccess" }
$meJson = Test-Endpoint -Name "GET /accounts/me/ (Teacher)" -Method GET -Url "/api/accounts/me/" -Headers $authH -ReturnContent
Write-Host "        Role: $(($meJson | ConvertFrom-Json).role)" -ForegroundColor DarkGray

# Update profile
$patchBody = "{`"bio`":`"Test teacher bio`",`"location`":`"Tehran`"}"
Test-Endpoint -Name "PATCH /accounts/me/ (Update)" -Method PATCH -Url "/api/accounts/me/" -Body $patchBody -Headers $authH

# Unauthenticated
Test-Endpoint -Name "GET /accounts/me/ No Auth (expect 401)" -Method GET -Url "/api/accounts/me/" -ExpectedStatus @(401)

# Student me
$sLoginBody = "{`"username`":`"live_student_$ts`",`"password`":`"SecurePass123!`"}"
$sLoginJson = Test-Endpoint -Name "Login Student" -Method POST -Url "/api/token/" -Body $sLoginBody -ExpectedStatus @(200) -ReturnContent
$sTokens = $sLoginJson | ConvertFrom-Json
$sAccess = $sTokens.access
$sAuthH = @{ Authorization = "Bearer $sAccess" }
$sMeJson = Test-Endpoint -Name "GET /accounts/me/ (Student)" -Method GET -Url "/api/accounts/me/" -Headers $sAuthH -ReturnContent
Write-Host "        Role: $(($sMeJson | ConvertFrom-Json).role)" -ForegroundColor DarkGray

# ─── 5. AUTH - PASSWORD CHANGE ───
Write-Host "`n--- Auth: Password Change ---" -ForegroundColor Yellow
$pwBody = "{`"old_password`":`"SecurePass123!`",`"new_password`":`"NewSecure456!`"}"
Test-Endpoint -Name "Password Change" -Method POST -Url "/api/auth/password-change/" -Body $pwBody -Headers $authH

# Login with new password
$newLoginBody = "{`"username`":`"live_teacher_$ts`",`"password`":`"NewSecure456!`"}"
$newLoginJson = Test-Endpoint -Name "Login with New Password" -Method POST -Url "/api/token/" -Body $newLoginBody -ExpectedStatus @(200) -ReturnContent
$newLogin = $newLoginJson | ConvertFrom-Json
$tAccess = $newLogin.access
$authH = @{ Authorization = "Bearer $tAccess" }

# ─── 6. CLASSES - TEACHER SESSIONS ───
Write-Host "`n--- Classes: Teacher Sessions ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /classes/creation-sessions/ (Teacher)" -Method GET -Url "/api/classes/creation-sessions/" -Headers $authH

# Student cannot access teacher sessions
Test-Endpoint -Name "GET /classes/creation-sessions/ (Student=403)" -Method GET -Url "/api/classes/creation-sessions/" -Headers $sAuthH -ExpectedStatus @(403)

# ─── 7. CLASSES - TEACHER ANALYTICS ───
Write-Host "`n--- Classes: Teacher Analytics ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET analytics/stats/" -Method GET -Url "/api/classes/teacher/analytics/stats/" -Headers $authH
Test-Endpoint -Name "GET analytics/chart/" -Method GET -Url "/api/classes/teacher/analytics/chart/" -Headers $authH
Test-Endpoint -Name "GET analytics/distribution/" -Method GET -Url "/api/classes/teacher/analytics/distribution/" -Headers $authH
Test-Endpoint -Name "GET analytics/activities/" -Method GET -Url "/api/classes/teacher/analytics/activities/" -Headers $authH
Test-Endpoint -Name "GET analytics/export-csv/" -Method GET -Url "/api/classes/teacher/analytics/export-csv/" -Headers $authH

# ─── 8. CLASSES - TEACHER STUDENTS ───
Write-Host "`n--- Classes: Teacher Students ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /teacher/students/" -Method GET -Url "/api/classes/teacher/students/" -Headers $authH

# ─── 9. CLASSES - STUDENT COURSES ───
Write-Host "`n--- Classes: Student Courses ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /student/courses/" -Method GET -Url "/api/classes/student/courses/" -Headers $sAuthH

# ─── 10. STUDENT NOTIFICATIONS ───
Write-Host "`n--- Student Notifications ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /student/notifications/" -Method GET -Url "/api/classes/student/notifications/" -Headers $sAuthH

# ─── 11. STUDENT EXAM PREPS ───
Write-Host "`n--- Student Exam Preps ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /student/exam-preps/" -Method GET -Url "/api/classes/student/exam-preps/" -Headers $sAuthH

# ─── 12. NOTIFICATIONS - TEACHER ───
Write-Host "`n--- Notifications: Teacher ---" -ForegroundColor Yellow
Test-Endpoint -Name "GET /notifications/teacher/" -Method GET -Url "/api/notifications/teacher/" -Headers $authH

# ─── 13. NOTIFICATIONS - READ ALL ───
Write-Host "`n--- Notifications: Read All ---" -ForegroundColor Yellow
Test-Endpoint -Name "POST /notifications/read-all/" -Method POST -Url "/api/notifications/read-all/" -Headers $authH

# ─── 14. INVITE VERIFY ───
Write-Host "`n--- Invite Verify ---" -ForegroundColor Yellow
$invBody = "{`"code`":`"INVALID_CODE`"}"
Test-Endpoint -Name "POST /invites/verify/ (invalid)" -Method POST -Url "/api/classes/invites/verify/" -Body $invBody

# ─── 15. AUTH - LOGOUT ───
Write-Host "`n--- Auth: Logout ---" -ForegroundColor Yellow
$logoutRefresh = $newLogin.refresh
if ($logoutRefresh) {
    $logoutBody = "{`"refresh`":`"$logoutRefresh`"}"
    Test-Endpoint -Name "Logout (blacklist token)" -Method POST -Url "/api/auth/logout/" -Body $logoutBody -Headers $authH -ExpectedStatus @(200, 204, 205)
} else {
    Write-Host "  SKIP  Logout - no refresh token" -ForegroundColor DarkYellow
}

# ─── SUMMARY ───
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  PASSED: $pass" -ForegroundColor Green
Write-Host "  FAILED: $fail" -ForegroundColor $(if ($fail -gt 0) { 'Red' } else { 'Green' })
if ($errors.Count -gt 0) {
    Write-Host "`n  Failures:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}
Write-Host "========================================`n" -ForegroundColor Cyan
