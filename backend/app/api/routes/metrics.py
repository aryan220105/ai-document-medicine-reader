from fastapi import APIRouter, Request

from app.dependencies import AppContainer

router = APIRouter()


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    """Operational counters for the interpreter and the upload pipeline.

    Deliberately plain JSON rather than a metrics exposition format: the point is that
    somebody running this can answer "is the model being called, is it failing, is the
    cache doing its job, and what is it costing" without turning on debug logging. The
    numbers are per process and reset on restart.
    """
    container: AppContainer = request.app.state.container
    interpreter = container.interpreter
    return {
        "interpreter": {
            "available": interpreter.available(),
            "circuit_open": not interpreter.breaker.allow(),
            "consecutive_failures": interpreter.breaker.failures,
            "cache_entries": len(interpreter.cache.entries),
            **interpreter.stats.snapshot(),
        },
        "documents": container.documents.counters(),
        "uploads": container.rate_limiter.snapshot(),
    }
