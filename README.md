# Dev Castle — Student Performance Analysis & Quiz System

Django-based LMS for Dev Castle software house.

## Tech stack

- Python 3, Django 6
- SQLite, Pandas, NumPy, Matplotlib, Seaborn
- Bootstrap 5

## Setup

```powershell
cd D:\LMS
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Module 1 — Authentication (complete)

### Create superuser

Run interactively (you choose username/password — nothing is hardcoded):

```powershell
python manage.py createsuperuser
```

Then open **http://127.0.0.1:8000/admin/** and set the superuser's **Profile → Role** to **Admin**.

### Create teacher & student test users

1. Go to http://127.0.0.1:8000/admin/
2. **Users → Add user** — create `teacher1` and `student1` (set passwords on the next screen)
3. On each user's edit page, set **Profile → Role** to **Teacher** or **Student**

### URLs to test

| URL | Who can access |
|-----|----------------|
| http://127.0.0.1:8000/ | Redirects to role dashboard (or login) |
| http://127.0.0.1:8000/accounts/login/ | Everyone (public) |
| http://127.0.0.1:8000/accounts/logout/ | POST only — use navbar Logout button |
| http://127.0.0.1:8000/accounts/dashboard/admin/ | Admin role only |
| http://127.0.0.1:8000/accounts/dashboard/teacher/ | Teacher role only |
| http://127.0.0.1:8000/accounts/dashboard/student/ | Student role only |
| http://127.0.0.1:8000/admin/ | Staff/superuser (Django admin) |

### Expected behaviour

- Login as **admin** → lands on `/accounts/dashboard/admin/`
- Login as **teacher** → lands on `/accounts/dashboard/teacher/`
- Login as **student** → lands on `/accounts/dashboard/student/`
- Wrong role on a dashboard URL → redirected to your own dashboard
- Navbar shows role-specific links (placeholder URLs may 404 until later modules)
- Logout → returns to login page

## Project structure

```
LMS/
├── devcastle/          # Project settings & root URLs
├── accounts/           # Authentication, Profile, dashboards
├── students/           # Module 2: Student CRUD
├── analytics/          # Module 3: CSV upload & preprocessing
├── sample_data/        # Sample CSVs for testing uploads
├── quizzes/            # Module 5 (stub)
├── reports/            # Module 6 (stub)
├── templates/
├── static/
└── media/
```

## Auth design

- Django's built-in `User` model + `accounts.Profile` (OneToOne, `role` field)
- Profile auto-created on user creation via signal
- Role checks enforced in views via `@role_required` decorator (not template-only)

## Module 2 — Student Management (complete)

### URLs

| URL | Who can access |
|-----|----------------|
| http://127.0.0.1:8000/students/ | Admin, Teacher — paginated list with search/filter |
| http://127.0.0.1:8000/students/add/ | Admin, Teacher — creates User + Student together |
| http://127.0.0.1:8000/students/&lt;id&gt;/ | Admin, Teacher (any); Student (own only) |
| http://127.0.0.1:8000/students/&lt;id&gt;/edit/ | Admin, Teacher |
| http://127.0.0.1:8000/students/&lt;id&gt;/delete/ | Admin only |
| http://127.0.0.1:8000/students/profile/ | Student — redirects to own profile |

### What to check per role

- **Admin** — student list with Add / Edit / View / **Delete** buttons
- **Teacher** — list with Add / Edit / View; no Delete button; delete URL redirects away
- **Student** — "My Profile" in navbar works; `/students/` blocked; another student's profile URL redirects to dashboard

## Module 3 — CSV Upload & Preprocessing (complete)

### CSV schema

Required columns (exact names, case-insensitive headers accepted):

| Column | Type | Rules |
|--------|------|-------|
| `roll_number` | string | Must match an existing `Student.roll_number` |
| `subject` | string | Non-empty |
| `marks_obtained` | numeric | ≥ 0 and ≤ total_marks |
| `total_marks` | numeric | > 0 |
| `attendance_percentage` | numeric | 0–100 inclusive |

`class_name` is entered on the upload form, not in the CSV.

### Sample CSV files

Located in `sample_data/`:

- `performance_valid.csv` — imports successfully (needs students S001–S003 in admin)
- `performance_broken.csv` — partial import with row-level skips
- `performance_missing_columns.csv` — structural error, nothing saved

### Setup test students

Use the student CRUD form at http://127.0.0.1:8000/students/add/ (Admin/Teacher) with roll numbers **S001**, **S002**, **S003** to match the sample CSV.

### URLs to test

| URL | Who can access |
|-----|----------------|
| http://127.0.0.1:8000/analytics/upload/ | Admin, Teacher |
| http://127.0.0.1:8000/analytics/upload/history/ | Admin, Teacher |
| http://127.0.0.1:8000/analytics/upload/&lt;id&gt;/summary/ | Admin, Teacher |

Students hitting these URLs are redirected to their dashboard.

### Test scenarios

1. **Valid upload** — login as teacher/admin, upload `sample_data/performance_valid.csv`, class `CS-2024-A` → summary shows 6 rows processed, class/subject stats.
2. **Broken rows** — upload `performance_broken.csv` → valid rows import; skipped table shows e.g. `Row 3: roll_number 'S045' not found...`, `Row 4: marks_obtained (150) exceeds total_marks (100)`.
3. **Bad structure** — upload `performance_missing_columns.csv` → red structural error alert, **no DB records created**.
4. **Student blocked** — login as student, visit `/analytics/upload/` → redirected to student dashboard.

## Module 5 — Shuffled Quiz System (complete)

### Teacher URLs

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/quizzes/ | Quiz list |
| http://127.0.0.1:8000/quizzes/create/ | Manual create → add questions via formset |
| http://127.0.0.1:8000/quizzes/upload/ | Bulk CSV upload (`sample_data/quiz_questions_valid.csv`) |
| http://127.0.0.1:8000/quizzes/&lt;id&gt;/ | Quiz detail (unshuffled — teacher only) |
| http://127.0.0.1:8000/quizzes/&lt;id&gt;/attempts/ | Submitted attempts with search/sort |

### Student URLs

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8000/quizzes/my/ | Available active quizzes for their class/section |
| http://127.0.0.1:8000/quizzes/&lt;id&gt;/start/ | POST — creates attempt with persisted shuffle |
| http://127.0.0.1:8000/quizzes/attempt/&lt;id&gt;/take/ | Take quiz in shuffled order |
| http://127.0.0.1:8000/quizzes/attempt/&lt;id&gt;/result/ | Score after submit |

### How to test shuffling

1. Create two student accounts in the **same** `class_name` and `section` (e.g. CS-2024-A / A).
2. Create a quiz (manual or CSV bulk upload) targeting that class/section; set **Active**.
3. Log in as student 1 → Start quiz → note question order in DB or on screen.
4. Log in as student 2 → Start same quiz → order should differ.
5. Submit both with correct answers → both should score full marks (grading maps shuffled display letters back correctly).
6. Refresh the take page mid-attempt → order stays the same (read from `QuizAttempt`, not regenerated).

### CSV question schema

`question_text`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_option` (A–D), `marks` (optional)

## Module progress

- [x] Environment & project scaffold
- [x] Module 1: Authentication & role dashboards
- [x] Module 2: Student Management
- [x] Module 3: Data Science pipeline (CSV upload & preprocessing)
- [ ] Module 4: Visualization Dashboard
- [x] Module 5: Quiz System
- [ ] Module 6: Reports
