"""
Demo data seeding — Part 1.2 Core Warranty Data + Claim Workflow

Phase 2: auth demo accounts
Part 1.2: products, policies, serials, claims across all states

Run with (from /backend, venv active):
    python seed.py

Demo accounts created:
    customer  demo.customer@warrantyos.com   / DemoPass123!
    admin     demo.admin@warrantyos.com      / DemoPass123!
    + additional synthetic customers for workflow testing
"""

from datetime import date, datetime, timezone, timedelta
import random

from app.core.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.core.security import hash_password
from app.models.product import Product, Retailer, ProductionBatch, ProductSerial, WarrantyPolicy
from app.models.user import Admin, Customer, Role, User
from app.models.claim import Claim, ClaimTimeline, ClaimEvidence

DEMO_PASSWORD = "DemoPass123!"

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # Roles — seed individually to avoid skipping if one already exists
    for rname in ("customer", "admin", "support"):
        if not db.query(Role).filter(Role.name == rname).first():
            db.add(Role(name=rname))
    db.commit()
    if db.query(Role).count() == 3:
        print("Seeded roles: customer, admin, support")

    if not db.query(Product).first():
        db.add(Product(
            name="Washing Machine X1",
            sku="WMX1-2026",
            category="Home Appliances",
            manufacturer="Aurelia Home",
            warranty_period_months=24,
        ))
        db.commit()
        print("Seeded demo product: Washing Machine X1")

    if not db.query(Retailer).first():
        db.add(Retailer(name="Aurelia Direct Store", region="National"))
        db.commit()
        print("Seeded demo retailer: Aurelia Direct Store")

    customer_role = db.query(Role).filter(Role.name == "customer").first()
    admin_role = db.query(Role).filter(Role.name == "admin").first()

    if not customer_role or not admin_role:
        raise RuntimeError("Roles not seeded — cannot create demo users")

    if not db.query(User).filter(User.email == "demo.customer@warrantyos.com").first():
        demo_customer_user = User(
            email="demo.customer@warrantyos.com",
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name="Rahul Mehta",
            role_id=customer_role.id,
        )
        db.add(demo_customer_user)
        db.flush()
        db.add(Customer(user_id=demo_customer_user.id, phone="+91 98765 43210"))
        db.commit()
        print("Seeded demo customer login: demo.customer@warrantyos.com")

    if not db.query(User).filter(User.email == "demo.admin@warrantyos.com").first():
        demo_admin_user = User(
            email="demo.admin@warrantyos.com",
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name="Priya Nair",
            role_id=admin_role.id,
        )
        db.add(demo_admin_user)
        db.flush()
        db.add(Admin(user_id=demo_admin_user.id, department="Claims Operations"))
        db.commit()
        print("Seeded demo admin login: demo.admin@warrantyos.com")

    print(f"\nDemo password for both accounts: {DEMO_PASSWORD}")
    print("Phase 2 seed complete.")

    # ==================== Part 1.2: Warranty Domain ====================
    print("\n--- Part 1.2 seeding ---")

    # Products (5)
    products_data = [
        ("Washing Machine X1", "WMX1-2026", "Home Appliances", "Aurelia Home", 24),
        ("Refrigerator Frost 300", "RFF300-2025", "Home Appliances", "FrostTech", 24),
        ("AC CoolMax 1.5T", "ACCM15-2024", "Home Appliances", "CoolMax", 12),
        ("Microwave SwiftHeat 25L", "MWSH25-2025", "Kitchen Appliances", "SwiftHeat", 12),
        ("TV VisionPro 55", "TVVP55-2025", "Electronics", "VisionPro", 24),
    ]
    for name, sku, cat, manuf, months in products_data:
        if not db.query(Product).filter(Product.sku == sku).first():
            db.add(Product(name=name, sku=sku, category=cat, manufacturer=manuf, warranty_period_months=months))
    db.commit()
    print(f"Products: {db.query(Product).count()}")

    # Retailers (3)
    for rname, region in [("Aurelia Direct Store", "National"), ("Electro Hub", "West"), ("QuickTrade", "South")]:
        if not db.query(Retailer).filter(Retailer.name == rname).first():
            db.add(Retailer(name=rname, region=region))
    db.commit()

    # Warranty Policies
    policy_specs = {
        "WMX1-2026": (24, ["Manufacturing defects", "Motor failure", "Electrical failure"], ["Physical damage", "Water damage", "Unauthorized repair"], "Proof of purchase required; serial must match; commercial use excluded.", ["motor", "drum", "pump", "leak"]),
        "RFF300-2025": (24, ["Compressor failure", "Cooling system defect"], ["Physical damage", "Power surge", "Improper installation"], "Original invoice required.", ["compressor", "cooling", "overheat"]),
        "ACCM15-2024": (12, ["Compressor failure", "Gas leakage manufacturing"], ["Accidental damage", "Water damage", "Normal wear"], "Annual servicing required.", ["compressor", "gas", "cooling", "overheat"]),
        "MWSH25-2025": (12, ["Magnetron failure", "Electrical defect"], ["Physical damage", "Water damage"], "Domestic use only.", ["magnetron", "display", "heating"]),
        "TVVP55-2025": (24, ["Panel defect", "Backlight failure", "Speaker defect"], ["Physical damage", "Water damage", "Power surge", "Screen burn due to misuse"], "Panel warranty covers manufacturing defects only.", ["display", "panel", "backlight", "speaker"]),
    }
    for sku, (months, covered, not_covered, cond, cats) in policy_specs.items():
        prod = db.query(Product).filter(Product.sku == sku).first()
        if prod and not db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == prod.id).first():
            db.add(WarrantyPolicy(product_id=prod.id, warranty_months=months, covered=covered, not_covered=not_covered, conditions=cond, covered_fault_categories=cats))
    db.commit()
    print(f"WarrantyPolicies: {db.query(WarrantyPolicy).count()}")

    # Production Batches (one per product)
    for prod in db.query(Product).all():
        if not db.query(ProductionBatch).filter(ProductionBatch.product_id == prod.id).first():
            db.add(ProductionBatch(product_id=prod.id, batch_code=f"BATCH-{prod.sku}-01", produced_on=date(2024, 6, 1), units_produced=1000))
    db.commit()

    # Additional customers
    extra_customers = [
        ("arjun.patel@example.com", "Arjun Patel", "+91 98765 43211"),
        ("sara.khan@example.com", "Sara Khan", "+91 98765 43212"),
        ("vikram.desai@example.com", "Vikram Desai", "+91 98765 43213"),
    ]
    for email, full_name, phone in extra_customers:
        if not db.query(User).filter(User.email == email).first():
            u = User(email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=full_name, role_id=customer_role.id)
            db.add(u)
            db.flush()
            db.add(Customer(user_id=u.id, phone=phone))
            db.commit()
            print(f"Seeded customer {email}")

    # Product Serials with ownership & purchase dates
    retailer_map = {r.name: r for r in db.query(Retailer).all()}
    prod_map = {p.sku: p for p in db.query(Product).all()}
    batch_map = {b.product_id: b for b in db.query(ProductionBatch).all()}
    cust_map = {}
    for u in db.query(User).all():
        c = db.query(Customer).filter(Customer.user_id == u.id).first()
        if c:
            cust_map[u.email] = c

    serials_data = [
        # (serial, sku, owner_email, purchase_date, retailer_name)
        ("WMX-98234", "WMX1-2026", "demo.customer@warrantyos.com", date(2025, 3, 15), "Aurelia Direct Store"),  # active
        ("RF-44102", "RFF300-2025", "demo.customer@warrantyos.com", date(2023, 1, 10), "Aurelia Direct Store"),  # expired (24mo -> 2025-01-10)
        ("AC-CM-7781", "ACCM15-2024", "demo.customer@warrantyos.com", date(2024, 9, 1), "Electro Hub"),  # active? 12mo -> 2025-09-01 pending expired? today 2026 -> expired
        ("RF-33111", "RFF300-2025", "arjun.patel@example.com", date(2024, 9, 1), "Electro Hub"),  # active
        ("TV-55201", "TVVP55-2025", "arjun.patel@example.com", date(2024, 2, 20), "QuickTrade"),  # expired (24mo -> 2026-02-20, today maybe 2026-08 -> active? borderline)
        ("MW-9901", "MWSH25-2025", "sara.khan@example.com", date(2025, 1, 10), "Aurelia Direct Store"),  # active 12mo -> 2026-01-10 expired? today 2026-08 -> expired
        ("TV-55302", "TVVP55-2025", "vikram.desai@example.com", date(2022, 5, 1), "Electro Hub"),  # expired
        ("WM-99102", "WMX1-2026", "vikram.desai@example.com", date(2025, 7, 1), "Aurelia Direct Store"),  # active
        ("WM-99103", "WMX1-2026", "sara.khan@example.com", date(2025, 5, 20), "QuickTrade"),  # active
        ("AC-88201", "ACCM15-2024", "vikram.desai@example.com", date(2025, 2, 15), "Electro Hub"),  # active 12mo -> 2026-02-15
    ]
    for serial_num, sku, owner_email, pur_date, retailer_name in serials_data:
        if not db.query(ProductSerial).filter(ProductSerial.serial_number == serial_num).first():
            prod = prod_map.get(sku)
            cust = cust_map.get(owner_email)
            batch = batch_map.get(prod.id) if prod else None
            retailer = retailer_map.get(retailer_name)
            db.add(ProductSerial(
                product_id=prod.id if prod else None,
                batch_id=batch.id if batch else None,
                serial_number=serial_num,
                sold_by_retailer_id=retailer.id if retailer else None,
                purchase_date=pur_date,
                owner_customer_id=cust.id if cust else None,
            ))
    db.commit()
    print(f"ProductSerials: {db.query(ProductSerial).count()}")

    # Claims across states (Part 1.2) — deterministic, no AI
    # Helper to create claim if not exists by claim_code
    from app.services.warranty_rules import evaluate_warranty

    claims_data = [
        # (code, customer_email, sku, serial, fault_desc, fault_cat, status, purchase_override, exclusions_test)
        ("WR-20001", "demo.customer@warrantyos.com", "WMX1-2026", "WMX-98234", "Washing machine drum not spinning, loud noise during cycle, motor seems to fail intermittently.", "motor", "SUBMITTED", None, False),
        ("WR-20002", "arjun.patel@example.com", "RFF300-2025", "RF-33111", "Refrigerator compressor not cooling, temperature rising, food spoiling.", "compressor", "PROCESSING", None, False),
        ("WR-20003", "sara.khan@example.com", "MWSH25-2025", "MW-9901", "Microwave display panel flickering and not heating food evenly.", "display", "UNDER_REVIEW", None, False),
        ("WR-20004", "vikram.desai@example.com", "WMX1-2026", "WM-99102", "Washing machine water leak from bottom, pump issue suspected.", "pump", "APPROVED", None, False),
        ("WR-20005", "demo.customer@warrantyos.com", "RFF300-2025", "RF-44102", "Refrigerator not cooling, but purchase was 2023, warranty should be expired.", "compressor", "REJECTED", None, False),
        ("WR-20006", "arjun.patel@example.com", "RFF300-2025", "RF-33111", "Refrigerator has physical damage due to accidental drop, compressor area dented and housing cracked.", "compressor", "MORE_INFORMATION_REQUIRED", None, True),  # triggers exclusion (Physical damage) with active warranty
        ("WR-20007", "sara.khan@example.com", "WMX1-2026", "WM-99103", "Washing machine motor overheat and drum stuck, needs thorough review.", "motor", "RESOLVED", None, False),
    ]

    for code, cust_email, sku, serial_num, fault_desc, fault_cat, target_status, pur_override, force_excluded in claims_data:
        if db.query(Claim).filter(Claim.claim_code == code).first():
            continue
        cust = cust_map.get(cust_email)
        prod = prod_map.get(sku)
        serial = db.query(ProductSerial).filter(ProductSerial.serial_number == serial_num).first() if serial_num else None
        retailer_id = serial.sold_by_retailer_id if serial else None
        policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == prod.id).first() if prod else None

        # Evaluate warranty deterministically
        result = evaluate_warranty(
            product=prod,
            serial=serial,
            policy=policy,
            customer_id=cust.id if cust else None,
            fault_description=fault_desc,
            fault_category=fault_cat,
            purchase_date_override=pur_override,
            today=date(2026, 5, 15),  # fixed today for deterministic seed
        )
        # For forced excluded case, ensure fault contains exclusion term
        if force_excluded:
            fault_desc = "Refrigerator has physical damage due to accidental drop, compressor housing cracked."
            result = evaluate_warranty(product=prod, serial=serial, policy=policy, customer_id=cust.id if cust else None, fault_description=fault_desc, fault_category=fault_cat, today=date(2026,5,15))
            # result should be EXCLUDED

        claim = Claim(
            claim_code=code,
            customer_id=cust.id,
            product_id=prod.id,
            serial_id=serial.id if serial else None,
            retailer_id=retailer_id,
            fault_description=fault_desc,
            fault_category=fault_cat,
            status=target_status,
            purchase_date=result.purchase_date,
            warranty_eligible=result.eligible,
            eligibility_reason=result.reason,
            warranty_checked_at=datetime.now(timezone.utc),
            exclusions_triggered=result.exclusions_triggered,
            missing_information=result.missing_information,
        )
        db.add(claim)
        db.flush()
        # Timeline events
        events = [
            ("CLAIM_CREATED", f"customer:{cust_email}", f"Claim {code} created.", {"warranty_eligible": result.eligible}),
            ("WARRANTY_CHECKED", "system", result.reason, {"eligible": result.eligible, "reason": result.reason}),
        ]
        # Add status progression history
        # Map target_status to progression: SUBMITTED->PROCESSING->... etc, create STATUS_CHANGED events for history
        progression = {
            "SUBMITTED": [],
            "PROCESSING": ["SUBMITTED->PROCESSING"],
            "UNDER_REVIEW": ["SUBMITTED->PROCESSING", "PROCESSING->UNDER_REVIEW"],
            "APPROVED": ["SUBMITTED->PROCESSING", "PROCESSING->APPROVED"],
            "REJECTED": ["SUBMITTED->PROCESSING", "PROCESSING->REJECTED"],
            "MORE_INFORMATION_REQUIRED": ["SUBMITTED->PROCESSING", "PROCESSING->MORE_INFORMATION_REQUIRED"],
            "RESOLVED": ["SUBMITTED->PROCESSING", "PROCESSING->APPROVED", "APPROVED->RESOLVED"],
        }
        for step in progression.get(target_status, []):
            frm, to = step.split("->")
            events.append(("STATUS_CHANGED", "system", f"Status {frm} -> {to}", {"from": frm, "to": to}))
        for etype, actor, notes, meta in events:
            db.add(ClaimTimeline(claim_id=claim.id, event_type=etype, actor=actor, notes=notes, event_metadata=meta))

        # Add some evidence for a few claims
        if code in ("WR-20001", "WR-20003", "WR-20007"):
            # synthetic evidence metadata (no actual file, just DB record)
            ev_type = "INVOICE" if code == "WR-20001" else "PHOTO"
            db.add(ClaimEvidence(claim_id=claim.id, evidence_type=ev_type, file_path=f"{claim.id}/seed_{ev_type.lower()}.pdf", original_filename=f"{ev_type.lower()}.pdf", stored_filename=f"seed_{ev_type.lower()}.pdf", mime_type="application/pdf" if ev_type=="INVOICE" else "image/jpeg", file_size=102400, uploaded_by_user_id=cust.user_id if cust else None, description=f"Seed evidence for {code}"))

        db.commit()
        print(f"Seeded claim {code} status={target_status} eligible={result.eligible}")

    print(f"Claims: {db.query(Claim).count()}")
    print(f"ClaimTimeline: {db.query(ClaimTimeline).count()}")
    print(f"ClaimEvidence: {db.query(ClaimEvidence).count()}")
    print("Part 1.2 seed complete.")

    # ==================== Part 2.2: Historical Case Corpus (20-50) ====================
    print("\n--- Part 2.2 historical corpus ---")
    from app.models.intelligence import HistoricalCase
    if db.query(HistoricalCase).count() < 20:
        # Clear and reseed for determinism
        # Create 30 historical cases across products and fault types
        historical_data = [
            # Washing Machine cases
            ("WMX1-2026", "motor", "REPAIR", "Washing machine motor failure, drum not spinning, loud noise. Warranty active. Repaired under warranty."),
            ("WMX1-2026", "pump", "REPAIR", "Water leak from pump, bottom leakage. Manufacturing defect confirmed. Pump replaced."),
            ("WMX1-2026", "drum", "REPLACE", "Drum stuck, overheat, repeated failures. Beyond repair, unit replaced."),
            ("WMX1-2026", "motor", "REPAIR", "Motor overheat, intermittent failure. Cooling fan replaced."),
            ("WMX1-2026", "leak", "REPAIR", "Inlet hose leak, water damage but not physical damage. Hose replaced."),
            ("WMX1-2026", "motor", "DENY", "Motor failure but physical damage due to unauthorized repair attempt. Claim denied."),
            # Refrigerator cases
            ("RFF300-2025", "compressor", "REPAIR", "Compressor not cooling, temperature high. Compressor replaced under warranty."),
            ("RFF300-2025", "cooling", "REPAIR", "Cooling system defect, food spoiling. Thermostat replaced."),
            ("RFF300-2025", "compressor", "DENY", "Physical damage to compressor housing due to drop. Not covered."),
            ("RFF300-2025", "overheat", "REPAIR", "Overheating, condenser fan failure. Fan replaced."),
            ("RFF300-2025", "cooling", "REPLACE", "Repeated cooling failures, sealed system leak. Unit replaced."),
            ("RFF300-2025", "compressor", "DENY", "Power surge damage, not covered per policy. Claim denied."),
            # AC cases
            ("ACCM15-2024", "compressor", "REPAIR", "AC compressor failure, no cooling. Compressor replaced."),
            ("ACCM15-2024", "gas", "REPAIR", "Gas leakage, manufacturing defect. Refilled and sealed."),
            ("ACCM15-2024", "cooling", "DENY", "Accidental damage to outdoor unit, physical dent. Not covered."),
            ("ACCM15-2024", "overheat", "REPAIR", "Overheating, fan motor failure. Motor replaced."),
            ("ACCM15-2024", "gas", "DENY", "Normal wear after 14 months, warranty 12 months expired. Denied."),
            # Microwave cases
            ("MWSH25-2025", "magnetron", "REPAIR", "Magnetron failure, not heating. Magnetron replaced."),
            ("MWSH25-2025", "display", "REPAIR", "Display flickering, control panel defect. Panel replaced."),
            ("MWSH25-2025", "heating", "REPLACE", "Uneven heating, waveguide defect. Unit replaced."),
            ("MWSH25-2025", "magnetron", "DENY", "Water damage inside cavity due to misuse. Not covered."),
            # TV cases
            ("TVVP55-2025", "display", "REPAIR", "Panel defect, backlight flickering. Panel replaced under warranty."),
            ("TVVP55-2025", "panel", "REPLACE", "Severe panel crack, manufacturing defect. Unit replaced."),
            ("TVVP55-2025", "display", "DENY", "Physical damage due to drop, screen cracked. Not covered."),
            ("TVVP55-2025", "speaker", "REPAIR", "Speaker defect, no sound. Speaker replaced."),
            ("TVVP55-2025", "backlight", "REPAIR", "Backlight failure, dim display. Backlight strip replaced."),
            ("TVVP55-2025", "display", "DENY", "Power surge damage, not covered. Claim denied."),
            ("TVVP55-2025", "panel", "REPAIR", "Panel discoloration, manufacturing defect. Panel replaced."),
            ("RFF300-2025", "cooling", "REPAIR", "Cooling issue, door seal defect. Seal replaced."),
            ("WMX1-2026", "pump", "REPAIR", "Pump blockage, water not draining. Pump cleaned and replaced."),
        ]
        # Ensure we have 30 by repeating with variations if needed
        # Currently we have 29, add one more
        historical_data.append(("ACCM15-2024", "compressor", "REPAIR", "AC not cooling, compressor relay failure. Relay replaced."))

        for sku, fault_cat, resolution, summary in historical_data:
            prod = prod_map.get(sku)
            if not prod:
                continue
            # Avoid duplicates: check if similar exists
            existing = db.query(HistoricalCase).filter(HistoricalCase.product_id==prod.id, HistoricalCase.fault_category==fault_cat, HistoricalCase.summary==summary).first()
            if existing:
                continue
            db.add(HistoricalCase(product_id=prod.id, fault_category=fault_cat, resolution=resolution, summary=summary))
        db.commit()
        print(f"HistoricalCases: {db.query(HistoricalCase).count()} (seeded 30)")
    else:
        print(f"HistoricalCases: {db.query(HistoricalCase).count()} (already seeded)")

    print("Part 2.2 historical corpus complete.")

except Exception as e:
    db.rollback()
    print(f"Seed failed: {e}")
    raise
finally:
    db.close()
