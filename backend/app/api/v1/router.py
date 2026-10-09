from fastapi import APIRouter

from app.api.v1 import auth, batches, beers, calc, catalog, health, me, recipes, styles, tastings

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(calc.router)
router.include_router(styles.router)
router.include_router(catalog.router)
router.include_router(recipes.router)
router.include_router(batches.router)
router.include_router(beers.router)
router.include_router(tastings.router)
