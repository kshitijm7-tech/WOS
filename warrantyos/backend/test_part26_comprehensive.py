"""
Part 2.6 Comprehensive Test Suite — WarrantyOS
Validates Production Intelligence, Evaluation, Observability, Retrieval Hardening & Failure Injection.
Runs completely offline against local SQLite/Postgres DB using FastAPI TestClient.
"""

import os
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User, Role, Customer, Admin
from app.models.product import Product, ProductSerial, WarrantyPolicy, Retailer
from app.models.claim import Claim, ClaimEvidence, ClaimDecision, AIExecution, AIExecutionStage, ClaimTimeline
from app.models.intelligence import HistoricalCase
from app.services.embedding_provider import MockEmbeddingProvider, VectorDimensionMismatchError, get_embedding_provider
from app.services.vector_store import MemoryVectorStore, PgVectorStore, get_vector_store
from app.services.historical_case_service import find_similar_cases
from app.services.policy_knowledge_service import retrieve_policy_knowledge, KeywordPolicyRetriever, get_policy_retriever
from app.services.document_extractor import MockDocumentExtractor, OCRDocumentExtractor, get_document_extractor
from app.services.evidence_consistency_service import check_evidence_consistency
from app.services.ai_evaluation import evaluate_claims, evaluate_retrieval_quality, get_evaluation_dataset
from app.services.golden_dataset import get_golden_dataset, GOLDEN_SCENARIOS
from app.services.ai_orchestrator import create_execution, execute_claim_analysis


