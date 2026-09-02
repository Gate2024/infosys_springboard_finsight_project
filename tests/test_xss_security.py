import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _render_budget_modal(budget):
    dashboard_source = (ROOT / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")
    harness = f"""
const elements = {{
  viewModal: {{
    classList: {{ add() {{}}, remove() {{}} }}
  }},
  'modal-body-content': {{ innerHTML: '' }}
}};
global.document = {{
  addEventListener() {{}},
  getElementById(id) {{ return elements[id] || null; }},
  querySelectorAll() {{ return []; }}
}};
global.fetch = async () => ({{
  json: async () => ({{ success: true, budget: {json.dumps(budget)} }})
}});

eval({json.dumps(dashboard_source)});
openViewModal(1).then(() => process.stdout.write(elements['modal-body-content'].innerHTML));
"""
    result = subprocess.run(
        ["node", "-e", harness],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_budget_modal_escapes_untrusted_fields_at_innerhtml_boundary():
    malicious = '<script>alert(1)</script>'
    output = _render_budget_modal(
        {
            "budget_id": 7,
            "budget_name": malicious,
            "category": '<img src=x onerror=alert(1)>',
            "currency": '"><script>alert(1)</script>',
            "description": "'><script>alert(1)</script>",
            "start_date": "\\\"; <img src=x onerror=alert(1)>",
            "end_date": "';\\\\<script>alert(1)</script>",
            "priority": malicious,
            "status": malicious,
            "notes": malicious,
            "color_label": '"><img src=x onerror=alert(1)>',
            "budget_icon": '"><script>alert(1)</script>',
            "budget_amount": "1000",
            "spent_amount": "100",
            "remaining_amount": "900",
            "is_recurring": False,
        }
    )

    assert malicious not in output
    assert "<script" not in output
    assert "<img" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "&#039;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert "background: #0E5A4E" in output
    assert 'class="fa-solid fa-wallet"' in output
    assert "priority-Medium" in output
    assert ">Active</span>" in output
    assert 'href="/budget/edit/7"' in output


def test_budget_modal_preserves_supported_values():
    output = _render_budget_modal(
        {
            "budget_id": 8,
            "budget_name": "Monthly Food",
            "category": "Food",
            "currency": "USD",
            "description": "Planned monthly spending",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "priority": "High",
            "status": "Completed",
            "notes": "Review at month end",
            "color_label": "#0E5A4E",
            "budget_icon": "fa-wallet",
            "budget_amount": "1000",
            "spent_amount": "100",
            "remaining_amount": "900",
            "is_recurring": True,
        }
    )

    assert "Monthly Food" in output
    assert "Food • USD" in output
    assert "priority-High" in output
    assert ">High</span>" in output
    assert ">Completed</span>" in output
    assert "Review at month end" in output
    assert 'class="fa-solid fa-wallet"' in output


def test_expense_modal_keeps_existing_html_escaping():
    expenses_source = (ROOT / "static" / "js" / "expenses.js").read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in expenses_source
    assert "${escapeHtml(expense.description || \"Untitled expense\")}" in expenses_source
    assert "${escapeHtml(expense.category || \"\")}" in expenses_source
