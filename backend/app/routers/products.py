from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from typing import List, Optional
from app.database import get_db
from app.models import Product
from app.schemas import ProductOut

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("", response_model=List[ProductOut])
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = Query(None, description="price_asc, price_desc, rating_desc, newest"),
    featured: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.is_active == True)

    if category:
        query = query.filter(Product.category_slug == category)
    
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.brand.ilike(search_term),
                Product.description.ilike(search_term),
                Product.category_slug.ilike(search_term)
            )
        )

    if brand:
        query = query.filter(Product.brand == brand)

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if featured is not None:
        query = query.filter(Product.is_featured == featured)

    # Sorting
    if sort_by == "price_asc":
        query = query.order_by(asc(Product.price))
    elif sort_by == "price_desc":
        query = query.order_by(desc(Product.price))
    elif sort_by == "rating_desc":
        query = query.order_by(desc(Product.rating))
    elif sort_by == "newest":
        query = query.order_by(desc(Product.id))
    else:
        query = query.order_by(desc(Product.id))

    return query.offset(offset).limit(limit).all()

@router.get("/deals", response_model=List[ProductOut])
def get_deals(limit: int = 10, db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.is_active == True, Product.discount_percent > 0).order_by(desc(Product.discount_percent)).limit(limit).all()

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
