# FinSight

Personal Finance & Investment Intelligence Platform.

## Setup

### 1. Clone Repository

git clone <repository-url>
cd FinSight

### 2. Create Virtual Environment

python -m venv env

Activate:

Windows PowerShell:
.\env\Scripts\Activate.ps1

### 3. Install Dependencies

pip install -r requirements.txt

### 4. Configure Environment

Create `.env` in the project root:

DB_HOST=localhost
DB_NAME=Finsight
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432
SECRET_KEY=your_secret_key
FLASK_DEBUG=true  # local development only

### 5. Database

Make sure PostgreSQL is running.

Create a database named:

Finsight

Run the project migrations.

### 6. Run Application

python app.py

Open:

http://127.0.0.1:5000

### 7. Run Tests

pytest
