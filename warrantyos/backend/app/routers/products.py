"""
Products & Serials endpoints — Part 1.2 minimal
Allows customer to discover owned products for claim creation.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, Customer
from app.models.product import Product, ProductSerial, WarrantyPolicy, Retailer

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=List[dict])
def list_products(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    prods = db.query(Product).filter(Product.is_active == True).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "category": p.category,
            "manufacturer": p.manufacturer,
            "warranty_period_months": p.warranty_period_months,
        }
        for p in prods
    ]


@router.get("/serials/mine", response_model=List[dict])
def list_my_serials(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Only customers have serials; admins get empty
    cust = db.query(Customer).filter(Customer.user_id == current_user.id).first()
    if not cust:
        return []
    serials = db.query(ProductSerial).filter(ProductSerial.owner_customer_id == cust.id).all()
    out = []
    for s in serials:
        prod = db.query(Product).filter(Product.id == s.product_id).first()
        retailer = db.query(Retailer).filter(Retailer.id == s.sold_by_retailer_id).first() if s.sold_by_retailer_id else None
        out.append({
            "id": s.id,
            "serial_number": s.serial_number,
            "product_id": s.product_id,
            "product_name": prod.name if prod else None,
            "product_sku": prod.sku if prod else None,
            "purchase_date": s.purchase_date.isoformat() if s.purchase_date else None,
            "retailer": retailer.name if retailer else None,
        })
    return out


@router.get("/{product_id}", response_model=dict)
def get_product(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found.")
    policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == p.id).first()
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "category": p.category,
        "manufacturer": p.manufacturer,
        "warranty_period_months": p.warranty_period_months,
        "policy": {
            "warranty_months": policy.warranty_months if policy else p.warranty_period_months,
            "covered": policy.covered if policy and policy.covered else [],
            "not_covered": policy.not_covered if policy and policy.not_covered else [],
            "conditions": policy.conditions if policy and policy.conditions else None,
        } if policy else None,
    }
