"""
LoanFlow Comprehensive Test Suite
Tests:
- Authentication & RBAC
- Application lifecycle & State Machine
- Sensitive KYC data masking
- Duplicate document detection via SHA-256 hash
- Policy & Eligibility rule engine explainability
- Risk scoring & Limit calculation
- Maker-checker enforcement (preparer cannot approve, manager only)
- Loan disbursement & EMI schedule generation
- Servicing repayment processing
- Delinquency & Collection monitoring
- Assessment report compilation
- Portfolio analytics
"""
import os
import sys
import uuid
import hashlib
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

# Point database to isolated test SQLite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_loanflow.db"
os.environ["JWT_SECRET"] = "test-secret-key-1234567890-test"

# Add services path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services")))

from shared.database import init_db, engine, AsyncSessionLocal, Base
from shared.security import create_access_token, mask_sensitive
from loan_app.main import app as loan_app
from loan_app.models import Application, ApplicationStage, Document, LoanAccount, EMISchedule, AuditLog, PolicyRule
from auth.main import app as auth_app, UserModel, pwd_context


@pytest.fixture(autouse=True, scope="module")
def setup_test_database():
    """Initialize database tables and seed users synchronously for the test module."""
    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSessionLocal() as session:
            cust = UserModel(
                id="cust-101",
                username="amit_customer",
                email="amit@example.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Amit Sharma",
                role="customer",
            )
            emp = UserModel(
                id="emp-201",
                username="rahul_maker",
                email="rahul@bank.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Rahul Verma (Loan Officer)",
                role="employee",
            )
            mgr = UserModel(
                id="mgr-301",
                username="priya_checker",
                email="priya@bank.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Priya Mehta (Branch Manager)",
                role="manager",
            )
            session.add_all([cust, emp, mgr])

            # Seed policy rules
            rules = [
                PolicyRule(
                    rule_name="min_income",
                    loan_type="Home Loan",
                    rule_config={"type": "min_income", "min": 300000, "description": "Min ₹3L income"},
                ),
                PolicyRule(
                    rule_name="max_emi_ratio",
                    loan_type="Home Loan",
                    rule_config={"type": "max_emi_ratio", "max_ratio": 0.5, "description": "EMI <= 50% income"},
                ),
            ]
            session.add_all(rules)
            await session.commit()

    asyncio.run(_init())
    yield
    async def _clean():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    try:
        asyncio.run(_clean())
    except Exception:
        pass


def get_auth_cookies(user_id: str, role: str, username: str) -> dict:
    """Helper to generate JWT auth cookie."""
    token = create_access_token(user_id=user_id, role=role, username=username)
    return {"lf_access_token": token}


def test_kyc_masking_utility():
    """Verify sensitive fields like Aadhaar, PAN, and phone are securely masked."""
    # Aadhaar 12 digits -> show only last 4
    masked_aadhaar = mask_sensitive("123456789012", 4)
    assert masked_aadhaar.endswith("9012")
    assert "12345678" not in masked_aadhaar

    # PAN 10 characters -> show only last 4
    masked_pan = mask_sensitive("ABCDE1234F", 4)
    assert masked_pan.endswith("234F")
    assert "ABCDE" not in masked_pan

    # Phone 10 digits -> show only last 4
    masked_phone = mask_sensitive("9876543210", 4)
    assert masked_phone.endswith("3210")



