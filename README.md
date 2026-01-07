# AI AMOOZ - Quick Start Guide



## 🚀 Quick Setup

### 1. Clone & Install

```bash
git clone <repository-url>
cd AI_AMOOZ

# Backend setup
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r backend/requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### 2. Database Setup

```bash
# Start PostgreSQL with Docker
docker-compose up -d

# Run migrations
cd backend
python manage.py migrate
python manage.py createcachetable
```

### 3. Environment Configuration

#### Backend Environment (`.env`)

Create `backend/.env` file with the following variables:

```bash
# ============ CORE SETTINGS ============
DEBUG=True                                      # Set to False in production
DJANGO_SECRET_KEY=your-secret-key-here         # Generate a secure key
ALLOWED_HOSTS=localhost,127.0.0.1              # Comma-separated hosts

# ============ DATABASE ============
DATABASE_URL=postgresql://ai_amooz:ai_amooz_password@localhost:5432/ai_amooz
# Format: postgresql://username:password@host:port/database

# ============ REDIS (Cache & Memory) ============
CHAT_REDIS_URL=redis://localhost:6379/0        # Optional, defaults to localhost:6379

# ============ LLM PROVIDERS ============
# Choose provider: 'gemini' | 'avalai' | 'auto' (tries both)
LLM_PROVIDER=auto

# Google Gemini API
GEMINI_API_KEY=your-gemini-api-key-here

# Avalai API (Iranian alternative)
AVALAI_API_KEY=your-avalai-api-key-here
AVALAI_BASE_URL=https://api.avalai.ir

# ============ LLM MODELS ============
MODEL_NAME=models/gemini-2.5-flash              # Main model for chat
TRANSCRIPTION_MODEL=models/gemini-2.5-flash     # Speech-to-text model
REWRITE_MODEL=models/gemini-2.5-flash           # Content rewriting
IMAGE_MODEL=models/gemini-3-pro-image-preview   # Image analysis model
EMBEDDING_MODEL_NAME=models/gemini-embedding-001 # Text embeddings

# ============ LLM SETTINGS ============
GENAI_HTTP_TIMEOUT=1000                         # Timeout in ms
MODE=avalai                                     # Legacy fallback (use LLM_PROVIDER)

# ============ OPTIONAL ============
MEDIANA_API_KEY=ZY2nMe3zsJaswUqPbtWJAyhEtpA2VPLmjfi7HnQbD38=
CLASS_PIPELINE_ASYNC=True                       # Run heavy tasks asynchronously
```

#### Frontend Environment (`.env.local`)

Create `frontend/.env.local` file:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api   # Backend API endpoint
NEXT_PUBLIC_APP_NAME=AI AMOOZ

```

### 4. Run the Project

**Terminal 1 - Backend:**
```bash
cd backend
python manage.py runserver 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 📍 Access Points

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/api/
- **Admin Panel:** http://localhost:8000/admin/

## 🧪 Testing

```bash
# Backend tests
cd backend
python -m pytest

# Frontend type check
cd frontend
npx tsc --noEmit
```

## 🛑 Stop Services

```bash
# Stop Docker containers
docker-compose down

# Stop dev servers with Ctrl+C
```

---

That's it! The project should be running locally with full AI chatbot functionality.