class TestPart26Comprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure new tables and columns exist in SQLite/Postgres
        Base.metadata.create_all(bind=engine)

        # Alter table for SQLite local dev if missing Part 2.6 columns
        with engine.connect() as conn:
            from sqlalchemy import text
            for col_def in [
                ("input_token_count", "INTEGER"),
                ("output_token_count", "INTEGER"),
                ("estimated_cost", "FLOAT DEFAULT 0.0"),
                ("latency_ms", "INTEGER"),
                ("provider_status", "VARCHAR(50)"),
                ("fallback_used", "BOOLEAN DEFAULT 0"),
                ("fallback_reason", "VARCHAR(255)"),
                ("failure_class", "VARCHAR(50)"),
                ("requested_provider", "VARCHAR(50)"),
                ("actual_provider", "VARCHAR(50)"),
                ("requested_model", "VARCHAR(100)"),
                ("actual_model", "VARCHAR(100)"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE ai_executions ADD COLUMN {col_def[0]} {col_def[1]}"))
                    conn.commit()
                except Exception:
                    pass

        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()


        # Seed essential test users and entities if missing
        cls.customer_role = cls.db.query(Role).filter(Role.name == "customer").first()
        if not cls.customer_role:
            cls.customer_role = Role(name="customer")
            cls.db.add(cls.customer_role)

        cls.admin_role = cls.db.query(Role).filter(Role.name == "admin").first()
        if not cls.admin_role:
            cls.admin_role = Role(name="admin")
            cls.db.add(cls.admin_role)

        cls.db.commit()

        # Users
        cls.user_cust1 = cls._get_or_create_user("cust26_1@test.com", cls.customer_role)
        cls.user_cust2 = cls._get_or_create_user("cust26_2@test.com", cls.customer_role)
        cls.user_admin = cls._get_or_create_user("admin26@test.com", cls.admin_role)

        cls.cust1 = cls._get_or_create_customer(cls.user_cust1)
        cls.cust2 = cls._get_or_create_customer(cls.user_cust2)
        cls.admin_ent = cls._get_or_create_admin(cls.user_admin)

        # Tokens
        cls.cust1_token = create_access_token(cls.user_cust1.email, "customer")
        cls.cust2_token = create_access_token(cls.user_cust2.email, "customer")
        cls.admin_token = create_access_token(cls.user_admin.email, "admin")


        # Product & Policy
        cls.product = cls.db.query(Product).filter(Product.name == "Test Smart Washer 2.6").first()
        if not cls.product:
            cls.product = Product(name="Test Smart Washer 2.6", category="Washing Machine", sku="SW-2600", warranty_period_months=24)
            cls.db.add(cls.product)
            cls.db.commit()
            cls.db.refresh(cls.product)

        cls.policy = cls.db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == cls.product.id).first()
        if not cls.policy:
            cls.policy = WarrantyPolicy(
                product_id=cls.product.id,
                warranty_months=24,
                covered=["motor", "display", "heating"],
                not_covered=["physical damage", "accidental", "liquid"],
                conditions="Requires valid proof of purchase"
            )
            cls.db.add(cls.policy)
            cls.db.commit()

        # Serial
        cls.serial = cls.db.query(ProductSerial).filter(ProductSerial.serial_number == "SN-PART26-001").first()
        if not cls.serial:
            cls.serial = ProductSerial(
                serial_number="SN-PART26-001",
                product_id=cls.product.id,
                owner_customer_id=cls.cust1.id,
                purchase_date=date(2025, 1, 15)
            )
            cls.db.add(cls.serial)
            cls.db.commit()

        # Retailer
        cls.retailer = cls.db.query(Retailer).filter(Retailer.name == "Official Appliance Store").first()
        if not cls.retailer:
            cls.retailer = Retailer(name="Official Appliance Store", region="North")
            cls.db.add(cls.retailer)
            cls.db.commit()


        # Claim 1 for Customer 1
        cls.claim1 = cls.db.query(Claim).filter(Claim.claim_code == "WR-26001").first()
        if not cls.claim1:
            cls.claim1 = Claim(
                claim_code="WR-26001",
                customer_id=cls.cust1.id,
                product_id=cls.product.id,
                serial_id=cls.serial.id,
                retailer_id=cls.retailer.id,
                fault_description="Motor grinding noise during spin cycle",
                fault_category="motor",
                status="SUBMITTED",
                purchase_date=date(2025, 1, 15),
                warranty_eligible=True,
                eligibility_reason="VALID: Purchase date within 24 months warranty",
                warranty_checked_at=datetime.now(timezone.utc),
            )
            cls.db.add(cls.claim1)
            cls.db.commit()
            cls.db.refresh(cls.claim1)

            # Add Evidence
            cls.ev_invoice = ClaimEvidence(
                claim_id=cls.claim1.id,
                evidence_type="INVOICE",
                file_path="./uploads/invoice_26001.pdf",
                stored_filename="invoice_26001.pdf",
                original_filename="receipt.pdf",
                mime_type="application/pdf",
                file_size=1024,
                uploaded_by_user_id=cls.user_cust1.id
            )
            cls.db.add(cls.ev_invoice)
            cls.db.commit()

        # Seed Historical Cases for retrieval testing
        if cls.db.query(HistoricalCase).count() < 3:
            cases = [
                HistoricalCase(product_id=cls.product.id, fault_category="motor", resolution="REPAIR", summary="Motor bearing replaced under warranty"),
                HistoricalCase(product_id=cls.product.id, fault_category="display", resolution="REPLACE", summary="Display board replaced due to control failure"),
                HistoricalCase(product_id=cls.product.id, fault_category="heating", resolution="REPAIR", summary="Heating element replaced"),
            ]
            cls.db.add_all(cases)
            cls.db.commit()

    @classmethod
    def _get_or_create_user(cls, email: str, role: Role) -> User:
        user = cls.db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, hashed_password="hashed_test_pass", full_name="Test User", role_id=role.id, is_active=True)
            cls.db.add(user)
            cls.db.commit()
            cls.db.refresh(user)
        return user


    @classmethod
    def _get_or_create_customer(cls, user: User) -> Customer:
        cust = cls.db.query(Customer).filter(Customer.user_id == user.id).first()
        if not cust:
            cust = Customer(user_id=user.id, phone="555-0199")
            cls.db.add(cust)
            cls.db.commit()
            cls.db.refresh(cust)
        return cust

    @classmethod
    def _get_or_create_admin(cls, user: User) -> Admin:
        adm = cls.db.query(Admin).filter(Admin.user_id == user.id).first()
        if not adm:
            adm = Admin(user_id=user.id, department="Engineering")
            cls.db.add(adm)
            cls.db.commit()
            cls.db.refresh(adm)
        return adm


    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # --- 1. SECURITY & RBAC TESTS ---
    def test_security_rbac_ai_health(self):
        """Test GET /api/admin/ai/health requires admin role (Customer = 403, Admin = 200)."""
        # Customer access -> 403 Forbidden
        res_cust = self.client.get("/api/admin/ai/health", headers={"Authorization": f"Bearer {self.cust1_token}"})
        self.assertEqual(res_cust.status_code, 403)

        # Admin access -> 200 OK
        res_admin = self.client.get("/api/admin/ai/health", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["active_provider"], "mock")
        self.assertEqual(data["embedding_provider"], "mock")
        self.assertEqual(data["vector_store"], "memory")
        self.assertIn("fallback_used", data)

    def test_security_idor_claim_analysis(self):
        """Test Customer B cannot trigger or view Customer A's claim analysis (IDOR protection)."""
        # Customer 2 attempting to analyze Claim 1 owned by Customer 1
        res = self.client.post(f"/api/claims/{self.claim1.id}/analyze", headers={"Authorization": f"Bearer {self.cust2_token}"})
        self.assertEqual(res.status_code, 403)

        # Customer 2 attempting to view Claim 1 analysis
        res2 = self.client.get(f"/api/claims/{self.claim1.id}/analysis", headers={"Authorization": f"Bearer {self.cust2_token}"})
        self.assertEqual(res2.status_code, 403)

    # --- 2. EXECUTION & TELEMETRY TESTS ---
    def test_orchestrator_execution_and_stage_telemetry(self):
        """Test execution lifecycle, stage-level AIExecutionStage creation, and telemetry recording."""
        execution = create_execution(self.db, self.claim1)
        self.assertIsNotNone(execution.execution_id)
        self.assertEqual(execution.status, "QUEUED")

        # Run orchestrator synchronously
        execute_claim_analysis(self.claim1.id, execution.execution_id)

        # Reload execution
        self.db.refresh(execution)
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(execution.actual_provider, "mock")
        self.assertEqual(execution.actual_model, "mock-v1")
        self.assertFalse(execution.fallback_used)
        self.assertIsNotNone(execution.duration_ms)
        self.assertIsNotNone(execution.input_token_count)
        self.assertIsNotNone(execution.output_token_count)

        # Verify stage-level observability rows
        stages = self.db.query(AIExecutionStage).filter(AIExecutionStage.ai_execution_id == execution.id).all()
        stage_names = set(s.stage_name for s in stages)
        self.assertIn("DOCUMENT_EXTRACTION", stage_names)
        self.assertIn("POLICY_CHECK", stage_names)
        self.assertIn("DECISION_AGENT", stage_names)
        self.assertIn("VALIDATOR", stage_names)
        self.assertIn("GOVERNANCE", stage_names)

        for s in stages:
            self.assertEqual(s.status, "COMPLETED")
            self.assertGreater(s.duration_ms, 0)

    def test_admin_executions_endpoint_telemetry(self):
        """Test GET /api/admin/claims/{id}/ai-executions returns stage timings and provider telemetry."""
        execution = create_execution(self.db, self.claim1)
        execute_claim_analysis(self.claim1.id, execution.execution_id)

        res = self.client.get(f"/api/admin/claims/{self.claim1.id}/ai-executions", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["claim_id"], self.claim1.id)
        self.assertGreater(len(data["executions"]), 0)

        first_exec = data["executions"][0]
        self.assertIn("requested_provider", first_exec)
        self.assertIn("actual_provider", first_exec)
        self.assertIn("fallback_used", first_exec)
        self.assertIn("stages", first_exec)
        self.assertGreater(len(first_exec["stages"]), 0)


    # --- 3. VECTOR STORE & DIMENSION VALIDATION TESTS ---
    def test_embedding_and_vector_dimension_mismatch(self):
        """Test vector store dimension checking raises VectorDimensionMismatchError on length mismatch."""
        embedder = MockEmbeddingProvider(dim=16)
        self.assertEqual(embedder.dimension(), 16)
        vec = embedder.embed("Test Text")
        self.assertEqual(len(vec), 16)

        store = MemoryVectorStore(expected_dim=16)
        store.upsert("doc1", vec, {"meta": "val"})
        self.assertEqual(store.count(), 1)

        # Attempt to upsert vector with wrong dimension (8 instead of 16)
        wrong_vec = [0.1] * 8
        with self.assertRaises(VectorDimensionMismatchError):
            store.upsert("doc2", wrong_vec, {})

        # Attempt search with wrong dimension
        with self.assertRaises(VectorDimensionMismatchError):
            store.search(wrong_vec, top_k=5)

    def test_pgvector_store_fallback_safety(self):
        """Test PgVectorStore initializes or cleanly reports availability/fallback status."""
        try:
            store = PgVectorStore(collection_name="test_cases", expected_dim=16)
            health = store.health_check()
            self.assertIn("type", health)
        except RuntimeError as e:
            self.assertIn("fallback to memory", str(e).lower())

    # --- 4. HISTORICAL RETRIEVAL & POLICY TRACEABILITY TESTS ---
    def test_historical_retrieval_explicit_scoring(self):
        """Test historical retrieval explicit scoring breakdown (semantic_score, structured_score, similarity_score)."""
        result = find_similar_cases(self.db, self.claim1, top_k=3)
        self.assertGreater(result.similar_case_count, 0)
        self.assertGreater(len(result.top_cases), 0)

        first_case = result.top_cases[0]
        self.assertIsNotNone(first_case.similarity_score)
        self.assertIsNotNone(first_case.semantic_score)
        self.assertIsNotNone(first_case.structured_score)
        self.assertIsNotNone(first_case.matched_features)
        self.assertIsNotNone(first_case.relevance_reason)

    def test_policy_retrieval_traceability(self):
        """Test PolicyRetriever interface and policy knowledge item relevance scoring."""
        retriever = get_policy_retriever()
        items = retriever.retrieve(self.db, self.claim1, top_k=5)
        self.assertGreater(len(items), 0)

        first_item = items[0]
        self.assertIsNotNone(first_item.policy_id)
        self.assertIsNotNone(first_item.title)
        self.assertGreater(first_item.relevance, 0.0)
        self.assertIsNotNone(first_item.reason)

    # --- 5. OCR & CONSISTENCY SERVICE TESTS ---
    def test_ocr_document_extractor_field_confidence(self):
        """Test ExtractedDocument field-level confidence scoring."""
        extractor = get_document_extractor()
        doc = extractor.extract(self.db, self.claim1)
        self.assertEqual(doc.document_type, "INVOICE")
        self.assertGreater(doc.extraction_confidence, 0.5)
        self.assertIn("invoice_number", doc.field_confidence)
        self.assertIn("confidence", doc.field_confidence["invoice_number"])

    def test_evidence_consistency_service_signals(self):
        """Test evidence consistency service detects serial mismatch and invoice discrepancies."""
        extractor = MockDocumentExtractor()
        doc = extractor.extract(self.db, self.claim1)

        # Inject serial mismatch into doc for testing
        doc.serial_number = "SN-MISMATCHED-999"

        signals = check_evidence_consistency(self.db, self.claim1, doc)
        codes = [s.code for s in signals]
        self.assertIn("SERIAL_MISMATCH", codes)

        mismatch_sig = next(s for s in signals if s.code == "SERIAL_MISMATCH")
        self.assertEqual(mismatch_sig.severity, "HIGH")
        self.assertEqual(mismatch_sig.source, "OCR_CONSISTENCY")

    # --- 6. EVALUATION & GOLDEN DATASET TESTS ---
    def test_golden_dataset_scenarios(self):
        """Test golden dataset fixtures Scenarios A through H are loaded deterministically."""
        dataset = get_golden_dataset()
        self.assertEqual(len(dataset), 8)
        scenario_ids = [s["scenario_id"] for s in dataset]
        self.assertIn("SCENARIO_A", scenario_ids)
        self.assertIn("SCENARIO_B", scenario_ids)
        self.assertIn("SCENARIO_C", scenario_ids)
        self.assertIn("SCENARIO_D", scenario_ids)

    def test_model_evaluation_and_retrieval_endpoints(self):
        """Test GET /api/admin/evaluation, /dataset, and /retrieval endpoints."""
        res_eval = self.client.get("/api/admin/evaluation", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res_eval.status_code, 200)
        data_eval = res_eval.json()
        self.assertIn("evaluation_sample_size", data_eval)
        self.assertIn("confidence_calibration", data_eval)

        res_ret = self.client.get("/api/admin/evaluation/retrieval", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res_ret.status_code, 200)
        data_ret = res_ret.json()
        self.assertIn("status", data_ret)

        res_ds = self.client.get("/api/admin/evaluation/dataset", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res_ds.status_code, 200)
        data_ds = res_ds.json()
        self.assertIn("dataset", data_ds)

    # --- 7. FAILURE INJECTION TESTS ---
    def test_failure_injection_provider_timeout(self):
        """Test orchestrator handles controlled execution timeout gracefully without uncaught stack traces."""
        execution = create_execution(self.db, self.claim1)
        # Set artificially small timeout in settings for test
        settings = get_settings()
        original_timeout = settings.AI_EXECUTION_TIMEOUT_SECONDS
        settings.AI_EXECUTION_TIMEOUT_SECONDS = -1  # force immediate timeout check

        try:
            execute_claim_analysis(self.claim1.id, execution.execution_id)
            self.db.refresh(execution)
            self.assertEqual(execution.status, "TIMED_OUT")
            self.assertEqual(execution.error_code, "AI_EXECUTION_TIMEOUT")
        finally:
            settings.AI_EXECUTION_TIMEOUT_SECONDS = original_timeout


if __name__ == "__main__":
    unittest.main()
