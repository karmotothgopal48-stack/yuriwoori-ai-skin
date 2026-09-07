import sys
import os
import time
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.db.models import Product
from app.services.shopify_client import get_variant_id_by_handle


def resolve():
    db = SessionLocal()
    products = db.query(Product).filter(Product.active == True).all()  # noqa: E712

    resolved, missing = 0, 0
    for p in products:
        # shopify_product_id holds the real handle (from the CSV import in Step 12)
        variant_id = get_variant_id_by_handle(p.shopify_product_id)
        if variant_id:
            p.shopify_variant_id = variant_id
            resolved += 1
        else:
            print(f"No live variant found for '{p.name}' (handle: {p.shopify_product_id})")
            missing += 1
        time.sleep(0.3)

    db.commit()
    db.close()
    print(f"Resolved {resolved} variants, {missing} missing.")


if __name__ == "__main__":
    resolve()