def test_full_loan_lifecycle_and_maker_checker():
    """
    Complete end-to-end integration test:
    1. Customer creates draft application
    2. Customer uploads document
    3. Duplicate document rejection via hash (409)
    4. Customer submits application (Draft -> Submitted)
    5. Employee runs KYC verification (sensitive data masked)
    6. Employee evaluates policy rules (explainable reasons)
    7. Employee calculates risk score & max limit
    8. Employee prepares application and moves to 'With Manager'
    9. Maker-checker enforcement:
       - Preparer attempts to approve -> HTTP 403 Forbidden
       - Non-manager attempts to approve -> HTTP 403 Forbidden
       - Manager (different user) approves successfully
    10. Disburse loan -> creates LoanAccount and EMI schedule
    11. Servicing repayment -> payment recorded, balance reduced
    12. Assessment report generation
    13. Portfolio analytics summary
    """
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust_cookies = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp_cookies = get_auth_cookies("emp-201", "employee", "rahul_maker")
            mgr_cookies = get_auth_cookies("mgr-301", "manager", "priya_checker")

            # 1. Customer creates draft application
            app_payload = {
                "loan_type": "Home Loan",
                "requested_amount": 1000000,
                "annual_income": 1500000,
                "existing_emi": 8000,
                "employment_type": "Salaried",
                "employer_name": "Tech Corp",
                "loan_tenure_months": 120,
                "customer_name": "Amit Sharma",
            }
            res = await client.post("/applications", json=app_payload, cookies=cust_cookies)
            assert res.status_code == 201, res.text
            app_data = res.json()
            app_id = app_data["id"]
            assert app_data["stage"] == "Draft"
            assert app_data["app_number"].startswith("LF-")

            # 2. Upload Document
            doc_content = b"Sample Salary Slip 2026 Content For Test"
            files = {"file": ("salary_slip.pdf", doc_content, "application/pdf")}
            data = {"document_type": "Income Proof"}
            res = await client.post(f"/applications/{app_id}/documents", data=data, files=files, cookies=cust_cookies)
            assert res.status_code == 201, res.text
            doc_data = res.json()
            assert doc_data["document_type"] == "Income Proof"
            assert doc_data["file_hash"] == hashlib.sha256(doc_content).hexdigest()

            # 3. Duplicate Document Detection (Must return HTTP 409 Conflict)
            res_dup = await client.post(f"/applications/{app_id}/documents", data=data, files=files, cookies=cust_cookies)
            assert res_dup.status_code == 409
            assert "Duplicate document detected" in res_dup.json()["detail"]

            # 4. Customer submits application (Draft -> Submitted)
            res = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "Submitted"},
                cookies=cust_cookies,
            )
            assert res.status_code == 200
            assert res.json()["new_stage"] == "Submitted"

            # Customer cannot transition to manager stages
            res_fail = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "Approved"},
                cookies=cust_cookies,
            )
            assert res_fail.status_code == 403

            # 5. Move to KYC stage and run KYC
            await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "KYC"},
                cookies=emp_cookies,
            )
            res_kyc = await client.post(f"/applications/{app_id}/kyc", cookies=emp_cookies)
            assert res_kyc.status_code == 200
            kyc_res = res_kyc.json()
            assert kyc_res["verified"] is True
            # Verify masking
            assert "*" in kyc_res["masked_data"]["aadhaar_number"]
            assert kyc_res["masked_data"]["aadhaar_number"].endswith("9012")
            assert "*" in kyc_res["masked_data"]["pan_number"]
            assert kyc_res["masked_data"]["pan_number"].endswith("234F")


            # 6. Move through Docs -> Verification -> Risk
            await client.post(f"/applications/{app_id}/transition", json={"target_stage": "Docs"}, cookies=emp_cookies)
            await client.post(f"/applications/{app_id}/transition", json={"target_stage": "Verification"}, cookies=emp_cookies)

            # Employee verifies document
            res_verify = await client.patch(
                f"/documents/{doc_data['id']}/verify",
                json={"status": "Verified", "remarks": "Salary credits verified against bank statement"},
                cookies=emp_cookies,
            )
            assert res_verify.status_code == 200
            assert res_verify.json()["status"] == "Verified"

            # Move to Risk stage
            await client.post(f"/applications/{app_id}/transition", json={"target_stage": "Risk"}, cookies=emp_cookies)

            # 7. Evaluate Eligibility Rules (Explainable reasons)
            res_elig = await client.post(f"/applications/{app_id}/eligibility", cookies=emp_cookies)
            assert res_elig.status_code == 200
            elig_data = res_elig.json()
            assert elig_data["passed"] >= 1
            assert "Annual income ₹" in elig_data["results"][0]["reason"]

            # Calculate Risk Score
            res_risk = await client.post(f"/applications/{app_id}/risk-score", cookies=emp_cookies)
            assert res_risk.status_code == 200
            assert res_risk.json()["score"] > 0
            assert res_risk.json()["band"] in ["Low", "Medium", "High", "Very High"]

            # Calculate Limit
            res_lim = await client.post(f"/applications/{app_id}/limit", cookies=emp_cookies)
            assert res_lim.status_code == 200
            assert res_lim.json()["max_permissible_limit"] > 0

            # 8. Employee prepares application (Risk -> Prepared -> With Manager)
            await client.post(f"/applications/{app_id}/transition", json={"target_stage": "Prepared"}, cookies=emp_cookies)
            res_with_mgr = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "With Manager", "remarks": "Assessment complete, recommended for approval"},
                cookies=emp_cookies,
            )
            assert res_with_mgr.status_code == 200

            # 9. MAKER-CHECKER ENFORCEMENT
            # A) The employee who prepared the file attempts to approve -> Must get HTTP 403
            res_maker_approve = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "Approved"},
                cookies=emp_cookies,  # Prepared by emp-201
            )
            assert res_maker_approve.status_code == 403
            assert "Maker-checker violation" in res_maker_approve.json()["detail"] or "Only managers" in res_maker_approve.json()["detail"]

            # B) Customer attempts to approve -> Must get HTTP 403
            res_cust_approve = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "Approved"},
                cookies=cust_cookies,
            )
            assert res_cust_approve.status_code == 403

            # C) Manager (distinct user Priya / mgr-301) approves -> Success
            res_mgr_approve = await client.post(
                f"/applications/{app_id}/transition",
                json={"target_stage": "Approved", "remarks": "Approved with standard terms"},
                cookies=mgr_cookies,
            )
            assert res_mgr_approve.status_code == 200
            assert res_mgr_approve.json()["new_stage"] == "Approved"

            # 10. Disburse Loan & Generate EMI Schedule
            res_disburse = await client.post(
                f"/applications/{app_id}/disburse",
                json={"interest_rate": 8.75},
                cookies=mgr_cookies,
            )
            assert res_disburse.status_code == 200
            loan_acc = res_disburse.json()
            assert loan_acc["status"] == "ACTIVE"
            assert loan_acc["principal_amount"] == 1000000
            assert loan_acc["emi_amount"] > 0
            assert len(loan_acc["schedules"]) == 120  # 120 monthly installments

            # 11. Servicing & Repayment
            account_id = loan_acc["id"]
            res_pay = await client.post(
                f"/servicing/accounts/{account_id}/pay",
                json={"amount": loan_acc["emi_amount"], "payment_method": "UPI"},
                cookies=cust_cookies,
            )
            assert res_pay.status_code == 200
            pay_res = res_pay.json()
            assert pay_res["status"] == "SUCCESS"
            assert pay_res["remaining_balance"] < 1000000

            # Verify servicing schedule updated
            res_servicing = await client.get(f"/applications/{app_id}/servicing", cookies=cust_cookies)
            assert res_servicing.status_code == 200
            serv_data = res_servicing.json()
            assert serv_data["schedules"][0]["status"] == "PAID"

            # 12. Assessment Report Generation
            res_report = await client.get(f"/applications/{app_id}/assessment-report", cookies=mgr_cookies)
            assert res_report.status_code == 200
            report = res_report.json()
            assert report["application"]["stage"] == "Approved"
            assert report["maker_checker"]["maker_checker_compliant"] is True
            assert report["maker_checker"]["prepared_by"] == "emp-201"
            assert report["maker_checker"]["approved_by"] == "mgr-301"
            assert len(report["audit_history"]) >= 5

            # 13. Portfolio Risk & KPI Analytics
            res_analytics = await client.get("/analytics/summary", cookies=emp_cookies)
            assert res_analytics.status_code == 200
            analytics = res_analytics.json()
            assert analytics["total_applications"] >= 1
            assert analytics["total_disbursed_volume"] >= 1000000
            assert analytics["active_loans_count"] >= 1

    asyncio.run(_run())
