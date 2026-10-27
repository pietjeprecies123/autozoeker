"""Command line: `autozoeker serve | seed-demo | crawl | retrain | verify-sources | capture | research`."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Autozoeker – tweedehands auto's zoeken voor de Nederlandse markt", no_args_is_help=True)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the web app (API + UI)."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command("seed-demo")
def seed_demo(n: int = 5000):
    """Load the demo dataset and train the valuation model."""
    from app.analysis import refresh
    from app.db import migrate, session_scope
    from app.demo.seed import seed_demo as seed

    migrate()
    with session_scope() as session:
        added = seed(session, n=n)
    with session_scope() as session:
        refresh(session, retrain=True)
    typer.echo(f"{added} demo-advertenties toegevoegd")


@app.command()
def crawl():
    """Run one crawl cycle now (sources → ingest → score → alerts)."""
    from app.db import migrate
    from app.scheduler import crawl_cycle

    migrate()
    typer.echo(json.dumps(crawl_cycle(), indent=2))


@app.command()
def retrain():
    """Retrain the valuation model and rescore all active listings."""
    from app.db import migrate
    from app.scheduler import nightly
    from app.valuation.model import get_model_instance

    migrate()
    nightly()
    typer.echo(json.dumps(get_model_instance().metrics, indent=2))


@app.command("verify-sources")
def verify_sources(make: str = "volkswagen", model: str = "golf"):
    """Fetch one page from each real source and report how well it parses."""
    from app.sources.base import SourceQuery
    from app.sources.registry import ALL, get_adapter

    for name in ALL:
        adapter = get_adapter(name)
        try:
            items = list(adapter.search(SourceQuery(make=make, model=model, max_pages=1)))
        except Exception as exc:
            typer.secho(f"{name}: FOUT – {type(exc).__name__}: {exc}", fg="red")
            continue
        if not items:
            typer.secho(f"{name}: 0 advertenties geparsed – parser moet worden aangepast (zie `capture`)", fg="red")
            continue
        fields = ["price_eur", "mileage_km", "first_registration", "fuel_raw", "postcode", "city", "kenteken", "image_urls"]
        filled = {f: sum(1 for i in items if getattr(i, f)) for f in fields}
        typer.secho(f"{name}: {len(items)} advertenties", fg="green")
        for f, n in filled.items():
            typer.echo(f"  {f:20s} {n}/{len(items)}")
        typer.echo(f"  voorbeeld: {items[0].title} – €{items[0].price_eur} – {items[0].mileage_km} km – {items[0].url}")


@app.command()
def capture(source: str, make: str = "volkswagen", model: str = "golf", out: Path = Path("captures")):
    """Save raw search responses from a source (to build test fixtures / fix the parser)."""
    from app.sources import autoscout24, marktplaats
    from app.sources.base import PoliteClient, SourceQuery

    out.mkdir(parents=True, exist_ok=True)
    client = PoliteClient()
    q = SourceQuery(make=make, model=model)
    if source == "autoscout24":
        url = autoscout24.search_url(q, 1)
        path = out / f"autoscout24_{make}_{model}.html"
        path.write_text(client.get(url).text, encoding="utf-8")
    elif source == "marktplaats":
        url = marktplaats.search_url(q, 0)
        path = out / f"marktplaats_{make}_{model}.json"
        path.write_text(client.get(url, headers={"Accept": "application/json"}).text, encoding="utf-8")
    else:
        raise typer.BadParameter("source moet autoscout24 of marktplaats zijn")
    typer.echo(f"{url}\n→ {path}")


@app.command()
def research(make: str, model: str, generation: str | None = None, force: bool = False):
    """Research known issues for a model with Claude (needs ANTHROPIC_API_KEY)."""
    from app.ai.research import get_or_research
    from app.db import migrate, session_scope

    migrate()
    with session_scope() as session:
        rec = get_or_research(session, make, model, generation, force=force)
        typer.echo(json.dumps(rec.result, indent=2, ensure_ascii=False))
        typer.echo(f"kosten: ${rec.cost_usd} ({rec.input_tokens} in, {rec.output_tokens} uit, {rec.web_searches} zoekopdrachten)")


if __name__ == "__main__":
    app()
