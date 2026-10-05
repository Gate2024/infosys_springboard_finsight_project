<div align="center">

# 💰 FinSight

### **See Smarter. Spend Better. Live Brighter.**

<p><strong>A full-stack personal finance management, analytics, and financial wellness platform.</strong></p>

<p>Track your money • Understand your spending • Manage budgets • Monitor investments • Set goals • Make informed financial decisions</p>

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6%2B-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![Chart.js](https://img.shields.io/badge/Chart.js-Data%20Visualization-FF6384?style=for-the-badge&logo=chart.js&logoColor=white)](https://www.chartjs.org/)
[![SQLite](https://img.shields.io/badge/SQLite-Development-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Production-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-Production%20WSGI-499848?style=for-the-badge)](https://gunicorn.org/)
[![Render](https://img.shields.io/badge/Render-Deployment-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/)
[![UptimeRobot](https://img.shields.io/badge/UptimeRobot-Monitoring-00B894?style=for-the-badge)](https://uptimerobot.com/)

### 🌐 Live Application

**[🚀 Open FinSight Live](https://infosys-springboard-finsight-project.onrender.com/)**

</div>

---

## 📑 Table of Contents

- [🌟 Project Overview](#-project-overview)
- [🎯 Problem Statement](#-problem-statement)
- [💡 Project Objective](#-project-objective)
- [🚀 Key Features](#-key-features)
- [🧠 Product Design Philosophy](#-product-design-philosophy)
- [🛠️ Technology Stack](#️-technology-stack)
- [🏗️ System Architecture](#️-system-architecture)
- [🔄 Application Workflow](#-application-workflow)
- [🗄️ Database Architecture](#️-database-architecture)
- [🔐 Security Architecture](#-security-architecture)
- [🗃️ Database Migration System](#️-database-migration-system)
- [📂 Project Structure](#-project-structure)
- [📊 Financial Analytics](#-financial-analytics)
- [📄 Reporting & Export Architecture](#-reporting--export-architecture)
- [🧪 Testing & Quality Assurance](#-testing--quality-assurance)
- [🚀 Production Deployment](#-production-deployment)
- [💓 Health Monitoring](#-health-monitoring)
- [📡 Health Endpoint](#-health-endpoint)
- [⚙️ Local Installation](#️-local-installation)
- [🔑 Environment Configuration](#-environment-configuration)
- [🔒 Production Security & Reliability](#-production-security--reliability)
- [🛠️ Engineering Work & Production Hardening](#️-engineering-work--production-hardening)
- [🐛 Challenges & Solutions](#-challenges--solutions)
- [📚 Development Journey](#-development-journey)
- [🧠 What I Learned](#-what-i-learned)
- [🔮 Future Improvements](#-future-improvements)
- [👨‍💻 Developer](#-developer)
- [⭐ Support](#-support)

---

# 🌟 Project Overview

**FinSight** is a full-stack personal finance management and analytics web application developed to help users organize financial information, understand spending behavior, manage budgets, track investments and goals, and generate meaningful financial insights.

The project was developed with a strong focus on going beyond basic CRUD functionality. It combines secure authentication, financial record management, data visualization, financial analytics, budgeting, investments, goals, reporting, notifications, personalization, responsive UI, database migrations, production deployment, and monitoring.

The application was taken through the complete development lifecycle:

```text
Idea
  ↓
Requirements
  ↓
Application Development
  ↓
Authentication & Security
  ↓
Financial Modules
  ↓
Analytics & Visualization
  ↓
Reports & Exports
  ↓
Responsive UI
  ↓
Automated Testing
  ↓
Production Hardening
  ↓
Render Deployment
  ↓
Health Monitoring
  ↓
🟢 LIVE APPLICATION
```

---

# 🎯 Problem Statement

Personal financial information is often distributed across multiple places:

```text
Income             → Spreadsheet / Notes
Expenses           → Manual records / Separate apps
Budgets            → Manual calculations
Investments        → Separate platforms
Financial Goals    → Personal tracking
Reports            → Manual preparation
Financial Analysis → Often unavailable
```

This makes it difficult to obtain a single, understandable picture of financial activity.

Users may know **how much they spent**, but not necessarily:

- where they spend the most
- whether they are staying within their budgets
- how their spending is distributed
- how their financial position is changing
- what areas require attention
- how their financial information can be converted into useful insights

---

# 💡 Project Objective

FinSight was designed to bring these financial activities into one platform.

The central workflow is:

```text
                    ┌───────────────┐
                    │    TRACK      │
                    │ Income        │
                    │ Expenses      │
                    │ Investments   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    ANALYZE    │
                    │ Spending      │
                    │ Budgets       │
                    │ Financial     │
                    │ Health        │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     PLAN      │
                    │ Budgets       │
                    │ Goals         │
                    │ Investments   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │     ACT       │
                    │ Recommendations│
                    │ Reports       │
                    │ Better choices│
                    └───────────────┘
```

---

# 🚀 Key Features

## 🔐 Authentication & Account Security

FinSight includes a complete authentication foundation designed around secure account access.

### Registration

- User registration
- Input validation
- Password requirements
- CSRF protection
- Secure password hashing
- Direct account creation
- No dependency on external email delivery for normal registration

### Login

- Secure login
- Password verification
- Session creation
- CSRF protection
- Login rate limiting
- Remember Me support
- TOTP authentication when enabled

### Logout

- POST-based logout
- CSRF protection
- Session revocation
- Remember Me token handling

### Session Security

Tracked sessions include:

- inactivity timeout
- absolute session timeout
- session revocation
- ownership validation
- secure cookie configuration

### Remember Me

FinSight uses dedicated Remember Me token storage rather than storing raw long-lived authentication tokens.

```text
Login
  ↓
Remember Me Token
  ↓
Hashed Token Storage
  ↓
Token Rotation
  ↓
Revocation on Logout / Security Events
```

### TOTP 2FA

FinSight includes authenticator-app-based two-factor authentication.

The TOTP system is separate from email OTP functionality. Users can configure authenticator-based 2FA and complete an additional authentication step when enabled.

---

## 📊 Financial Dashboard

The dashboard provides a centralized overview of a user's financial situation.

It can surface:

- total income
- total expenses
- available balance
- financial health information
- expense breakdown
- income vs expenses
- spending patterns
- budget analysis
- recommendations

The dashboard is designed to turn multiple financial modules into one understandable overview.

---

## 💸 Expense Management

The expense module provides structured expense tracking.

### Capabilities

- Add expenses
- Edit expenses
- Delete expenses
- Categorize expenses
- Track expense amounts
- Review expense history
- Analyze category-level spending
- Use expense data in financial analytics

The expense data becomes the foundation for multiple analytical features.

---

## 💰 Income Tracking

Income information is incorporated into the financial dashboard and analytics layer.

```text
Income
   ↓
Expenses
   ↓
Balance
   ↓
Financial Position
```

Income data supports dashboard summaries and financial analysis.

---

## 🎯 Budget Management

The budget module allows users to create and manage planned spending.

FinSight can compare planned budgets with actual spending.

```text
              ┌──────────────┐
              │    Budget    │
              │   Planned    │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │   Compare    │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Actual Spend │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │   Insight    │
              └──────────────┘
```

---

## 📈 Investment Management

FinSight includes an investment management module so users can maintain investment-related financial information alongside other personal financial records.

Investment information is integrated into the broader financial picture rather than existing as an isolated feature.

---

## 🏆 Financial Goals

Users can define financial goals and monitor their progress.

Examples include:

- savings targets
- emergency funds
- major purchases
- personal financial milestones

Goals provide a planning layer on top of historical financial tracking.

---

## ❤️ Financial Health Score

FinSight calculates a **Financial Health Score** using available financial information.

Conceptually:

```text
Financial Information
        │
        ├── Income
        ├── Expenses
        ├── Budget Information
        └── Other Available Data
                │
                ▼
        Financial Analysis
                │
                ▼
        Financial Health Score
```

When the system does not have enough financial information to generate a meaningful score, it displays an **Insufficient Data** state rather than presenting misleading information.

---

## 📉 Spending Pattern Analysis

FinSight analyzes available expense information to help users understand spending behavior.

The analysis can help identify:

- high-spending categories
- distribution of expenses
- spending patterns
- category-level behavior
- changes in spending

---

## ⚖️ Budget vs Spending

The application provides budget-vs-spending analysis.

```text
How much did I plan to spend?
              ↓
How much did I actually spend?
              ↓
What is the difference?
              ↓
Which categories require attention?
```

This connects the Budget and Expense modules into a single analytical workflow.

---

## 💡 Spending Recommendations

FinSight includes a spending recommendation layer.

The objective is to transform financial information into actionable insights rather than displaying only raw numbers.

Recommendations are based on available financial information and spending behavior.

---

## 📑 Reports & Exports

Supported formats include:

| Format | Purpose |
|---|---|
| 📄 PDF | Human-readable financial reports |
| 📊 Excel | Spreadsheet-based analysis |
| 📋 CSV | Portable structured data |

---

## 🔔 Notifications

FinSight includes an in-application notification system.

Features include:

- notification bell
- notification listing
- read/unread state
- filtering
- persistent notification state
- authenticated access
- CSRF protection
- user ownership validation

---

## 👤 Profile & Preferences

Users can manage:

- profile information
- application preferences
- language preferences
- currency display preferences
- theme preferences
- security settings
- TOTP configuration

---

## 🌍 Localization

FinSight supports:

| Code | Language |
|---|---|
| 🇬🇧 `en` | English |
| 🇮🇳 `hi` | Hindi |
| 🇯🇵 `ja` | Japanese |
| 🇩🇪 `de` | German |
| 🇫🇷 `fr` | French |
| 🇪🇸 `es` | Spanish |
| 🇮🇳 `mr` | Marathi |

Currency is supported as a display preference; it is not intended to perform real-time foreign exchange conversion.

---

## 🎨 Theme & UI

The application includes:

- light/dark theme support
- persisted theme preference
- responsive navigation
- dashboard cards
- visual financial indicators
- consistent iconography
- responsive layouts
- mobile navigation behavior
- local Font Awesome assets

---

## 📱 Responsive Design

Responsive design was treated as an implementation requirement.

The interface was refined for:

```text
📱 Mobile
   ↓
📲 Tablet
   ↓
💻 Desktop
```

Responsive improvements include:

- mobile sidebar drawer
- navigation overlay
- Escape-key handling
- outside-click handling
- body scroll locking
- ARIA considerations
- responsive authentication layouts
- responsive dashboard cards
- adaptive chart containers
- mobile-friendly navbar behavior
- prevention of unnecessary horizontal overflow
- desktop layout preservation

The mobile interface was reviewed using phone-sized layouts, including dashboard cards, navigation, charts, and spacing.

---

# 🧠 Product Design Philosophy

FinSight follows four principles:

### 1. Track
Record financial information easily.

### 2. Understand
Transform financial records into understandable visual information.

### 3. Plan
Use budgets, investments, and goals for forward-looking organization.

### 4. Act
Use insights, recommendations, and reports to turn information into action.

```text
TRACK → UNDERSTAND → PLAN → ACT
```

---

# 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| 🐍 Backend | Python |
| 🌐 Web Framework | Flask |
| 🎨 Frontend | HTML5, CSS3, JavaScript |
| 📊 Visualization | Chart.js |
| 🗄️ Development Database | SQLite |
| 🐘 Production Database | PostgreSQL |
| 🔐 Authentication | Flask session architecture |
| 🔒 2FA | TOTP |
| 📄 Reporting | CSV / PDF / Excel |
| 🖥️ Production Server | Gunicorn |
| ☁️ Deployment | Render |
| 💓 Monitoring | UptimeRobot |
| 🔧 Version Control | Git + GitHub |

---

# 🏗️ System Architecture

```text
                           ┌──────────────────────┐
                           │        USER          │
                           │ Browser / Mobile     │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │     Flask Web App    │
                           │                      │
                           │ Routes / Controllers │
                           │ Business Logic       │
                           │ Authentication       │
                           │ Financial Analytics  │
                           └──────────┬───────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
        ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐
        │   Frontend     │  │ Financial       │  │ Security        │
        │ HTML/CSS/JS    │  │ Analytics       │  │ Sessions        │
        │ Templates      │  │ Charts          │  │ CSRF            │
        │ Responsive UI  │  │ Recommendations │  │ Remember Me     │
        └────────────────┘  └─────────────────┘  │ TOTP            │
                                                 └────────┬────────┘
                                                          │
                                                          ▼
                                             ┌────────────────────────┐
                                             │       Database         │
                                             │ SQLite / PostgreSQL    │
                                             └────────────────────────┘
```

---

# 🔄 Application Workflow

## New User

```text
Landing Page
     │
     ▼
Registration
     │
     ▼
Account Created
     │
     ▼
Login
     │
     ▼
Dashboard
```

## Returning User

```text
Login
  │
  ├───────────────┐
  │               │
  ▼               ▼
Remember Me     TOTP
  │               │
  └───────┬───────┘
          ▼
      Dashboard
          │
          ├── Expenses
          ├── Budget
          ├── Investments
          ├── Goals
          ├── Reports
          ├── Notifications
          └── Profile / Preferences
```

---

# 🗄️ Database Architecture

FinSight uses a relational data model organized around authenticated users and their financial information.

```text
                         ┌──────────────┐
                         │    USERS     │
                         └──────┬───────┘
                                │
              ┌─────────────────┼──────────────────┐
              │                 │                  │
              ▼                 ▼                  ▼
        ┌──────────┐     ┌─────────────┐    ┌────────────┐
        │ Sessions │     │ Remember Me │    │    TOTP    │
        └──────────┘     └─────────────┘    └────────────┘
              │
              ├──────────────┬───────────────┬───────────────┐
              ▼              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐    ┌────────────┐   ┌─────────┐
        │ Expenses │   │ Budgets  │    │ Investments│   │  Goals  │
        └──────────┘   └──────────┘    └────────────┘   └─────────┘
              │
              ├──────────────────┐
              ▼                  ▼
        ┌───────────┐      ┌──────────────┐
        │ Analytics │      │ Notifications│
        └───────────┘      └──────────────┘
```

---

# 🔐 Security Architecture

## Password Security

Passwords are stored using secure password hashing rather than plaintext.

```text
Plain Password
      │
      ▼
Password Hashing
      │
      ▼
Stored Password Hash
      │
      ▼
Verification During Login
```

## CSRF Protection

State-changing authentication operations are protected using CSRF validation.

## Session Tracking

Protected requests require a valid authenticated user session with appropriate session validation.

Controls include:

- inactivity timeout
- absolute timeout
- revocation
- ownership validation
- secure cookie configuration

## Remember Me

Long-lived authentication uses dedicated token records and hashed token storage.

## TOTP

Authenticator-app-based TOTP provides an additional security factor independently of email.

## Authorization

Financial data is associated with the authenticated user and protected using ownership checks.

---

# 🗃️ Database Migration System

Production database changes are handled using a forward-only migration system.

The migration runner:

1. Discovers migration files numerically.
2. Checks the migration tracking table.
3. Identifies unapplied migrations.
4. Applies migrations in order.
5. Records a migration only after successful execution.
6. Uses locking to avoid conflicting migration execution.
7. Stops safely when a migration fails.

```text
Migration Files
      │
      ▼
Numeric Discovery
      │
      ▼
schema_migrations
      │
      ▼
Find Unapplied Versions
      │
      ▼
Apply Migration
      │
      ▼
Successful?
   ┌──┴──┐
  Yes    No
   │      │
   ▼      ▼
Record   Stop
```

---

# 📂 Project Structure

```text
FinSight/
│
├── app.py
├── config.py
├── db.py
├── email_service.py
├── i18n.py
│
├── database/
│   ├── migrations/
│   │   ├── 000_*.sql
│   │   ├── 001_*.sql
│   │   ├── ...
│   │   └── 016_*.sql
│   │
│   └── migrate_investments.py
│
├── templates/
│   ├── dashboard/
│   ├── expenses/
│   ├── budgets/
│   ├── investments/
│   ├── goals/
│   ├── reports/
│   ├── profile/
│   ├── notifications/
│   └── authentication/
│
├── static/
│   ├── css/
│   ├── js/
│   ├── images/
│   └── vendor/
│       └── fontawesome/
│
├── tests/
│   ├── authentication
│   ├── database
│   ├── financial modules
│   ├── localization
│   ├── security
│   └── integration
│
├── requirements.txt
├── render.yaml
├── .python-version
├── .env.example
└── README.md
```

---

# 📊 Financial Analytics

FinSight's analytics layer connects multiple financial modules.

```text
Income
   │
   ├──────────────┐
   │              │
   ▼              ▼
Expenses       Budget
   │              │
   └──────┬───────┘
          ▼
   Financial Analysis
          │
    ┌─────┼──────────────┐
    │     │              │
    ▼     ▼              ▼
 Health  Spending      Budget vs
 Score   Patterns      Spending
    │     │              │
    └─────┴──────┬───────┘
                 ▼
          Recommendations
```

The objective is to make financial data understandable rather than simply displaying database records.

---

# 📄 Reporting & Export Architecture

```text
Financial Data
      │
      ▼
Reporting Data Layer
      │
      ├──────────► CSV
      │
      ├──────────► Excel
      │
      └──────────► PDF
```

The export system keeps reporting functionality separate from core financial operations.

---

# 🧪 Testing & Quality Assurance

Testing was continuously used throughout development.

The final project state reached:

```text
426 passed
```

### Full Test Suite

```bash
python -m pytest -q
```

### Compilation

```bash
python -m compileall -q .
```

### Git Diff Validation

```bash
git diff --check
```

### Testing Focus

The test suite covers areas including:

- authentication
- registration
- session behavior
- security
- database bootstrap
- migrations
- localization
- financial modules
- application behavior
- regression scenarios

The final OTP/Forgot Password removal was followed by a complete regression run to ensure the remaining authentication and financial functionality stayed intact.

---

# 🚀 Production Deployment

FinSight is live on Render.

## Production URL

**https://infosys-springboard-finsight-project.onrender.com/**

### Production Stack

```text
GitHub
   │
   ▼
Render
   │
   ├── Gunicorn
   ├── Flask
   └── PostgreSQL
```

### Production WSGI Server

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

### Production Database

The deployed environment uses PostgreSQL rather than the local SQLite development database.

### Deployment Configuration

The project includes configuration for:

- Python runtime
- dependency installation
- Gunicorn startup
- health checks
- production configuration
- database migrations where supported

---

# 💓 Health Monitoring

FinSight is monitored externally using **UptimeRobot**.

## Current Monitor

```text
Monitor:
FinSight Production

Type:
HTTP/S

Endpoint:
https://infosys-springboard-finsight-project.onrender.com/health

Frequency:
Every 5 minutes

Monitoring:
UptimeRobot Free

Expected Result:
HTTP 200
```

The current monitor has successfully reported the application as **Up** and provides availability history and outage notifications.

### Monitoring Flow

```text
UptimeRobot
     │
     │ every 5 minutes
     ▼
FinSight /health
     │
     ▼
HTTP 200
     │
     ▼
Render service receives traffic
```

This also provides external visibility into application availability.

---

# 📡 Health Endpoint

FinSight exposes:

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

The endpoint is intentionally lightweight and does not require:

- user authentication
- session state
- CSRF token
- financial data
- dashboard rendering

It is suitable for:

- Render health checks
- external uptime monitoring
- deployment smoke testing
- basic service availability verification

---

# ⚙️ Local Installation

## Prerequisites

- Python 3.10+
- Git
- pip
- PostgreSQL if running against PostgreSQL locally

## 1. Clone

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd FinSight
```

## 2. Virtual Environment

### Windows

```powershell
python -m venv .venv
.venv\Scriptsctivate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment

Create `.env` based on:

```text
.env.example
```

Never commit production secrets.

## 5. Run Migrations

```bash
python -m database.migrate_investments
```

## 6. Start

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

# 🔑 Environment Configuration

Typical configuration includes:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=your-database-url
```

Depending on the environment, additional configuration may be required.

### Never commit

```text
.env
```

Never expose:

- Flask secret keys
- database credentials
- API keys
- authentication secrets
- production passwords

---

# 🔒 Production Security & Reliability

Production hardening included:

### WSGI

Development Flask serving was replaced in production with Gunicorn.

### HTTPS

Production traffic is served through Render HTTPS.

### HSTS

Production-only HSTS configuration is enabled when appropriate.

### Proxy Awareness

Production proxy configuration is handled using ProxyFix so Flask can correctly interpret forwarded HTTPS/host information.

### Database

Production uses PostgreSQL with migration tracking.

### Health Monitoring

A dedicated `/health` endpoint is available to Render and UptimeRobot.

### Secrets

Sensitive configuration is supplied through environment variables rather than committed source files.

---

# 🛠️ Engineering Work & Production Hardening

FinSight was taken beyond a local Flask application and prepared for real deployment.

### Application Server

```text
Flask development server
        ↓
Gunicorn production WSGI
```

### Database

```text
Local development
     ↓
SQLite

Production
     ↓
PostgreSQL
```

### Database Evolution

```text
Manual schema changes
        ↓
Tracked migrations
```

### Service Monitoring

```text
No external monitoring
        ↓
/health
        ↓
UptimeRobot
```

### Deployment

```text
Local application
       ↓
GitHub
       ↓
Render
       ↓
Live application
```

---

# 🐛 Challenges & Solutions

| Challenge | Approach / Solution |
|---|---|
| Flask application needed production serving | Added Gunicorn |
| Production database required controlled schema evolution | Implemented migration tracking |
| Render needed a health endpoint | Added `/health` |
| Mobile UI had layout issues | Performed responsive audits and targeted responsive fixes |
| Desktop layout needed to remain stable | Scoped responsive changes to mobile/tablet behavior |
| Authentication required multiple security layers | Implemented CSRF, sessions, Remember Me, TOTP and authorization |
| External email delivery created unnecessary dependency for authentication | Removed registration/password-reset OTP workflows while preserving core authentication |
| Password-reset infrastructure became obsolete | Removed active workflow and added forward migration for obsolete database infrastructure |
| PDF generation can differ between environments | Added environment-compatible font handling |
| Production database differs from local development | Added PostgreSQL deployment support and migrations |
| Application needed external availability visibility | Integrated UptimeRobot |
| Responsive UI needed actual phone testing | Reviewed mobile layouts using phone-sized viewports |

---

# 🔐 OTP / Password-Reset Architecture Decision

An important architectural change was made during finalization.

The application originally contained email-based OTP workflows for:

- registration verification
- password reset

During production preparation, it became clear that external email delivery was not required for the core authentication requirements.

The registration flow was simplified to:

```text
Registration
     ↓
Validation
     ↓
Account Creation
     ↓
Login
```

The obsolete Forgot Password/password-reset workflow was subsequently removed.

The following security capabilities were intentionally preserved:

- password hashing
- CSRF protection
- tracked sessions
- Remember Me
- TOTP authenticator-app 2FA
- authorization
- ownership checks
- secure cookies

Historical migrations are retained as migration history, while obsolete active database infrastructure is handled through forward-only migrations rather than rewriting historical migrations.

---

# 🧩 Why the Project Goes Beyond CRUD

A basic finance CRUD application might look like:

```text
Create
Read
Update
Delete
```

FinSight extends that model:

```text
                 ┌───────────────┐
                 │     CRUD      │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Analytics   │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ Visualization │
                 └───────┬───────┘
                         │
                         ▼
                 ┌────────────────┐
                 │ Recommendations│
                 └───────┬────────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Reporting   │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Production  │
                 │   Deployment  │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Monitoring  │
                 └───────────────┘
```

The project was intentionally developed as a complete software product rather than only a database-backed web interface.

---

# 📚 Development Journey

## Milestone 1 — Core Finance

Implemented:

- authentication foundation
- user accounts
- expenses
- budgets
- core dashboard functionality

## Milestone 2 — Financial Expansion

Added:

- investments
- financial goals

## Milestone 3 — Financial Intelligence

Added:

- Financial Health Score
- Spending Pattern Analysis
- Budget vs Spending Analysis
- Spending Recommendations

This milestone moved the application beyond basic record management into financial analytics.

## Milestone 4 — Complete Product Experience

Added and refined:

- Reports Overview
- reporting data layer
- CSV export
- PDF export
- Excel export
- profile
- preferences
- security settings
- TOTP 2FA
- notifications
- theme persistence
- multilingual support
- currency display preferences
- responsive navigation
- mobile sidebar
- UI/security polish

## Production Readiness

The project was then prepared through:

- Gunicorn
- PostgreSQL
- database migration tracking
- health endpoint
- production proxy handling
- production security configuration
- deployment configuration
- responsive fixes
- regression testing
- Render deployment

## Production Monitoring

Finally:

```text
Live FinSight
     ↓
/health
     ↓
UptimeRobot
     ↓
Every 5 minutes
     ↓
External availability monitoring
```

---

# 🧠 What I Learned

## 💻 Full-Stack Development

- Python
- Flask
- HTML
- CSS
- JavaScript
- Chart.js
- SQL
- relational database design
- server-side rendering

## 🔐 Application Security

- password hashing
- CSRF protection
- authentication
- authorization
- session management
- session expiration
- session revocation
- Remember Me security
- TOTP 2FA
- secure cookies
- ownership validation

## 🗄️ Database Engineering

- relational schema design
- SQLite
- PostgreSQL
- migration architecture
- migration tracking
- production database changes

## 📊 Data & Analytics

- financial aggregation
- spending analysis
- budget comparisons
- data visualization
- financial health calculations
- recommendations
- report generation

## 🎨 Frontend Engineering

- responsive layouts
- mobile navigation
- dashboard UI
- chart containers
- theme support
- localization
- accessibility considerations

## 🚀 DevOps & Deployment

- Git
- GitHub
- Render
- Gunicorn
- PostgreSQL
- environment configuration
- deployment debugging
- health checks
- uptime monitoring

## 🧪 Quality Assurance

- automated testing
- regression testing
- compilation checks
- diff validation
- database migration testing
- responsive testing
- deployment smoke testing

---

# 🔮 Future Improvements

Potential future improvements include:

### 🤖 Advanced Financial Intelligence

- machine-learning-based spending prediction
- anomaly detection
- personalized financial forecasting
- smarter financial recommendations

### 📈 Investment Analytics

- investment performance analysis
- portfolio visualization
- asset allocation analytics
- historical performance tracking

### 📱 Platform Expansion

- Progressive Web App support
- mobile application
- offline capabilities

### ☁️ Infrastructure

- automated database backups
- stronger observability
- centralized logging
- performance monitoring

### 🔗 Integrations

- financial institution integrations
- secure transaction imports
- automated financial data synchronization

### 📊 Advanced Reporting

- richer financial reports
- scheduled reports
- additional export formats
- customizable reporting dashboards

---

# 📌 Project Highlights

```text
┌──────────────────────────────────────────────────────────┐
│                       FinSight                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  💰 Personal Finance Management                          │
│  📊 Financial Analytics                                  │
│  ❤️ Financial Health Score                               │
│  📉 Spending Pattern Analysis                            │
│  ⚖️ Budget vs Spending                                  │
│  💡 Spending Recommendations                             │
│  📈 Investment Tracking                                  │
│  🏆 Financial Goals                                      │
│  📑 PDF / Excel / CSV Reports                            │
│  🔔 Notifications                                        │
│  🌍 Multilingual Support                                 │
│  🎨 Theme Preferences                                    │
│  📱 Responsive UI                                        │
│  🔐 CSRF + Sessions + Remember Me + TOTP                │
│  🗄️ SQLite + PostgreSQL                                  │
│  🚀 Render Deployment                                    │
│  💓 UptimeRobot Monitoring                               │
│  🧪 Automated Regression Testing                         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

# 🌐 Live Project

<div align="center">

### 🚀 Try FinSight

**[Open the Live Application](https://infosys-springboard-finsight-project.onrender.com/)**

### 💓 Health Check

**[Open `/health`](https://infosys-springboard-finsight-project.onrender.com/health)**

</div>

---

# 👨‍💻 Developer

<div align="center">

## Narayan Kishor Adhude

**Computer Science & Engineering Graduate**

**Full-Stack Developer • AI/ML Enthusiast**

FinSight represents hands-on work across application development, financial analytics, authentication, security, responsive UI engineering, database design, deployment, and production monitoring.

The project was developed with the objective of transforming a personal-finance application idea into a complete, tested, deployed, and monitored web product.

</div>

---

# ⭐ Support

If you find FinSight useful or interesting:

- ⭐ Star the repository
- 🍴 Fork the project
- 🐛 Report issues
- 💡 Suggest improvements
- 🤝 Contribute

---

<div align="center">

## 💚 FinSight

### **See Smarter. Spend Better. Live Brighter.**

**Built with curiosity, persistence, problem-solving, and continuous learning.**

Made with ❤️ by **Narayan Kishor Adhude**

</div>
