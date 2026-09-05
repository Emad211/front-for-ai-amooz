"""Seed the ten grade-9 shared-exam demo students (auto on every ``migrate``).

The ten real students from the shared exam result export (exam-result.json,
group 'نهم', test date 1405/05/31) get real accounts so their result import and
student-side review can be exercised in production without any manual operator
step: this data migration runs during the normal deploy-time ``migrate``.

Design rules (deliberate):
- Username AND phone are the same reserved fake mobile ``09129091001..010`` —
  login is username-based and the platform keys students by phone, so one
  number is the single credential id to hand out. The block is deliberately
  distinct from the old ``091290900xx`` demo seed block.
- Credentials are intentionally simple/deterministic (shared password
  ``grade9-demo-123``, the repo's documented demo password). Rotate before any
  non-test use.
- Idempotent AND defensive: the migration only ever updates rows whose
  ``username`` is one of the reserved ids above. A reserved username or phone
  already owned by a DIFFERENT account (non-student, or a student created under
  another username) is skipped, never overwritten — no real account is ever
  hijacked by this seed.
- Profiles: grade ``09`` (نهم) so ``is_effectively_completed``/curriculum
  derivation resolves. Major is intentionally unset (09 is not a high-school
  grade, so it is not required). No class/exam invitation is created here —
  that happens per published exam session via the operator commands.

Reverse simply removes the ten reserved accounts (their profiles cascade).
"""

from django.contrib.auth.hashers import make_password
from django.db import migrations

DEMO_PASSWORD = "grade9-demo-123"

# (username == reserved fake phone, first_name, last_name)
# Order = order of students in exam-result.json (counter asc).
ROSTER = [
    ("09129091001", "\u0645\u0627\u0647\u0627\u0646", "\u0627\u0628\u0627\u0630\u0631\u064a"),
    ("09129091002", "\u0627\u0645\u064a\u0631\u06a9\u0633\u0631\u064a", "\u0627\u0633\u062f\u0646\u0698\u0627\u062f"),
    ("09129091003", "\u0622\u0646\u064a\u0627", "\u0635\u0627\u0644\u062d\u064a"),
    ("09129091004", "\u067e\u0631\u064a\u0627", "\u067e\u064a\u0631\u0627\u0646\u064a \u0628\u0647\u0645\u0646 \u0622\u0628\u0627\u062f"),
    ("09129091005", "\u0627\u0628\u0648\u0627\u0644\u0642\u0627\u0633\u0645", "\u0631\u0648\u063a\u0646\u064a"),
    ("09129091006", "\u0631\u0627\u064a\u0627\u0646", "\u0627\u062d\u0645\u062f\u064a"),
    ("09129091007", "\u0633\u0627\u0645 \u0631\u0627\u062f", "\u062c\u0644\u0627\u0628"),
    ("09129091008", "\u0639\u0644\u064a \u0631\u0636\u0627", "\u0647\u062f\u0627\u064a\u062a\u064a"),
    ("09129091009", "\u0622\u064a\u0646\u0627\u0632", "\u064a\u0627\u062e\u0686\u064a\u200c\u062f\u0631"),
    ("09129091010", "\u0645\u062d\u0645\u062f\u0645\u0647\u062f\u064a", "\u062e\u0644\u064a\u0641\u0647"),
]
RESERVED_USERNAMES = [row[0] for row in ROSTER]
GRADE_9_CODE = "09"


def _is_test_database(schema_editor) -> bool:
    """True when ``migrate`` is building a pytest/Django test database.

    Every test run creates the full schema from scratch, which would otherwise
    re-seed the ten demo rows into the test DB and break tests that assert a
    pristine user/profile table (e.g. ``StudentProfile.objects.exists()``).
    Test databases are always named ``test_<db>`` by the Django test runner, so
    the seed is skipped there while still running on every real ``migrate``.
    """
    name = schema_editor.connection.settings_dict.get("NAME") or ""
    return name.startswith("test_")


def seed_grade9_demo_students(apps, schema_editor):
    if _is_test_database(schema_editor):
        return
    User = apps.get_model("accounts", "User")
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    for username, first_name, last_name in ROSTER:
        user = User.objects.filter(username=username).first()
        if user is None:
            # uniq_student_phone (role=STUDENT, phone not null): never create a
            # second STUDENT on a phone that already belongs to someone else.
            if User.objects.filter(phone=username, role="STUDENT").exists():
                continue
            user = User(
                username=username,
                phone=username,
                role="STUDENT",
                first_name=first_name,
                last_name=last_name,
                is_profile_completed=True,
                is_active=True,
            )
            user.password = make_password(DEMO_PASSWORD)
            user.save()
        else:
            if user.role != "STUDENT":
                # Reserved username taken by a non-student account — leave it.
                continue
            user.phone = username
            user.first_name = first_name
            user.last_name = last_name
            user.role = "STUDENT"
            user.is_profile_completed = True
            user.password = make_password(DEMO_PASSWORD)
            user.save(update_fields=[
                "phone", "first_name", "last_name", "role",
                "is_profile_completed", "password",
            ])
        profile, _created = StudentProfile.objects.get_or_create(user_id=user.pk)
        if profile.grade != GRADE_9_CODE:
            profile.grade = GRADE_9_CODE
            profile.save(update_fields=["grade"])


def unseed_grade9_demo_students(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(username__in=RESERVED_USERNAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_alter_user_role_parent"),
    ]

    operations = [
        migrations.RunPython(seed_grade9_demo_students, unseed_grade9_demo_students),
    ]
